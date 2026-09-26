"""Complete the 82 unmeasured P1 overload-list k5 cells with frozen E0.

The manifest fixes scope and cost. Every cell launches at most one constructor
and one independent official E0. Existing cells are never retried.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
import threading
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
SOLVER_COMMIT = "3c6e41b938c764d207de45584fb526c64f4eb845"
CODE_HASH = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
MANIFEST = ROOT / "src/local_benchmarks/s59ee_p1_overload_manifest.json"
RESULT_ROOT = ROOT / "results/a/local-q1-overload-gapfill-20260925"
MIN_AVAILABLE = 6 * 1024**3


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_sources(source, declaration):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=source, text=True)
    if head != SOLVER_COMMIT or dirty or declaration["solver_commit"] != SOLVER_COMMIT:
        raise RuntimeError("pinned solver checkout changed")
    manifest = read(ROOT / "docs/a/source-manifest.json")
    if manifest["official_code_hash"] != CODE_HASH:
        raise RuntimeError("official aggregate identity changed")
    for record in manifest["files"]:
        name = record["path"]
        if name.startswith("code/") or name == "data/config.txt" or re.fullmatch(r"data/case_\d{3}\.json", name):
            bases = (ROOT, source) if name.startswith("code/") or name == "data/config.txt" else (ROOT,)
            for base in bases:
                path = base / "data/raw/a/official" / name
                if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                    raise RuntimeError(f"frozen file mismatch: {name}")
    if declaration["cases"] != [f"{i:03d}" for i in range(1, 101) if f"{i:03d}" not in declaration["completed_elsewhere"]]:
        raise RuntimeError("manifest does not exactly cover the remaining coordinates")
    if declaration["cores"] != [5] or len(declaration["cases"]) != 82:
        raise RuntimeError("manifest scope differs from 82 k5 cells")
    if declaration["maximum_calls"] != {"solver": 82, "E0": 82, "E1": 0, "E2": 0} or declaration["retries"] != 0:
        raise RuntimeError("manifest budget changed")
    return manifest


def available_bytes():
    text = subprocess.check_output(["vm_stat"], text=True)
    page = int(re.search(r"page size of (\d+) bytes", text).group(1))
    values = {k: int(v.replace(".", "")) for k, v in re.findall(r"^(Pages (?:free|inactive|speculative|purgeable)):\s+([\d.]+)", text, re.M)}
    return page * sum(values.values())


def group_rss(pgid):
    rows = subprocess.check_output(["ps", "-A", "-o", "pgid=,rss="], text=True)
    total = 0
    for line in rows.splitlines():
        fields = line.split()
        if len(fields) == 2 and int(fields[0]) == pgid:
            total += int(fields[1]) * 1024
    return total


def run_child(argv, cwd, timeout, public_roots, source):
    started = utc()
    t0 = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen([str(x) for x in argv], cwd=cwd, start_new_session=True,
                                stdout=stdout, stderr=stderr,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
                                     "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                                     "PYTHONPATH": os.pathsep.join((str(source / "data/raw/a/official/code"), str(source)))})
        peak = 0
        status = "ok"
        cleanup_confirmed = True
        try:
            while proc.poll() is None:
                peak = max(peak, group_rss(proc.pid))
                if time.monotonic() - t0 > timeout:
                    status = "timeout"
                    os.killpg(proc.pid, signal.SIGKILL)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired as error:
                        cleanup_confirmed = False
                        raise RuntimeError("process group cleanup unconfirmed") from error
                    break
                time.sleep(.25)
            proc.wait(timeout=10)
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    cleanup_confirmed = False
            raise
        def tail(file):
            file.seek(0, 2)
            file.seek(max(0, file.tell() - 10000))
            return file.read().decode("utf-8", "replace")
        out_tail, err_tail = tail(stdout), tail(stderr)
    def scrub(s):
        for actual, label in public_roots:
            s = s.replace(str(actual), label)
        return s[-10000:]
    return {"argv": [scrub(str(x)) for x in argv], "cwd": scrub(str(cwd)),
            "started_at": started, "finished_at": utc(), "wall_seconds": time.monotonic() - t0,
            "timeout_seconds": timeout, "returncode": proc.returncode,
            "status": status if status == "timeout" else ("ok" if proc.returncode == 0 else "failed"),
            "peak_rss_bytes_sampled": peak, "cleanup_confirmed": cleanup_confirmed,
            "stdout_tail": scrub(out_tail),
            "stderr_tail": scrub(err_tail)}


def compress_lossless(path):
    original = Path(path).read_bytes()
    target = Path(str(path) + ".gz")
    with target.open("xb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0, compresslevel=1) as z:
            z.write(original)
    if gzip.decompress(target.read_bytes()) != original:
        raise RuntimeError("gzip roundtrip failed")
    Path(path).unlink()
    return {"path": target.relative_to(ROOT).as_posix(), "sha256": sha(target),
            "raw_sha256": hashlib.sha256(original).hexdigest(), "raw_bytes": len(original)}


def cell(case, cores, source, batch, deadline, stopped, limits):
    folder = batch / "cells" / case / f"k{cores}"
    folder.mkdir(parents=True, exist_ok=False)
    graph = ROOT / f"data/raw/a/official/data/case_{case}.json"
    plan = folder / f"case_{case}_multicore_res.json"
    result = folder / "result.json"
    trace = folder / "trace.json"
    log = folder / "official.log"
    diag = folder / "diagnostics.json"
    paths = [(ROOT, "<benchmark-root>"), (source, "<solver-root>")]
    record = {"case_id": case, "problem": "P1", "cores": cores, "algorithm_id": "q1-component-overload-list",
              "solver_commit": SOLVER_COMMIT, "started_at": utc(), "status": "running",
              "graph_sha256": sha(graph), "config_sha256": sha(OFFICIAL / "data/config.txt"),
              "official_code_hash": CODE_HASH, "artifacts": {}, "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}}
    write(folder / "run.json", record)
    try:
        if stopped.is_set() or time.monotonic() >= deadline:
            record.update(status="not_run", failure={"stage": "queue", "reason": "earlier failure or batch deadline"})
            return record
        if available_bytes() < MIN_AVAILABLE:
            raise RuntimeError("available memory below 6 GiB before launch")
        solver = [sys.executable, "-B", source / "src/q1/component_overload.py", graph,
                  "--cores", str(cores), "--output", plan, "--diagnostics", diag]
        record["calls"]["solver"] = 1
        record["solver"] = run_child(solver, source, min(limits["solver"], max(1, deadline - time.monotonic())), paths, source)
        if record["solver"]["status"] != "ok" or not plan.exists():
            record.update(status=record["solver"]["status"] if record["solver"]["status"] != "ok" else "failed",
                          failure={"stage": "solver", "reason": "solver did not publish plan"})
            stopped.set()
            return record
        plan_obj = read(plan)
        if set(plan_obj) != {"node_to_subgraph", "core_schedules"}:
            raise RuntimeError("plan top-level keys differ from official contract")
        record["artifacts"]["plan"] = {"path": plan.relative_to(ROOT).as_posix(), "sha256": sha(plan)}
        if diag.exists():
            record["artifacts"]["diagnostics"] = {"path": diag.relative_to(ROOT).as_posix(), "sha256": sha(diag)}
        if time.monotonic() >= deadline:
            record.update(status="timeout", failure={"stage": "evaluation", "reason": "batch deadline before E0"})
            stopped.set()
            return record
        official = [sys.executable, "-B", OFFICIAL / "code/multicore_cut_evaluate_problem_1.py", graph,
                    plan, "--config", OFFICIAL / "data/config.txt", "--output", result,
                    "--trace-output", trace, "--log-output", log]
        record["calls"]["E0"] = 1
        record["evaluation"] = run_child(official, ROOT, min(limits["E0"], max(1, deadline - time.monotonic())), paths, source)
        if record["evaluation"]["status"] != "ok" or not result.exists():
            record.update(status=record["evaluation"]["status"] if record["evaluation"]["status"] != "ok" else "failed",
                          failure={"stage": "E0", "reason": "official CLI did not publish result"})
            stopped.set()
            return record
        full = read(result)
        if full.get("scene") != "A" or full.get("num_cores") != cores or not isinstance(full.get("makespan"), (int, float)):
            raise RuntimeError("official result identity invalid")
        record["makespan_cycles"] = full["makespan"]
        record["data_movement_bytes"] = full.get("data_movement_bytes")
        record["artifacts"]["result"] = compress_lossless(result)
        if trace.exists():
            record["artifacts"]["trace"] = compress_lossless(trace)
        if log.exists():
            record["artifacts"]["log"] = {"path": log.relative_to(ROOT).as_posix(), "sha256": sha(log)}
        record["status"] = "ok"
        return record
    except Exception as error:
        record.update(status="failed", failure={"stage": "controller", "reason": f"{type(error).__name__}: {error}"})
        stopped.set()
        return record
    finally:
        record["finished_at"] = utc()
        write(folder / "run.json", record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true", help="verify fixed bytes and scope without running")
    args = parser.parse_args()
    source, batch = args.source.resolve(), args.batch.resolve()
    if not batch.is_relative_to(RESULT_ROOT):
        parser.error("batch must be in this session's results directory")
    declaration = read(MANIFEST)
    manifest = verify_sources(source, declaration)
    availability = available_bytes()
    if availability < MIN_AVAILABLE:
        raise RuntimeError(f"available memory below 6 GiB: {availability}")
    runner_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "show", f"{runner_commit}:src/local_benchmarks/s59ee_p1_overload_gapfill.py"], cwd=ROOT) != Path(__file__).read_bytes():
        raise RuntimeError("runner bytes differ from fixed commit")
    if subprocess.check_output(["git", "show", f"{runner_commit}:src/local_benchmarks/s59ee_p1_overload_manifest.json"], cwd=ROOT) != MANIFEST.read_bytes():
        raise RuntimeError("manifest bytes differ from fixed commit")
    jobs = [(c, 5) for c in declaration["cases"]]
    if args.preflight:
        print(json.dumps({"valid": True, "cells": len(jobs), "solver_commit": SOLVER_COMMIT,
                          "runner_commit": runner_commit, "manifest_sha256": sha(MANIFEST),
                          "official_code_hash": manifest["official_code_hash"],
                          "available_bytes": availability, "batch_created": False}))
        return 0
    batch.mkdir(parents=True, exist_ok=False)
    meta_path = batch / "batch.json"
    limits = declaration["timeouts_seconds"]
    meta = {"schema": declaration["schema"], "batch_id": batch.name,
            "started_at": utc(), "finished_at": None, "solver_commit": SOLVER_COMMIT,
            "solver_entrypoint": declaration["solver_entrypoint"], "runner_commit": runner_commit,
            "runner_path": "src/local_benchmarks/s59ee_p1_overload_gapfill.py",
            "runner_sha256": sha(__file__), "manifest_sha256": sha(MANIFEST),
            "manifest": declaration, "official_code_hash": CODE_HASH,
            "official_manifest_sha256": sha(ROOT / "docs/a/source-manifest.json"),
            "config_sha256": sha(OFFICIAL / "data/config.txt"), "python": sys.version,
            "environment": {"os": platform.platform(),
                            "cpu": subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip(),
                            "ram_bytes": int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()),
                            "threads_configured": 1},
            "workers_history": [], "invocations": [], "resource_preflight_available_bytes": availability,
            "deadline_seconds": limits["batch"], "stop_policy": declaration["stop_policy"]}
    write(meta_path, meta)
    deadline = time.monotonic() + limits["batch"]
    stopped = threading.Event()
    results = []
    for phase_jobs, workers in ((jobs[:4], 2), (jobs[4:], declaration["workers"])):
        if not phase_jobs:
            continue
        invocation = {"utc": utc(), "cases": [c for c, _ in phase_jobs], "cores": [5],
                      "workers": workers, "status": "running", "available_bytes": available_bytes()}
        meta["invocations"].append(invocation)
        meta["workers_history"].append({"utc": invocation["utc"], "workers": workers,
                                         "available_bytes": invocation["available_bytes"]})
        write(meta_path, meta)
        if stopped.is_set():
            for c, k in phase_jobs:
                results.append(cell(c, k, source, batch, deadline, stopped, limits))
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(cell, c, k, source, batch, deadline, stopped, limits): (c, k)
                           for c, k in phase_jobs}
                for future in as_completed(futures):
                    item = future.result()
                    results.append(item)
                    print(json.dumps({"case": item["case_id"], "cores": item["cores"],
                                      "status": item["status"], "makespan": item.get("makespan_cycles")}), flush=True)
        invocation.update(status="complete", finished_at=utc(), counts={s: sum(x["status"] == s for x in results)
                                                                       for s in sorted({x["status"] for x in results})})
        write(meta_path, meta)
    meta.update(finished_at=utc(), status="complete" if all(x["status"] == "ok" for x in results) else "stopped",
                counts={s: sum(x["status"] == s for x in results) for s in sorted({x["status"] for x in results})},
                actual_calls={k: sum(x["calls"][k] for x in results) for k in ("solver", "E0", "E1", "E2")})
    write(meta_path, meta)
    return 0 if all(x["status"] == "ok" for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
