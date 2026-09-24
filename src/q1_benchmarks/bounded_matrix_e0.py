"""Bounded two-worker controller; reuses frozen single-cell process/evidence helpers.

The manifest, scheduler, candidate executor and exporter are separate; no
algorithm search or hidden reruns. `selftest` uses four synthetic controller
jobs only. `run` refuses an existing batch directory.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_full4_e0 as h

HERE = "src/q1_benchmarks/bounded_matrix_e0.py"
MANIFEST = "src/q1_benchmarks/bounded_matrix_batch.json"
RESULT_ROOT = ROOT / "results/a/q1-bounded-matrix-20260924"
SUPPORT_COMMIT = "ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9"
SUPPORT_PATH = "src/q1_benchmarks/bounded_full4_e0.py"


def dispatch(jobs, worker, workers, guard, deadline):
    """At most workers submitted jobs, no large prefilled queue or retries."""
    halt = threading.Event()
    completed, inflight = {}, {}
    next_job = 0
    reason = None
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while next_job < len(jobs) or inflight:
            while not halt.is_set() and len(inflight) < workers and next_job < len(jobs):
                try:
                    if time.perf_counter() >= deadline:
                        raise RuntimeError("batch deadline reached")
                    guard()
                except Exception as error:
                    reason = f"dispatch stopped: {type(error).__name__}: {error}"
                    halt.set()
                    break
                job = jobs[next_job]
                next_job += 1
                inflight[pool.submit(worker, job, halt)] = job
            if not inflight:
                break
            ready, _ = wait(inflight, return_when=FIRST_COMPLETED, timeout=.25)
            for future in ready:
                job = inflight.pop(future)
                try:
                    result = future.result()
                except Exception as error:
                    result = {"status": "failed", "failure_class": "supervisor", "reason": str(error)}
                completed[job] = result
                if result.get("failure_class") == "supervisor":
                    reason = result.get("reason") or result.get("failure", {}).get("reason", "supervisor failure")
                    halt.set()
    return completed, reason


def selftest():
    active = peak = 0
    lock = threading.Lock()
    def worker(job, halt):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(.01)
        with lock:
            active -= 1
        return {"status": ["ok", "failed", "timeout", "ok"][job],
                "failure_class": "candidate" if job in (1, 2) else None}
    results, reason = dispatch(list(range(4)), worker, 2, lambda: None, time.perf_counter() + 5)
    assert len(results) == 4 and reason is None and peak <= 2
    stopped, reason = dispatch(list(range(4)), worker, 2, lambda: (_ for _ in ()).throw(RuntimeError("resource fixture")), time.perf_counter() + 5)
    assert not stopped and reason is not None
    print(json.dumps({"scope": "four synthetic controller jobs; no solver/E0/E1/E2", "completed": len(results), "peak_workers": peak,
                      "candidate_failures_continue": True, "resource_guard_stops_before_dispatch": True}))


def run(batch):
    begin = time.perf_counter()
    cfg = h.read(ROOT / MANIFEST)
    assert cfg["solver_commit"] == h.SOLVER
    assert cfg["cores"] == [1, 2, 3, 5] and cfg["workers"] == 2
    assert cfg["maximum_calls"] == {"solver": 400, "E0": 400, "E1": 0, "E2": 0}
    head, official, files = h.verify()
    for path, commit in ((HERE, head), (MANIFEST, head), (SUPPORT_PATH, SUPPORT_COMMIT)):
        if (ROOT / path).read_bytes() != h.git("show", f"{commit}:{path}"):
            raise RuntimeError(f"Unfrozen controller/support: {path}")
    guarded = [HERE, MANIFEST, SUPPORT_PATH, h.SOLVER_PATH, "src/q1/tree_frontier.py", "src/q1/component_pack.py", "uv.lock"]
    guarded += ["data/raw/a/official/" + p for p in files if p.startswith("code/") or p == "data/config.txt"]
    hashes = {p: h.sha(ROOT / p) for p in guarded}
    batch.mkdir(parents=True, exist_ok=False)
    env = h.environment()
    env["workers"] = cfg["workers"]
    jobs = [(f"{i:03d}", k) for i in range(1, 101) for k in cfg["cores"]]
    deadline = begin + cfg["batch_timeout_seconds"]
    records = {}  # In-memory start receipts survive a failed per-cell persistence step.
    meta = {"run_id": batch.name, "solver_commit": h.SOLVER, "runner_commit": head,
            "runner_path": HERE, "support_source": {"commit": SUPPORT_COMMIT, "path": SUPPORT_PATH},
            "official_code_hash": official["official_code_hash"], "config_sha256": h.sha(h.OFFICIAL / "data/config.txt"),
            "started_at": h.utc(), "finished_at": None, "environment": env, "manifest": cfg,
            "runner_argv": ["python", "-B", HERE, "run", batch.name], "status": "running",
            "cells": jobs, "resource_samples": [], "input_preparation_wall_seconds": None,
            "input_archive_sha256": official["case_archive"]["sha256"],
            "cold_start_definition": "Fresh interpreter per cell; OS filesystem caches not flushed",
            "concurrency_context": cfg["resource_agreement"], "stop_policy": cfg["stop_policy"]}
    h.write(batch / "batch.json", meta)

    def guard():
        if h.git("diff", "--name-only", head).strip():
            raise RuntimeError("tracked worktree changed after runner freeze")
        for path, expected in hashes.items():
            if h.sha(ROOT / path) != expected:
                raise RuntimeError(f"source/hash mismatch: {path}")
        raw = subprocess.check_output(["vm_stat"]).decode()
        pagesize = int(re.search(r"page size of (\d+) bytes", raw).group(1))
        counters = {a.strip(): int(b) for a, b in re.findall(r"([^\n:]+):\s+(\d+)\.", raw)}
        available = pagesize * sum(counters.get(k, 0) for k in ("Pages free", "Pages inactive", "Pages speculative"))
        processes = subprocess.check_output(["ps", "-axo", "pid=,pcpu=,command="]).decode()
        external = 0
        for line in processes.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) == 3 and int(parts[0]) != os.getpid() and float(parts[1]) >= 25 and "huaweicup2026" in parts[2] and batch.name not in parts[2]:
                external += 1
        sample = {"utc": h.utc(), "available_memory_estimate_bytes": available, "other_busy_project_processes": external}
        meta["resource_samples"].append(sample)
        if available < cfg["minimum_available_memory_bytes"]:
            raise RuntimeError("available-memory estimate below 4 GiB; stop dispatch for coordination")
        if external > cfg["maximum_other_busy_project_processes"]:
            raise RuntimeError("other busy project processes exceed coordinated two; stop dispatch for coordination")

    with tempfile.TemporaryDirectory(prefix="q1-bounded-matrix-input-") as tmp:
        inputs = Path(tmp)
        t0 = time.perf_counter()
        with zipfile.ZipFile(ROOT / official["case_archive"]["path"]) as z:
            for case in sorted({c for c, _ in jobs}):
                name = f"data/case_{case}.json"
                raw = z.read(name)
                if h.digest(raw) != files[name]["sha256"]:
                    raise RuntimeError("input archive member hash mismatch")
                (inputs / f"case_{case}.json").write_bytes(raw)
        meta["input_preparation_wall_seconds"] = time.perf_counter() - t0

        def worker(job, halt):
            case, cores = job
            folder = batch / "cells" / case / f"k{cores}"
            r = {"case_id": case, "cores": cores, "started_at": h.utc(), "finished_at": None,
                 "graph_sha256": files[f"data/case_{case}.json"]["sha256"], "status": "not_run", "failure": None,
                 "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, "artifacts": {}, "makespan_cycles": None}
            records[job] = r
            graph = inputs / f"case_{case}.json"
            plan, result, diag = folder / f"case_{case}_multicore_res.json", folder / "result.json", folder / "diagnostics.json"
            stage = "solver"
            try:
                folder.mkdir(parents=True, exist_ok=False)
                for stage in ("solver", "E0"):
                    if halt.is_set() or time.perf_counter() >= deadline:
                        r["not_run_reason"] = "supervisor stop or batch deadline before next stage"
                        break
                    if stage == "solver":
                        argv = [sys.executable, "-B", h.SOLVER_PATH, graph, "--output", plan, "--cores", cores,
                                "--packet-factor", 4, "--trigger-ops", 4096, "--chunk-ops", 1024, "--diagnostics", diag]
                    else:
                        argv = [sys.executable, "-B", h.OFFICIAL / "code/multicore_cut_evaluate_problem_1.py", graph, plan,
                                "--config", h.OFFICIAL / "data/config.txt", "--output", result, "--trace-output", folder / "trace.json", "--log-output", folder / "official.log"]
                    timeout = min(cfg["solver_timeout_seconds" if stage == "solver" else "evaluation_timeout_seconds"], deadline - time.perf_counter())
                    if timeout <= 0:
                        r["not_run_reason"] = "batch deadline before child spawn"
                        break
                    receipt = h.process(argv, folder, stage, timeout, inputs, lambda: r["calls"].__setitem__(stage, 1))
                    r["solver" if stage == "solver" else "evaluation"] = receipt
                    if receipt["status"] != "ok":
                        raise h.CandidateFailure(f"{stage} {receipt['status']}")
                    if stage == "solver":
                        if set(h.read(plan)) != {"node_to_subgraph", "core_schedules"}:
                            raise RuntimeError("Unexpected plan fields")
                        r["artifacts"].update(plan=h.artifact(plan), diagnostics=h.artifact(diag))
                        r["diagnostics"] = h.read(diag)
                        r["plan_sha256"] = h.sha(plan)
                    else:
                        obj = h.read(result)
                        if obj.get("scene") != "A" or obj.get("num_cores") != cores or type(obj.get("makespan")) not in (int, float) or obj["makespan"] <= 0:
                            raise RuntimeError("Unexpected official result identity")
                        r.update(makespan_cycles=obj["makespan"], data_movement_bytes=obj["data_movement_bytes"], status="ok")
                        r["artifacts"].update(result=h.compress(result), trace=h.compress(folder / "trace.json"), log=h.artifact(folder / "official.log"))
            except Exception as error:
                receipt = r.get("solver" if stage == "solver" else "evaluation", {})
                candidate = isinstance(error, h.CandidateFailure) and receipt.get("cleanup_confirmed") is True
                r.update(status="timeout" if receipt.get("status") == "timeout" else "failed", makespan_cycles=None,
                         failure_class="candidate" if candidate else "supervisor",
                         failure={"stage": stage, "reason": f"{type(error).__name__}: {error}", "exit_code": receipt.get("exit_code"), "elapsed_seconds": receipt.get("wall_seconds")})
                if not candidate:
                    halt.set()
            finally:
                r["finished_at"] = h.utc()
                try:
                    h.write(folder / "run.json", r)
                except Exception as error:
                    r.update(status="failed", failure_class="supervisor", makespan_cycles=None,
                             failure={"stage": "persistence", "reason": f"{type(error).__name__}: {error}"})
                    halt.set()
                print(json.dumps({"case": case, "cores": cores, "status": r["status"], "makespan": r["makespan_cycles"]}), flush=True)
            return r

        completed, reason = dispatch(jobs, worker, cfg["workers"], guard, deadline)
        for case, cores in jobs:
            if (case, cores) in completed and (batch / "cells" / case / f"k{cores}" / "run.json").exists():
                continue
            folder = batch / "cells" / case / f"k{cores}"
            folder.mkdir(parents=True, exist_ok=True)
            if (case, cores) in records:
                # Never overwrite an executed but unpersisted attempt with zero calls.
                h.write(folder / "run.json", records[(case, cores)])
                continue
            h.write(folder / "run.json", {"case_id": case, "cores": cores, "started_at": None, "finished_at": None,
                "graph_sha256": files[f"data/case_{case}.json"]["sha256"], "status": "not_run", "failure": None,
                "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, "artifacts": {}, "makespan_cycles": None,
                "not_run_reason": reason or "not dispatched"})
    rows = [h.read(batch / "cells" / c / f"k{k}" / "run.json") for c, k in jobs]
    counts = dict(Counter(r["status"] for r in rows))
    meta.update(finished_at=h.utc(), status="stopped" if reason else ("complete" if counts.get("ok") == 400 else "complete_with_candidate_failures"),
                stop_reason=reason or "all 400 cells processed", status_counts=counts,
                actual_calls={key: sum(r["calls"][key] for r in rows) for key in ("solver", "E0", "E1", "E2")})
    meta["batch_wall_seconds"] = time.perf_counter() - begin
    h.write(batch / "batch.json", meta)
    return 0 if meta["status"] == "complete" else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("selftest", "run"))
    p.add_argument("run_id", nargs="?")
    args = p.parse_args()
    if args.action == "selftest":
        return selftest()
    if not args.run_id or not re.fullmatch(r"[a-zA-Z0-9_-]+", args.run_id):
        p.error("valid run_id required")
    return run(RESULT_ROOT / args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
