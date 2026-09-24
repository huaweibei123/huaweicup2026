"""One explicitly authorized real-case008 mechanism probe; no search or retry.

The frozen author CLI's auto mode constructs a candidate even if its dominance
certificate is false. This runner evaluates that candidate once, without
claiming production adoption or invoking the author's fallback adapter.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import pro_micro_e0 as h

RUNNER = Path(__file__).relative_to(ROOT).as_posix()
RESULT_ROOT = ROOT / "results/a/review/p1-pro-case008-e0-20260924"


def verify(manifest, head):
    h.verify(manifest, head)
    if (ROOT / RUNNER).read_bytes() != h.git("show", f"{head}:{RUNNER}"):
        raise RuntimeError("Case008 runner not frozen")
    for item in manifest["runtime_dependencies"]:
        if h.digest((ROOT / item["path"]).read_bytes()) != item["sha256"]:
            raise RuntimeError(f"Runtime dependency changed: {item['path']}")
    for record in (manifest["input"], *manifest["baseline"]["artifacts"]):
        if record.get("commit"):
            raw = h.git("show", f"{record['commit']}:{record['path']}")
        else:
            raw = (ROOT / record["path"]).read_bytes()
        if h.digest(raw) != record["sha256"]:
            raise RuntimeError(f"Identity mismatch: {record['path']}")
        if not record.get("commit") and h.git("show", f"{head}:{record['path']}") != raw:
            raise RuntimeError(f"Frozen Git input bytes differ: {record['path']}")


def process(argv, batch, name, timeout, deadline, launched):
    started, t0 = h.utc(), time.perf_counter()
    end = min(t0 + timeout, deadline)
    if end - t0 <= 1:
        raise TimeoutError("No remaining process and cleanup budget")
    receipt = {"argv": argv, "cwd": ".", "started_at": started, "status": "starting",
               "pid": None, "exit_code": None, "cleanup_confirmed": False,
               "limit_including_cleanup_seconds": end - t0, "cleanup_reserve_seconds": 1}
    h.write(batch / f"{name}-process.json", receipt)
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    child = None
    timed_out = False
    try:
        with (batch / f"{name}.stdout.txt").open("xb") as out, (batch / f"{name}.stderr.txt").open("xb") as err:
            child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=err, start_new_session=True)
            receipt.update(pid=child.pid, process_group_id=child.pid, status="running")
            h.write(batch / f"{name}-process.json", receipt)
            launched()
            try:
                child.wait(timeout=max(0, end - time.perf_counter() - 1))
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=max(0, end - time.perf_counter()))
    finally:
        if child is not None:
            if child.poll() is None or not h.group_gone(child.pid):
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                if child.poll() is None:
                    child.wait(timeout=max(0, end - time.perf_counter()))
            receipt.update(exit_code=child.returncode,
                           cleanup_confirmed=child.poll() is not None and h.group_gone(child.pid))
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt.update(finished_at=h.utc(), wall_seconds=time.perf_counter() - t0, timed_out=timed_out,
                       user_cpu_seconds=after.ru_utime - before.ru_utime,
                       system_cpu_seconds=after.ru_stime - before.ru_stime,
                       child_peak_rss_bytes_cumulative=after.ru_maxrss,
                       rss_scope="Darwin cumulative child maximum, not isolated process peak",
                       status="timeout" if timed_out else "ok" if receipt["exit_code"] == 0 else "failed")
        for which in ("stdout", "stderr"):
            path = batch / f"{name}.{which}.txt"
            if path.exists():
                receipt[which] = h.artifact(path)
        receipt["text_derivation"] = "Raw stdout/stderr, relative paths, no rewriting"
        h.write(batch / f"{name}-process.json", receipt)
    if not receipt["cleanup_confirmed"]:
        raise RuntimeError("Cannot confirm owned process cleanup")
    return receipt


def run(batch, manifest):
    head = h.git("rev-parse", "HEAD").decode().strip()
    verify(manifest, head)
    auth = h.read(batch / "EXECUTION_AUTHORIZATION.json")
    if auth.get("gate") != "AUTHORIZED" or auth.get("runner_commit") != head or auth.get("source_commit") != manifest["source_commit"]:
        raise RuntimeError("HOLD: root execution authorization required")
    with (batch / "STARTED.json").open("x") as f:
        json.dump({"runner_commit": head, "started_at": h.utc(), "controller_pid": os.getpid()}, f)
        f.write("\n")
    t0 = time.perf_counter()
    deadline = t0 + 120
    record = {"run_id": batch.name, "case_id": "008", "cores": 4,
              "kind": "real-case mechanism candidate; not production adoption", "status": "running",
              "gate": "RUNNING", "started_at": h.utc(), "runner_commit": head,
              "source_commit": manifest["source_commit"], "source_sha256": manifest["entry_sha256"],
              "manifest": h.artifact(batch / "manifest.json"), "runner": h.artifact(ROOT / RUNNER),
              "authorization": h.artifact(batch / "EXECUTION_AUTHORIZATION.json"),
              "input": h.artifact(ROOT / manifest["input"]["path"]),
              "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0, "baseline_E0": 0},
              "evaluation": {"status": "not_run"}, "environment": manifest["environment"],
              "limitation": "CLI auto candidate is tested once even if certificate=false; no online E0 or parameter selection"}
    h.write(batch / "run.json", record)
    def launched(kind):
        record["calls"][kind] += 1
        h.write(batch / "run.json", record)
    rel = lambda p: p.relative_to(ROOT).as_posix()
    try:
        argv = [".venv/bin/python", "-B", manifest["entry_local_path"], manifest["input"]["path"],
                "--cores", "4", "--config", "data/raw/a/official/data/config.txt",
                "--output", rel(batch / "plan.json"), "--diagnostics", rel(batch / "diagnostics.json"), "--mode", "auto"]
        solver = process(argv, batch, "solver", 30, deadline, lambda: launched("solver"))
        record["solver"] = solver
        if solver["status"] != "ok":
            raise RuntimeError(f"Constructor {solver['status']}")
        info = h.read(batch / "diagnostics.json")
        plan = h.read(batch / "plan.json")
        graph = h.read(ROOT / manifest["input"]["path"])
        if set(plan) != {"node_to_subgraph", "core_schedules"}:
            raise ValueError("Unexpected plan keys")
        verify(manifest, head)
        sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
        from evaluation_validation import validate_graph, validate_task_order
        from stub_multicore_cut_and_schedule import derive_multicore_plan
        validate_graph(graph)
        view = derive_multicore_plan(graph, plan)
        validate_task_order(view)
        if view["num_cores"] != 4:
            raise ValueError("Candidate is not four-core")
        record.update(plan=h.artifact(batch / "plan.json"), diagnostics=h.artifact(batch / "diagnostics.json"),
                      task_count=len(view["subgraph_ids"]), legality="Official graph/plan/task-order checks passed",
                      constructor_selection={k: info.get(k) for k in ("packet", "cut_chains", "whole_packet", "conservative_dominance_certificate")})
        h.write(batch / "run.json", record)
        argv = [".venv/bin/python", "-B", "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
                manifest["input"]["path"], rel(batch / "plan.json"), "--config", "data/raw/a/official/data/config.txt",
                "--output", rel(batch / "result.json"), "--trace-output", rel(batch / "trace.json"),
                "--log-output", rel(batch / "official.log")]
        evaluation = process(argv, batch, "e0", 60, deadline, lambda: launched("E0"))
        record["evaluation"] = evaluation
        if evaluation["status"] != "ok":
            raise RuntimeError(f"Official E0 {evaluation['status']}")
        result = h.read(batch / "result.json")
        h.read(batch / "trace.json")
        if result["scene"] != "A" or result["num_cores"] != 4 or not result["makespan"] > 0:
            raise ValueError("Official result identity/value mismatch")
        record.update(status="ok", makespan_cycles=result["makespan"], data_movement_bytes=result["data_movement_bytes"],
                      M_V_overlap_cycles_sum_over_cores=h.overlap(result))
        for key in ("result.json", "trace.json", "official.log"):
            record[key] = h.artifact(batch / key)
        execution = []
        for core in result["per_core_timeline"]:
            groups = {}
            for op in core["ops"]:
                groups.setdefault((op["task_id"], op["pipe"]), []).append(op)
            for (task, pipe), ops in sorted(groups.items()):
                execution.append({"core": core["core_id"], "task": task, "pipe": pipe,
                                  "ops_in_observed_start_order": sorted(ops, key=lambda x: (x["start"], x["op_id"]))})
        audit = {"source": "Observed official E0 output only; no second compiler/evaluator invocation",
                 "pipe_execution_order": execution, "memory_dependency_count_by_task": {
                     key: value["memory_dependency_count"] for key, value in result["step3_by_task"].items()},
                 "memory_edge_endpoints": "Not emitted by official E0 result; not reconstructed or guessed"}
        h.write(batch / "official-structure-audit.json", audit)
        record["structure_audit"] = h.artifact(batch / "official-structure-audit.json")
        baseline = manifest["baseline"]
        old = json.loads(gzip.decompress(h.git("show", f"{baseline['commit']}:{baseline['result_path']}")))
        comparison = {"old_fixed": baseline, "new_official_makespan": result["makespan"],
                      "makespan_delta_new_minus_old": result["makespan"] - old["makespan"],
                      "old_over_new_ratio": old["makespan"] / result["makespan"],
                      "new_official_movement": result["data_movement_bytes"],
                      "old_official_movement": old["data_movement_bytes"],
                      "model_claims_not_official": {key: info["model"].get(key) for key in
                          ("cycles", "upper_envelope_cycles", "conditional_exact_model", "virgin_capacity_certificate",
                           "M_V_overlap_cycles_sum_over_cores", "official_iteration_budget_sufficient_condition")},
                      "full_model_output": h.artifact(batch / "diagnostics.json"),
                      "certificate": info.get("conservative_dominance_certificate"),
                      "scope": "Single offline mechanism candidate, no production adoption or generalization claim"}
        h.write(batch / "comparison.json", comparison)
        record["comparison"] = h.artifact(batch / "comparison.json")
    except BaseException as exc:
        record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        (batch / "failure.txt").write_text(traceback.format_exc())
    finally:
        receipts = [h.read(p) for p in batch.glob("*-process.json")]
        released = all(r["cleanup_confirmed"] and h.group_gone(r["pid"]) for r in receipts)
        record.update(finished_at=h.utc(), wall_seconds=time.perf_counter() - t0,
                      gate="CLOSED", owned_processes_released=released)
        h.write(batch / "run.json", record)
        h.write(batch / "resource-release.json", {"checked_at": h.utc(), "gate": "CLOSED",
            "all_owned_child_groups_exited": released, "pids": [r["pid"] for r in receipts], "calls": record["calls"]})
        print(json.dumps({k: record.get(k) for k in ("status", "calls", "makespan_cycles", "constructor_selection", "owned_processes_released", "wall_seconds", "error")}), flush=True)
    return 0 if record["status"] == "ok" and record["owned_processes_released"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "run"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id:
        raise ValueError("Invalid run id")
    batch = RESULT_ROOT / args.run_id
    manifest = h.read(batch / "manifest.json")
    if args.action == "preflight":
        verify(manifest, h.git("rev-parse", "HEAD").decode().strip())
        print(json.dumps({"status": "ready_hold", "solver_calls": 0, "E0_calls": 0}))
        return 0
    return run(batch, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
