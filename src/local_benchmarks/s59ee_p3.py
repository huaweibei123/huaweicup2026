"""Concurrent fixed Q3 construction with its single integrated official E0 call."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import subprocess
import sys
import time

import s59ee_p2_multicore as common

ROOT = common.ROOT
SOLVER_COMMIT = "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f"
CODE_HASH = common.CODE_HASH


def verify_source(source):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=source, text=True)
    if head != SOLVER_COMMIT or dirty:
        raise RuntimeError("pinned Q3 source is not clean")
    manifest = common.read(ROOT / "docs/a/source-manifest.json")
    if manifest["official_code_hash"] != CODE_HASH:
        raise RuntimeError("official code identity changed")
    for item in manifest["files"]:
        name = item["path"]
        if name.startswith("code/") or name == "data/config.txt" or name.startswith("data/case_"):
            for base in (ROOT, source):
                path = base / "data/raw/a/official" / name
                if path.stat().st_size != item["bytes"] or common.sha(path) != item["sha256"]:
                    raise RuntimeError(f"frozen file differs: {name}")


def cell(case, cores, source, batch, deadline):
    folder = batch / "cells" / case / f"k{cores}"
    folder.mkdir(parents=True, exist_ok=False)
    graph = source / f"data/raw/a/official/data/case_{case}.json"
    plan = folder / f"case_{case}_multicore_res.json"
    evidence = folder / "evidence"
    record = {"case_id": case, "problem": "P3", "cores": cores,
              "algorithm_id": "q3-structure-selected-online", "solver_commit": SOLVER_COMMIT,
              "started_at": common.utc(), "status": "running", "graph_sha256": common.sha(graph),
              "config_sha256": common.sha(source / "data/raw/a/official/data/config.txt"),
              "official_code_hash": CODE_HASH, "artifacts": {},
              "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}}
    common.write(folder / "run.json", record)
    try:
        if time.monotonic() >= deadline or common.available_bytes() < common.MIN_AVAILABLE:
            record.update(status="not_run", failure={"stage": "queue", "reason": "deadline or <8GiB available"})
            return record
        argv = [sys.executable, "-B", "-m", "src.q3.solve", graph, "--cores", str(cores),
                "-o", plan, "--evidence", evidence]
        record["calls"].update(solver=1, E0=1)  # integrated E0 can be entered; reserve one even on interruption
        record["solver"] = common.run_child(argv, source, min(180, max(1, deadline-time.monotonic())),
                                            [(ROOT, "<benchmark-root>"), (source, "<solver-root>")])
        if record["solver"]["status"] != "ok" or not plan.exists() or not (evidence / "result.json.gz").exists():
            record.update(status=record["solver"]["status"], failure={"stage": "Q3 solver/online E0", "reason": "no complete plan and E0 result"})
            return record
        plan_obj = common.read(plan)
        if set(plan_obj) != {"node_to_subgraph", "core_schedules"}:
            raise RuntimeError("plan shape differs")
        result = json.loads(gzip.decompress((evidence / "result.json.gz").read_bytes()))
        if result.get("scene") != "B" or result.get("problem") != 3 or result.get("cache_mode") != "read_only" or result.get("num_cores") != cores:
            raise RuntimeError("official P3 result identity differs")
        receipt = common.read(evidence / "receipt.json")
        if receipt["official_e0_calls"] != 1 or receipt["makespan"] != result["makespan"]:
            raise RuntimeError("Q3 result and receipt mismatch")
        record["makespan_cycles"] = result["makespan"]
        record["data_movement_bytes"] = result.get("data_movement_bytes")
        record["cache_stats"] = result.get("cache_stats")
        for name, path in (("plan", plan), ("result", evidence / "result.json.gz"),
                           ("q3_receipt", evidence / "receipt.json")):
            record["artifacts"][name] = {"path": path.relative_to(ROOT).as_posix(), "sha256": common.sha(path)}
        record["status"] = "ok"
        return record
    except Exception as error:
        record.update(status="failed", failure={"stage": "controller", "reason": f"{type(error).__name__}: {error}"})
        return record
    finally:
        record["finished_at"] = common.utc()
        common.write(folder / "run.json", record)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--batch", type=Path, required=True)
    p.add_argument("--cases", required=True)
    p.add_argument("--cores", default="1,2,3,4,5")
    p.add_argument("--workers", type=int, required=True)
    args = p.parse_args()
    cases = args.cases.split(",")
    cores = [int(x) for x in args.cores.split(",")]
    if len(set(cases)) != len(cases) or any(c not in {f"{i:03d}" for i in range(1,101)} for c in cases):
        p.error("invalid cases")
    if len(set(cores)) != len(cores) or any(k not in range(1,6) for k in cores):
        p.error("invalid cores")
    if args.workers not in (1,2,4,8):
        p.error("workers must be 1,2,4,8")
    source, batch = args.source.resolve(), args.batch.resolve()
    if not batch.is_relative_to(ROOT / "results/a/local-p3-20260924"):
        p.error("unexpected output directory")
    verify_source(source)
    batch.mkdir(parents=True, exist_ok=True)
    meta_path = batch / "batch.json"
    if meta_path.exists():
        meta = common.read(meta_path)
        if meta["solver_commit"] != SOLVER_COMMIT or meta["runner_sha256"] != common.sha(__file__):
            raise RuntimeError("batch identity changed")
    else:
        meta = {"schema": "local-p3-v1", "batch_id": batch.name, "started_at": common.utc(),
                "solver_commit": SOLVER_COMMIT, "official_code_hash": CODE_HASH,
                "runner_sha256": common.sha(__file__), "helper_sha256": common.sha(common.__file__),
                "python": sys.version, "invocations": []}
    start = datetime.fromisoformat(meta["started_at"].replace("Z", "+00:00"))
    deadline_utc = start + timedelta(minutes=30)
    deadline = time.monotonic() + (deadline_utc-datetime.now(timezone.utc)).total_seconds()
    meta["deadline_utc"] = deadline_utc.isoformat().replace("+00:00", "Z")
    if time.monotonic() >= deadline:
        raise RuntimeError("batch deadline exceeded")
    jobs = [(c,k) for c in cases for k in cores]
    existing = [(c,k) for c,k in jobs if (batch / "cells" / c / f"k{k}").exists()]
    if existing:
        raise RuntimeError(f"existing jobs may not be retried: {existing}")
    available = common.available_bytes()
    if available < common.MIN_AVAILABLE:
        raise RuntimeError("<8GiB available before launch")
    invocation = {"started_at": common.utc(), "cases": cases, "cores": cores,
                  "workers": args.workers, "available_bytes_before": available, "status": "running"}
    meta["invocations"].append(invocation)
    common.write(meta_path, meta)
    results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(cell,c,k,source,batch,deadline):(c,k) for c,k in jobs}
        for f in as_completed(futures):
            item=f.result(); results.append(item)
            print(json.dumps({"case": item["case_id"], "cores": item["cores"], "status": item["status"], "makespan": item.get("makespan_cycles")}), flush=True)
    invocation.update(status="complete", finished_at=common.utc(), counts={s:sum(x["status"]==s for x in results)
                                                                          for s in sorted({x["status"] for x in results})})
    common.write(meta_path, meta)
    return 0 if all(x["status"]=="ok" for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
