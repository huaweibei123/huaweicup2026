"""Build and attest the pinned E2 P2/P3 native library on Linux x86_64.

This tool never evaluates a plan. Keep its output manifest outside the source
capsule so the solver's exact-file-set guard can remain strict.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import sysconfig


E2_COMMIT = "603b0741e21c449d3db652ebd67c94f2dc014cc9"
# Exact bytes of results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json
# at ee4fe0282ca2ff5d73bb23d54b1c213909e1401c.
SOURCE_MANIFEST_SHA256 = "9ee379269c0c4f25b64f9d0aeaf1e397e85e48c2103b08637db356d3c9595387"
LIBRARY = Path("research/a/e2_search/native/libreplay_bc.so")
SOURCE = Path("research/a/e2_search/native/replay_bc.cpp")
FLAGS = ["-std=c++17", "-O3", "-shared", "-fno-fast-math",
         "-ffp-contract=off", "-Wall", "-Wextra", "-fPIC"]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def require_linux() -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise RuntimeError("this build is restricted to Linux x86_64")
    if sys.byteorder != "little" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("requires little-endian 64-bit Python")


def checked_sources(root: Path, source_manifest: Path) -> dict:
    if sha(source_manifest) != SOURCE_MANIFEST_SHA256:
        raise RuntimeError("source manifest differs from fixed P2 manifest")
    doc = json.loads(source_manifest.read_text())
    if doc.get("e2_commit") != E2_COMMIT:
        raise RuntimeError("E2 commit mismatch")
    entries = doc["e2_sources"]
    if entries.get(SOURCE.as_posix()) != "b3990fa45246c64e3f2e633ed9c0c99899cab57fae24d55e5287ac0dc25baf1d":
        raise RuntimeError("native source pin mismatch")
    for name, digest in entries.items():
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or not (root / rel).is_file():
            raise RuntimeError("missing or unsafe source: " + name)
        if sha(root / rel) != digest:
            raise RuntimeError("source drift: " + name)
    return entries


def checked_binary(binary: Path) -> dict:
    raw = binary.read_bytes()
    if len(raw) < 64 or raw[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", raw, 18)[0] != 62:
        raise RuntimeError("library is not a little-endian ELF64 x86_64 binary")
    lib = ctypes.CDLL(str(binary))
    abi = lib.replay_bc_abi
    abi.argtypes, abi.restype = [], ctypes.c_int
    if abi() != 1 or not hasattr(lib, "replay_bc"):
        raise RuntimeError("native replay_bc ABI/symbol mismatch")
    return {"path": LIBRARY.as_posix(), "sha256": sha(binary), "bytes": len(raw),
            "format": "ELF64 little-endian x86_64", "replay_bc_abi": 1}


def command_output(args: list[str]) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def machine_info() -> dict:
    return {"platform": platform.platform(), "machine": platform.machine(),
            "libc": platform.libc_ver(), "python": sys.version,
            "python_abi": sysconfig.get_config_var("SOABI"),
            "pointer_bytes": ctypes.sizeof(ctypes.c_void_p), "byteorder": sys.byteorder}


def binding_info(root: Path) -> dict:
    """Load the Python ctypes binding and the ABI symbol, without scoring."""
    code = (
        "import ctypes,json,numpy; from research.a.e2_search import _native_b as n; "
        "assert ctypes.sizeof(n.InputB)==160 and ctypes.sizeof(n.OutputB)==64; "
        "assert n.get_lib().replay_bc_abi()==1; "
        "print(json.dumps({'numpy':numpy.__version__,'input_bytes':ctypes.sizeof(n.InputB),"
        "'output_bytes':ctypes.sizeof(n.OutputB),"
        "'input_offsets':{k:getattr(n.InputB,k).offset for k,_ in n.InputB._fields_},"
        "'output_offsets':{k:getattr(n.OutputB,k).offset for k,_ in n.OutputB._fields_}}))"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=root,
                            env=env, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--root", type=Path, required=True, help="fixed E2 source capsule root")
    parser.add_argument("--source-manifest", type=Path, required=True,
                        help="fixed P2 manifest.json from commit ee4fe028")
    parser.add_argument("--out", type=Path, required=True,
                        help="Linux build manifest outside the source capsule")
    parser.add_argument("--compiler", help="absolute C++ compiler path; required for build")
    args = parser.parse_args()
    require_linux()
    root = args.root.resolve(strict=True)
    source_manifest = args.source_manifest.resolve(strict=True)
    out = args.out.resolve()  # must remain outside root's exact source-file set
    if out == root or root in out.parents:
        raise RuntimeError("write the build manifest outside the source capsule")
    sources = checked_sources(root, source_manifest)
    binary = root / LIBRARY

    if args.action == "build":
        if binary.exists() or out.exists():
            raise RuntimeError("refusing to overwrite an existing binary or manifest")
        if not args.compiler or not Path(args.compiler).is_absolute():
            raise RuntimeError("--compiler must be an absolute path")
        compiler = Path(args.compiler).resolve(strict=True)
        if not os.access(compiler, os.X_OK):
            raise RuntimeError("compiler is not executable")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run(
            [sys.executable, "-B", "-m", "research.a.e2_search.build_native",
             "--problem", "3", "--compiler", str(compiler)],
            cwd=root, env=env, text=True, capture_output=True, check=True)
        build_receipt = json.loads(process.stdout)
        if build_receipt["source_sha256"] != sources[SOURCE.as_posix()]:
            raise RuntimeError("build receipt source hash mismatch")
        actual_command = build_receipt["command"]
        if actual_command[1:1 + len(FLAGS)] != FLAGS:
            raise RuntimeError("build flags drift")
        info = checked_binary(binary)
        if build_receipt["binary_sha256"] != info["sha256"]:
            raise RuntimeError("build receipt binary hash mismatch")
        receipt = {"schema": "e2-linux-native-v1", "e2_commit": E2_COMMIT,
                   "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
                   "source_sha256": sources, "binary": info,
                   "build_utc": datetime.now(timezone.utc).isoformat(),
                   "build_receipt": build_receipt,
                   "compiler": {"path": str(compiler), "sha256": sha(compiler),
                                "version": command_output([str(compiler), "--version"]),
                                "target": command_output([str(compiler), "-dumpmachine"])},
                   "runtime": machine_info(), "bindings": binding_info(root),
                   "dynamic_dependencies": command_output(["ldd", str(binary)])}
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_name(out.name + ".tmp")
        temp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        temp.replace(out)
    else:
        receipt = json.loads(out.read_text())
        if receipt.get("schema") != "e2-linux-native-v1" or receipt.get("e2_commit") != E2_COMMIT:
            raise RuntimeError("Linux build manifest identity mismatch")
        if receipt.get("source_manifest_sha256") != SOURCE_MANIFEST_SHA256 or receipt.get("source_sha256") != sources:
            raise RuntimeError("Linux build source identity mismatch")
        if receipt.get("binary") != checked_binary(binary):
            raise RuntimeError("Linux binary identity/ABI mismatch")
        if receipt.get("bindings") != binding_info(root):
            raise RuntimeError("Linux Python binding layout/dependency mismatch")
    print(json.dumps({"status": "ok", "e2_commit": E2_COMMIT,
                      "binary_sha256": receipt["binary"]["sha256"],
                      "manifest_sha256": sha(out)}, sort_keys=True))


if __name__ == "__main__":
    main()
