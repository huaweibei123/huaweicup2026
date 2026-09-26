"""Bounded, concurrent P1 fixed64 k=1..5 benchmark of a pinned constructor.

Every cell launches one solver and, if a plan exists, one frozen official CLI.
Existing cells are never retried.  The controller does not select plans.
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
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
SOLVER_COMMIT = "4dff90ef699fd51845cf482951e8477066f5f566"
CODE_HASH = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
MIN_AVAILABLE = 8 * 1024**3
MAX_RSS = 24 * 1024**3


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


def verify_sources(source):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=source, text=True)
    if head != SOLVER_COMMIT or dirty:
        raise RuntimeError("pinned solver checkout changed")
    manifest = read(ROOT / "docs/a/source-manifest.json")
    if manifest["official_code_hash"] != CODE_HASH:
        raise RuntimeError("official aggregate identity changed")
    for record in manifest["files"]:
        name = record["path"]
        if name.startswith("code/") or name == "data/config.txt" or re.fullmatch(r"data/case_\d{3}\.json", name):
            for base in (ROOT, source):
                path = base / "data/raw/a/official" / name
                if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                    raise RuntimeError(f"frozen file mismatch: {name}")
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


def run_child(argv, cwd, timeout, public_roots):
    started = utc()
    t0 = time.monotonic()
    proc = subprocess.Popen([str(x) for x in argv], cwd=cwd, start_new_session=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
                                 "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
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
        stdout, stderr = proc.communicate(timeout=10)
    except BaseException:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cleanup_confirmed = False
        raise
    def scrub(s):
        for actual, label in public_roots:
            s = s.replace(str(actual), label)
        return s[-10000:]
    return {"argv": [scrub(str(x)) for x in argv], "cwd": scrub(str(cwd)),
            "started_at": started, "finished_at": utc(), "wall_seconds": time.monotonic() - t0,
            "timeout_seconds": timeout, "returncode": proc.returncode,
            "status": status if status == "timeout" else ("ok" if proc.returncode == 0 else "failed"),
            "peak_rss_bytes_sampled": peak, "cleanup_confirmed": cleanup_confirmed,
            "stdout_tail": scrub(stdout.decode("utf-8", "replace")),
            "stderr_tail": scrub(stderr.decode("utf-8", "replace"))}


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


def cell(case, cores, source, batch, deadline):
    folder = batch / "cells" / case / f"k{cores}"
    folder.mkdir(parents=True, exist_ok=False)
    graph = source / f"data/raw/a/official/data/case_{case}.json"
    plan = folder / f"case_{case}_multicore_res.json"
    result = folder / "result.json"
    trace = folder / "trace.json"
    log = folder / "official.log"
    paths = [(ROOT, "<benchmark-root>"), (source, "<solver-root>")]
    record = {"case_id": case, "problem": "P1", "cores": cores, "algorithm_id": "q1-fixed64-local-finish",
              "solver_commit": SOLVER_COMMIT, "started_at": utc(), "status": "running",
              "graph_sha256": sha(graph), "config_sha256": sha(OFFICIAL / "data/config.txt"),
              "official_code_hash": CODE_HASH, "artifacts": {}, "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}}
    write(folder / "run.json", record)
    try:
        if time.monotonic() >= deadline:
            record.update(status="not_run", failure={"stage": "queue", "reason": "batch deadline"})
            return record
        solver = [sys.executable, "-B", source / "src/q1/search.py", "propose", graph, plan, "--kind", "fixed64", "--cores", str(cores), "--seed", "0"]
        record["calls"]["solver"] = 1
        record["solver"] = run_child(solver, source, min(120, max(1, deadline - time.monotonic())), paths)
        if record["solver"]["status"] != "ok" or not plan.exists():
            record.update(status=record["solver"]["status"], failure={"stage": "solver", "reason": "solver did not publish plan"})
            return record
        plan_obj = read(plan)
        if set(plan_obj) != {"node_to_subgraph", "core_schedules"}:
            raise RuntimeError("plan top-level keys differ from official contract")
        record["artifacts"]["plan"] = {"path": plan.relative_to(ROOT).as_posix(), "sha256": sha(plan)}
        if time.monotonic() >= deadline:
            record.update(status="not_run", failure={"stage": "evaluation", "reason": "batch deadline"})
            return record
        official = [sys.executable, "-B", OFFICIAL / "code/multicore_cut_evaluate_problem_1.py", graph,
                    plan, "--config", OFFICIAL / "data/config.txt", "--output", result,
                    "--trace-output", trace, "--log-output", log]
        record["calls"]["E0"] = 1
        record["evaluation"] = run_child(official, ROOT, min(180, max(1, deadline - time.monotonic())), paths)
        if record["evaluation"]["status"] != "ok" or not result.exists():
            record.update(status=record["evaluation"]["status"], failure={"stage": "E0", "reason": "official CLI did not publish result"})
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
        return record
    finally:
        record["finished_at"] = utc()
        write(folder / "run.json", record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--cases", required=True, help="comma-separated 001..100")
    parser.add_argument("--cores", default="1,2,3,4,5")
    parser.add_argument("--workers", type=int, required=True)
    args = parser.parse_args()
    if args.workers not in (1, 2, 4, 8):
        parser.error("workers must be 1, 2, 4, or 8")
    cases = args.cases.split(",")
    cores = [int(x) for x in args.cores.split(",")]
    if len(set(cores)) != len(cores) or any(k not in (1, 2, 3, 4, 5) for k in cores):
        parser.error("cores must be unique 1..5")
    if len(set(cases)) != len(cases) or any(c not in {f"{i:03d}" for i in range(1, 101)} for c in cases):
        parser.error("cases must be unique 001..100")
    source, batch = args.source.resolve(), args.batch.resolve()
    if not batch.is_relative_to(ROOT / "results/a/local-p1-fixed64-20260924"):
        parser.error("batch must be in this session's results directory")
    manifest = verify_sources(source)
    batch.mkdir(parents=True, exist_ok=True)
    meta_path = batch / "batch.json"
    if meta_path.exists():
        meta = read(meta_path)
        if meta["solver_commit"] != SOLVER_COMMIT or meta["official_code_hash"] != CODE_HASH:
            raise RuntimeError("batch identity mismatch")
    else:
        meta = {"schema": "local-p1-fixed64-v1", "batch_id": batch.name, "started_at": utc(),
                "started_monotonic_note": "deadline is 120 minutes from first invocation start; no restart extension",
                "solver_commit": SOLVER_COMMIT, "solver_entrypoint": "src/q1/search.py propose --kind fixed64",
                "official_code_hash": CODE_HASH, "official_manifest_sha256": sha(ROOT / "docs/a/source-manifest.json"),
                "config_sha256": sha(OFFICIAL / "data/config.txt"), "runner_sha256": sha(__file__),
                "python": sys.version, "workers_history": [], "invocations": [], "deadline_utc": None}
    from datetime import timedelta
    start = datetime.fromisoformat(meta["started_at"].replace("Z", "+00:00"))
    deadline_utc = start + timedelta(hours=2)
    meta["deadline_utc"] = deadline_utc.isoformat().replace("+00:00", "Z")
    deadline = time.monotonic() + (deadline_utc - datetime.now(timezone.utc)).total_seconds()
    if time.monotonic() >= deadline:
        raise RuntimeError("batch deadline has passed")
    jobs = [(c, k) for c in cases for k in cores]
    existing = [(c, k) for c, k in jobs if (batch / "cells" / c / f"k{k}").exists()]
    if existing:
        raise RuntimeError(f"existing cells are never retried: {existing}")
    availability = available_bytes()
    if availability < MIN_AVAILABLE:
        raise RuntimeError(f"available memory below 8 GiB: {availability}")
    meta["workers_history"].append({"utc": utc(), "workers": args.workers, "available_bytes": availability})
    invocation = {"utc": utc(), "cases": cases, "cores": cores, "workers": args.workers, "status": "running"}
    meta["invocations"].append(invocation)
    write(meta_path, meta)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(cell, c, k, source, batch, deadline): (c, k) for c, k in jobs}
        for future in as_completed(futures):
            item = future.result()
            results.append(item)
            print(json.dumps({"case": item["case_id"], "cores": item["cores"], "status": item["status"], "makespan": item.get("makespan_cycles")}), flush=True)
    invocation.update(status="complete", finished_at=utc(), counts={s: sum(x["status"] == s for x in results)
                                                                   for s in sorted({x["status"] for x in results})})
    write(meta_path, meta)
    return 0 if all(x["status"] == "ok" for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
