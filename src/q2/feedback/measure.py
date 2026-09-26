"""Run a frozen, single-worker P2 development comparison; never resume or retry.

The spec and a durable budget reservation are saved before subprocess dispatch.
This file uses only the standard library; E0 remains the unmodified official CLI.
"""
from __future__ import annotations

import argparse
import ctypes
import gzip
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OFFICIAL = "data/raw/a/official/"
EVALUATOR = OFFICIAL + "code/multicore_cut_evaluate_problem_2.py"
RUNNER = "src/q2/feedback/measure.py"
SOLVER = "src/q2/feedback/construct.py"
RESULT_PREFIX = "results/a/q2-yuanzhifang/feedback-20260924/"
REPO = "huaweibei123/huaweicup2026"


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def save_json(path, value, *, replace=False):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not replace:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def repo_path(name):
    if not isinstance(name, str) or "\\" in name or ":" in name or ".." in Path(name).parts:
        raise ValueError(f"not a repository-relative path: {name!r}")
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("path escapes repository")
    return path


def artifact(path):
    return {"path": relative(path), "sha256": digest(path.read_bytes())}


def git_bytes(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)


def verify_code(commit, paths):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("code commits must be full lowercase SHA1 values")
    hashes = {}
    for name in paths:
        raw = repo_path(name).read_bytes()
        if raw != git_bytes("show", f"{commit}:{name}"):
            raise ValueError(f"working bytes differ from frozen {commit}: {name}")
        hashes[name] = digest(raw)
    return hashes


def validate_spec(spec):
    required = {"run_id", "producer_session", "task_url", "source_url", "runtime_id",
                "solver_commit", "runner_commit", "evaluator_commit", "cases", "methods",
                "cores", "output", "budget", "source_paths", "offline_costs"}
    if required - spec.keys():
        raise ValueError(f"missing spec fields: {sorted(required - spec.keys())}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}", spec["run_id"]):
        raise ValueError("run_id must be a short lowercase slug")
    if not spec["output"].startswith(RESULT_PREFIX):
        raise ValueError("output is outside this task's assigned result directory")
    repo_path(spec["output"])
    cases = spec["cases"]
    if not cases or len(set(cases)) != len(cases) or any(not re.fullmatch(r"(?:00[1-9]|0[1-9][0-9]|100)", c) for c in cases):
        raise ValueError("cases must be a unique nonempty ordered list of 001..100")
    if type(spec["cores"]) is not int or not 1 <= spec["cores"] <= 5:
        raise ValueError("cores must be 1..5")
    methods = spec["methods"]
    if not methods or len({m["variant"] for m in methods}) != len(methods):
        raise ValueError("methods must have unique variants")
    for method in methods:
        for key in ("variant", "algorithm_id", "algorithm_name", "description", "args", "references", "upstream"):
            if key not in method:
                raise ValueError(f"method requires {key}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", method["variant"]):
            raise ValueError("invalid method variant")
        if not all(isinstance(arg, str) for arg in method["args"]):
            raise ValueError("method args must be strings")
        if any(arg.split("=", 1)[0] in {"--graph", "--config", "--cores", "--method", "--strategy", "--output", "-o"} for arg in method["args"]):
            raise ValueError("method args cannot override frozen input/output/method")
    budget = spec["budget"]
    for key in ("batch_wall_seconds", "solver_timeout_seconds", "e0_timeout_seconds"):
        if type(budget.get(key)) not in (int, float) or not math.isfinite(budget[key]) or budget[key] <= 0:
            raise ValueError(f"budget.{key} must be finite and positive")
    if type(budget.get("max_e0_calls")) is not int or budget["max_e0_calls"] < len(cases) * len(methods):
        raise ValueError("max_e0_calls must cover the declared fixed comparison")
    if budget.get("workers") != 1 or budget.get("stop_on_first_failure") is not True:
        raise ValueError("this runner requires one worker and first-failure stop")
    if type(budget.get("cleanup_reserve_seconds")) not in (int, float) or not 0 < budget["cleanup_reserve_seconds"] < budget["batch_wall_seconds"]:
        raise ValueError("a positive cleanup reserve below the batch wall is required")
    if not isinstance(spec["offline_costs"], str) or not spec["offline_costs"]:
        raise ValueError("offline_costs needs an explicit statement")


def frozen_inputs(spec):
    manifest = read_json(ROOT / "docs/a/source-manifest.json")
    files = {item["path"]: item["sha256"] for item in manifest["files"]}
    source_names = sorted(name for name in files if name.startswith("code/"))
    code_text = "".join(f"{name}\t{files[name]}\n" for name in source_names).encode()
    if digest(code_text) != manifest["official_code_hash"]:
        raise ValueError("official manifest aggregate hash mismatch")
    needed = source_names + ["data/config.txt"] + [f"data/case_{case}.json" for case in spec["cases"]]
    for name in needed:
        if digest((ROOT / OFFICIAL / name).read_bytes()) != files[name]:
            raise ValueError(f"frozen official bytes mismatch: {name}")
    source_hashes = verify_code(spec["solver_commit"], spec["source_paths"])
    if SOLVER not in source_hashes:
        raise ValueError("source_paths must include the solver entrypoint and all local imports")
    source_hashes.update(verify_code(spec["runner_commit"], [RUNNER]))
    source_hashes.update(verify_code(spec["evaluator_commit"], [OFFICIAL + name for name in source_names]))
    return manifest, files, source_hashes


def environment():
    cpu, ram = platform.processor() or None, None
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                        ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                        ("avail_extended", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            ram = status.total_phys
    else:
        try:
            ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError, AttributeError):
            pass
    return {"os": platform.platform(), "cpu": cpu, "gpu": "none used (CPU-only solver and E0)",
            "ram_bytes": ram, "python": platform.python_version(),
            "dependencies": "standard library execution; uv.lock SHA256=" + digest((ROOT / "uv.lock").read_bytes()),
            "threads": 1, "workers": 1, "peak_rss_bytes": None}


def run_process(argv, timeout, directory, stage, ledger, ledger_path, run, run_path):
    """Reserve first, then record Popen success before waiting; ambiguous crashes stay charged."""
    reservation = {"attempt_id": run["attempt_id"], "stage": stage, "reserved_at": utc(),
                   "reserved_wall_seconds": timeout, "state": "reserved", "argv": argv}
    ledger["reservations"].append(reservation)
    ledger["charged_calls"][stage] += 1
    run["calls"][stage] += 1
    save_json(ledger_path, ledger, replace=True)
    save_json(run_path, run, replace=True)
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    started = time.perf_counter()
    record = {"argv": argv, "started_at": utc(), "timeout_seconds": timeout, "launched": False,
              "returncode": None, "status": "running", "failure_reason": None}
    with (directory / f"{stage}.stdout.txt").open("xb") as stdout, (directory / f"{stage}.stderr.txt").open("xb") as stderr:
        process = None
        try:
            process = subprocess.Popen([sys.executable, *argv[1:]], cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
            record["launched"] = True
            reservation["state"] = "launched"
            reservation["pid"] = process.pid
            save_json(ledger_path, ledger, replace=True)
            remaining = timeout - (time.perf_counter() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout)
            record["returncode"] = process.wait(timeout=remaining)
            record["status"] = "ok" if record["returncode"] == 0 else "failed"
            if record["status"] != "ok":
                record["failure_reason"] = f"process exited {record['returncode']}; see stderr log"
        except subprocess.TimeoutExpired:
            if process is not None:
                process.kill()
                record["returncode"] = process.wait()
            record["status"] = "timeout"
            record["failure_reason"] = "fixed wall-clock timeout; process killed; no retry"
        except BaseException as error:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            record["status"] = "failed"
            record["failure_reason"] = type(error).__name__ + ": " + str(error)
            if not record["launched"]:
                ledger["charged_calls"][stage] -= 1
                run["calls"][stage] -= 1
        record["wall_seconds"] = time.perf_counter() - started
        record["finished_at"] = utc()
    reservation.update(state=record["status"], launched=record["launched"], actual_wall_seconds=record["wall_seconds"])
    run["stages"][stage] = record
    save_json(ledger_path, ledger, replace=True)
    save_json(run_path, run, replace=True)
    return record


def preserve_outputs(directory):
    """Compress full original bytes deterministically; preserve raw hash and size."""
    compressed = {}
    for name in ("result.json", "trace.json"):
        path = directory / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        packed = gzip.compress(raw, mtime=0)
        if gzip.decompress(packed) != raw:
            raise ValueError("lossless compression check failed")
        target = path.with_suffix(path.suffix + ".gz")
        with target.open("xb") as stream:
            stream.write(packed)
        compressed[name] = {"raw_sha256": digest(raw), "raw_bytes": len(raw),
                            "stored_bytes": len(packed), "artifact": artifact(target), "transformation": "gzip lossless; mtime=0"}
        path.unlink()  # The byte-identical, verified gzip is the retained original.
    return compressed


def run_batch(spec, spec_path):
    preparation_start = time.perf_counter()
    preparation_started_at = utc()
    validate_spec(spec)
    manifest, files, source_hashes = frozen_inputs(spec)
    preparation_wall_seconds = time.perf_counter() - preparation_start
    out = repo_path(spec["output"])
    out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    batch_started_at = utc()
    env = environment()
    save_json(out / "spec.json", spec)
    ledger = {"version": 1, "run_id": spec["run_id"], "spec_sha256": digest(spec_path.read_bytes()),
              "started_at": batch_started_at, "finished_at": None, "state": "running", "stop_reason": None,
              "budget": spec["budget"], "charged_calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
              "reservations": [], "attempts": [], "source_hashes": source_hashes,
              "preparation": {"started_at": preparation_started_at, "wall_seconds": preparation_wall_seconds,
                              "scope": "one-off spec, Git source and frozen official hash preflight; before batch budget T0; no graph algorithm/solver/evaluator calls"},
              "environment": env, "costs": {"cloud_jobs": 0, "paid_compute_jobs": 0, "github_actions": 0,
                                             "offline": spec["offline_costs"]},
              "runner_argv": ["python", "-X", "utf8", "-B", "-m", "src.q2.feedback.measure", "--spec", relative(spec_path)]}
    ledger_path = out / "ledger.json"
    save_json(ledger_path, ledger)
    budget = spec["budget"]
    try:
        for case in spec["cases"]:
            for method in spec["methods"]:
                elapsed = time.perf_counter() - start
                reserve = budget["solver_timeout_seconds"] + budget["e0_timeout_seconds"] + budget["cleanup_reserve_seconds"]
                if elapsed + reserve > budget["batch_wall_seconds"]:
                    ledger["stop_reason"] = "batch wall remaining is insufficient to reserve a complete unit"
                    return ledger
                if ledger["charged_calls"]["E0"] >= budget["max_e0_calls"]:
                    ledger["stop_reason"] = "E0 call cap reached"
                    return ledger
                # Refuse a concurrent code mutation before any further dispatched work.
                for path, expected in source_hashes.items():
                    if digest(repo_path(path).read_bytes()) != expected:
                        raise ValueError("as-run source changed during batch: " + path)
                graph = OFFICIAL + f"data/case_{case}.json"
                config = OFFICIAL + "data/config.txt"
                for name in (graph, config):
                    if digest(repo_path(name).read_bytes()) != files[name.removeprefix(OFFICIAL)]:
                        raise ValueError("frozen input changed during batch: " + name)
                attempt = f"{spec['run_id']}-{method['variant']}-p2-{case}-k{spec['cores']}-seed0-repeat0"
                directory = out / (case + "-" + method["variant"])
                directory.mkdir()
                plan = directory / f"case_{case}_multicore_res.json"
                run_path = directory / "run.json"
                run = {"version": 1, "attempt_id": attempt, "run_id": spec["run_id"] + "-" + method["variant"],
                       "case_id": case, "problem": "P2", "cores": spec["cores"], "method": method,
                       "started_at": utc(), "finished_at": None, "status": "running", "failure": None,
                       "solver_commit": spec["solver_commit"], "runner_commit": spec["runner_commit"],
                       "evaluator_commit": spec["evaluator_commit"], "identity": {
                           "graph_sha256": files[f"data/case_{case}.json"], "config_sha256": files["data/config.txt"],
                           "official_sha256": manifest["official_code_hash"], "plan_sha256": None},
                       "source_hashes": source_hashes, "environment": env,
                       "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, "stages": {}, "artifacts": {}}
                save_json(run_path, run)
                ledger["attempts"].append(relative(run_path))
                save_json(ledger_path, ledger, replace=True)
                argv = ["python", "-X", "utf8", "-B", "-m", "src.q2.feedback.construct", graph,
                        "--cores", str(spec["cores"]), "--strategy", method["variant"],
                        "--output", relative(plan), *method["args"]]
                stage = run_process(argv, budget["solver_timeout_seconds"], directory, "solver", ledger, ledger_path, run, run_path)
                if stage["returncode"] == 2 and case in method.get("expected_unsupported_cases", []):
                    try:
                        message = json.loads((directory / "solver.stdout.txt").read_text(encoding="utf-8"))
                        if message["status"] == "unsupported" and isinstance(message["reason"], str):
                            stage = {**stage, "status": "unsupported", "failure_reason": message["reason"]}
                            run["stages"]["solver"]["semantic_status"] = "unsupported"
                    except (ValueError, KeyError, TypeError):
                        pass
                if stage["status"] == "ok":
                    try:
                        payload = read_json(plan)
                        if set(payload) != {"node_to_subgraph", "core_schedules"}:
                            raise ValueError("plan must contain exactly the two official fields")
                        run["identity"]["plan_sha256"] = digest(plan.read_bytes())
                        run["artifacts"]["plan"] = artifact(plan)
                    except (ValueError, OSError, TypeError) as error:
                        stage = {**stage, "status": "failed", "failure_reason": "plan validation: " + str(error)}
                if stage["status"] == "ok":
                    argv = ["python", "-X", "utf8", "-B", EVALUATOR, graph, relative(plan), "--config", config,
                            "--output", relative(directory / "result.json"),
                            "--trace-output", relative(directory / "trace.json"),
                            "--log-output", relative(directory / "result.txt")]
                    stage = run_process(argv, budget["e0_timeout_seconds"], directory, "E0", ledger, ledger_path, run, run_path)
                    if stage["status"] == "ok":
                        try:
                            result = read_json(directory / "result.json")
                            if result["scene"] != "B" or result["num_cores"] != spec["cores"]:
                                raise ValueError("official result scene/cores mismatch")
                            if type(result["makespan"]) not in (int, float) or not math.isfinite(result["makespan"]) or result["makespan"] <= 0:
                                raise ValueError("invalid makespan")
                            if result["input_graph"] != Path(graph).name or result["input_plan"] != plan.name:
                                raise ValueError("official result input names mismatch")
                            run["metrics"] = {"makespan_cycles": result["makespan"],
                                              "data_movement_bytes": result["data_movement_bytes"]}
                        except (ValueError, OSError, KeyError, TypeError) as error:
                            stage = {**stage, "status": "failed", "failure_reason": "result validation: " + str(error)}
                run["status"] = stage["status"]
                if stage["status"] != "ok":
                    run["failure"] = {"stage": "E0" if "E0" in run["stages"] else "solver",
                                      "reason": stage["failure_reason"], "exit_code": stage["returncode"],
                                      "elapsed_seconds": stage["wall_seconds"]}
                run["compression"] = preserve_outputs(directory)
                for key, name in (("result", "result.json.gz"), ("trace", "trace.json.gz"), ("log", "result.txt")):
                    if (directory / name).exists():
                        run["artifacts"][key] = artifact(directory / name)
                run["finished_at"] = utc()
                run["stop_reason"] = {"ok": "fixed direct construction and one external E0 completed",
                                      "unsupported": "predeclared unsupported structure; zero E0; continue next fixed unit"}.get(
                                          run["status"], "first unexpected failure; batch stopped without retry")
                save_json(run_path, run, replace=True)
                print(json.dumps({"case": case, "method": method["variant"], "status": run["status"],
                                  "makespan": run.get("metrics", {}).get("makespan_cycles"),
                                  "solver_wall_seconds": run["stages"]["solver"]["wall_seconds"],
                                  "E0_wall_seconds": run["stages"].get("E0", {}).get("wall_seconds")}), flush=True)
                if run["status"] not in ("ok", "unsupported"):
                    ledger["stop_reason"] = run["stop_reason"]
                    return ledger
        ledger["stop_reason"] = "all declared comparison units completed"
        ledger["state"] = "completed"
        return ledger
    except BaseException as error:
        ledger["stop_reason"] = "runner exception; no retry: " + type(error).__name__ + ": " + str(error)
        raise
    finally:
        if ledger["state"] != "completed":
            ledger["state"] = "stopped"
        ledger["finished_at"] = utc()
        ledger["batch_wall_seconds"] = time.perf_counter() - start
        save_json(ledger_path, ledger, replace=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true", help="validate spec, commits and frozen hashes; no solver/E0 calls")
    args = parser.parse_args()
    spec_path = args.spec.resolve()
    spec = read_json(spec_path)
    validate_spec(spec)
    if args.check_only:
        _, _, hashes = frozen_inputs(spec)
        print(json.dumps({"valid": True, "units": len(spec["cases"]) * len(spec["methods"]),
                          "verified_source_files": len(hashes), "solver_calls": 0, "E0_calls": 0}))
        return 0
    ledger = run_batch(spec, spec_path)
    return 0 if ledger["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
