"""Compile available native kernels and compare their canonical output bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from .reference import evaluate_bytes
except ImportError:
    from reference import evaluate_bytes


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
CPP_SOURCE = HERE / "cpp" / "kernel.cpp"
RUST_SOURCE = HERE / "rust" / "kernel.rs"
REFERENCE = HERE / "reference.py"


def _xorshift64(state: int) -> int:
    state ^= (state << 13) & ((1 << 64) - 1)
    state ^= state >> 7
    state ^= (state << 17) & ((1 << 64) - 1)
    return state & ((1 << 64) - 1)


def generate_input(count: int, seed: int) -> bytes:
    """Generate deterministic synthetic feature rows without external packages."""
    if count < 1:
        raise ValueError("candidates must be positive")
    state = seed & ((1 << 64) - 1) or 1
    rows = ["NATIVE_PROXY_V1\n"]
    for index in range(count):
        values = []
        for _ in range(7):
            state = _xorshift64(state)
            values.append(state)
        cross_task = values[4] % 65
        cross_core = values[5] % (cross_task + 1)
        fields = (
            f"candidate-{index:05d}",
            500_000 + values[0] % 50_000_000,
            500_000 + values[1] % 50_000_000,
            values[2] % 2_000_000,
            1 + values[3] % 65_536,
            cross_task,
            cross_core,
            750_000 + values[6] % 1_500_001,
        )
        rows.append("\t".join(map(str, fields)) + "\n")
    return "".join(rows).encode("ascii")


def _run(command: list[str], raw: bytes) -> bytes:
    process = subprocess.run(command, input=raw, capture_output=True, check=False)
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"command failed with exit {process.returncode}: {stderr}")
    return process.stdout


def _time_command(
    command: list[str], raw: bytes, expected: bytes, iterations: int
) -> dict:
    _run(command, raw)
    elapsed_ms = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        actual = _run(command, raw)
        elapsed_ms.append((time.perf_counter_ns() - start) / 1_000_000)
        if actual != expected:
            raise RuntimeError("output changed during timing")
    ordered = sorted(elapsed_ms)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "kind": "end_to_end_process_ms",
        "iterations": iterations,
        "warmup": 1,
        "median_ms": round(statistics.median(elapsed_ms), 6),
        "p95_ms": round(ordered[p95_index], 6),
        "min_ms": round(ordered[0], 6),
    }


def _compiler_version(command: list[str]) -> str:
    process = subprocess.run(command, capture_output=True, check=False)
    combined = process.stdout + b"\n" + process.stderr
    executable = Path(command[0]).name.lower()
    if executable in {"cl", "cl.exe"}:
        import re

        match = re.search(rb"\b\d+(?:\.\d+){2,3}\b", combined)
        if match:
            return f"Microsoft C/C++ {match.group().decode('ascii')}"
        return "Microsoft C/C++ (version unknown)"
    lines = combined.decode("utf-8", errors="replace").strip().splitlines()
    return lines[0].strip() if lines else "unknown"


def _compile_cpp(build_dir: Path) -> tuple[list[str] | None, dict]:
    compiler = next(
        (shutil.which(name) for name in ("cl", "g++", "clang++") if shutil.which(name)),
        None,
    )
    if compiler is None:
        return None, {
            "status": "unavailable",
            "reason": "cl, g++, and clang++ not found on PATH",
        }
    name = Path(compiler).name.lower()
    executable = build_dir / (
        "native_proxy_cpp.exe" if os.name == "nt" else "native_proxy_cpp"
    )
    if name == "cl.exe" or name == "cl":
        object_file = build_dir / "native_proxy_cpp.obj"
        command = [
            compiler,
            "/nologo",
            "/EHsc",
            "/std:c++17",
            "/O2",
            "/W4",
            str(CPP_SOURCE),
            f"/Fo:{object_file}",
            f"/Fe:{executable}",
        ]
        display = (
            "cl /nologo /EHsc /std:c++17 /O2 /W4 "
            "src/eval_proxy/native/cpp/kernel.cpp "
            "/Fo:<temp>/native_proxy_cpp.obj /Fe:<temp>/native_proxy_cpp.exe"
        )
        version_command = [compiler]
    else:
        command = [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-pedantic",
            str(CPP_SOURCE),
            "-o",
            str(executable),
        ]
        display = f"{Path(compiler).name} -std=c++17 -O2 -Wall -Wextra -pedantic src/eval_proxy/native/cpp/kernel.cpp -o <temp>/native_proxy_cpp"
        version_command = [compiler, "--version"]
    process = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
        errors="replace",
    )
    if process.returncode != 0:
        detail = (process.stdout + "\n" + process.stderr).strip()
        return None, {
            "status": "compile_failed",
            "compiler": Path(compiler).name,
            "command": display,
            "detail": detail,
        }
    return [str(executable)], {
        "status": "ran",
        "compiler": Path(compiler).name,
        "version": _compiler_version(version_command),
        "command": display,
    }


def _compile_rust(build_dir: Path) -> tuple[list[str] | None, dict]:
    compiler = shutil.which("rustc")
    if compiler is None:
        reason = "rustc not found on PATH"
        if shutil.which("cargo") is None:
            reason += "; cargo not found on PATH"
        return None, {"status": "unavailable", "reason": reason}
    executable = build_dir / (
        "native_proxy_rust.exe" if os.name == "nt" else "native_proxy_rust"
    )
    command = [
        compiler,
        "--edition=2021",
        "-C",
        "opt-level=2",
        str(RUST_SOURCE),
        "-o",
        str(executable),
    ]
    display = "rustc --edition=2021 -C opt-level=2 src/eval_proxy/native/rust/kernel.rs -o <temp>/native_proxy_rust"
    process = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
        errors="replace",
    )
    if process.returncode != 0:
        return None, {
            "status": "compile_failed",
            "compiler": "rustc",
            "command": display,
            "detail": (process.stdout + "\n" + process.stderr).strip(),
        }
    return [str(executable)], {
        "status": "ran",
        "compiler": "rustc",
        "version": _compiler_version([compiler, "--version"]),
        "command": display,
    }


def _comparison(
    command: list[str] | None,
    metadata: dict,
    raw: bytes,
    expected: bytes,
    iterations: int,
) -> dict:
    if command is None:
        return {"status": metadata["status"], "byte_equal": None}
    actual = _run(command, raw)
    return {
        "status": "pass" if actual == expected else "fail",
        "byte_equal": actual == expected,
        "output_sha256": hashlib.sha256(actual).hexdigest(),
        "output_bytes": len(actual),
        "timing": _time_command(command, raw, expected, iterations)
        if actual == expected
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=512)
    parser.add_argument("--iterations", type=int, default=11)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")

    raw = generate_input(args.candidates, args.seed)
    expected = evaluate_bytes(raw)
    with tempfile.TemporaryDirectory(prefix="native-proxy-") as temporary:
        build_dir = Path(temporary)
        cpp_command, cpp_metadata = _compile_cpp(build_dir)
        rust_command, rust_metadata = _compile_rust(build_dir)
        python_command = [sys.executable, str(REFERENCE)]
        python_actual = _run(python_command, raw)
        python_comparison = {
            "status": "pass" if python_actual == expected else "fail",
            "byte_equal": python_actual == expected,
            "output_sha256": hashlib.sha256(python_actual).hexdigest(),
            "output_bytes": len(python_actual),
            "timing": _time_command(python_command, raw, expected, args.iterations),
        }
        comparisons = {
            "python_reference_cli": python_comparison,
            "cpp_vs_python": _comparison(
                cpp_command, cpp_metadata, raw, expected, args.iterations
            ),
            "rust_vs_python": _comparison(
                rust_command, rust_metadata, raw, expected, args.iterations
            ),
        }

    toolchains = (("cpp", cpp_metadata), ("rust", rust_metadata))
    unavailable = [
        name for name, metadata in toolchains if metadata["status"] == "unavailable"
    ]
    toolchain_failures = [
        name for name, metadata in toolchains if metadata["status"] == "compile_failed"
    ]
    failed = [
        name
        for name, comparison in comparisons.items()
        if comparison["status"] == "fail"
    ]
    report = {
        "experiment": "native-proxy-kernel-smoke-v1",
        "scope": "synthetic feature/ranking kernel only; not official I/O and not E2/E0 accuracy evidence",
        "status": "failed"
        if failed or toolchain_failures
        else ("partial_toolchain" if unavailable else "pass"),
        "environment": {
            "os": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "workload": {
            "generator": "xorshift64-v1",
            "seed": args.seed,
            "candidates": args.candidates,
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "input_bytes": len(raw),
            "expected_output_sha256": hashlib.sha256(expected).hexdigest(),
            "expected_output_bytes": len(expected),
        },
        "toolchains": {"cpp": cpp_metadata, "rust": rust_metadata},
        "comparisons": comparisons,
        "unavailable_toolchains": unavailable,
        "failed_toolchains": toolchain_failures,
        "failed_comparisons": failed,
        "timing_note": "Warm process launches over identical stdin; includes startup, parsing, ranking, and serialization.",
    }
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8", newline="\n")
    print(serialized, end="")
    if failed or toolchain_failures or (args.require_all and unavailable):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
