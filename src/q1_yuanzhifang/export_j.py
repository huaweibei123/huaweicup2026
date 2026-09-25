"""Export Stage J's frozen three-cell E0 results; never run a solver."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPO = "huaweibei123/huaweicup2026"
SOLVER = "aa3f18a71b117ebd0476c8d714c97d8d366d74d7"
RUNNER = "f3e548f1915ce895e1f785219420fc747777ceb0"
BASELINE = "0b47d802cdd0bfe7011017c8098c1c0917b2c959"
BASELINE_SOURCE = "results/benchmark-board/official-singlecore-20260924/051"
OUT = Path("results/a/q1-yuanzhifang-stage-j/stage-j-20260925")
SESSION = "yuanzhifang30-sudo/s-7748b08eb22a449797a2417ad7825aaa"
CELLS = (("control", 3), ("paced", 3), ("paced", 4))
COPY_BYTES = 32768
ORIGINAL_LARGE_COPIES = 288


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def source(commit: str, path: str, entrypoint: str) -> dict:
    git("cat-file", "-e", f"{commit}:{path}")
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def artifact(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(raw)}


def allocation(plan: dict) -> dict:
    task_core = {task: core for core, tasks in enumerate(plan["core_schedules"])
                 for task in tasks}
    return {node: task_core[task] for node, task in plan["node_to_subgraph"].items()}


def official_hash() -> str:
    code = ROOT / "data/raw/a/official/code"
    signature = "".join(f"code/{p.name}\t{sha(p.read_bytes())}\n"
                        for p in sorted(code.iterdir()) if p.is_file())
    return sha(signature.encode())


def export(graphs: Path, feed_path: Path) -> int:
    folder = ROOT / OUT
    run_dir = folder / "run"
    manifest = json.loads((run_dir / "batch_manifest.json").read_text(encoding="utf-8"))
    receipt = json.loads((run_dir / "batch_receipt.json").read_text(encoding="utf-8"))
    if manifest["solver_commit"] != SOLVER or manifest["runner_head"] != RUNNER:
        raise ValueError("frozen solver/runner identity mismatch")
    if manifest["producer_session"] != SESSION:
        raise ValueError("producer session mismatch")
    if receipt["calls"] != {"solver": 3, "E0": 3, "E1": 0, "E2": 0}:
        raise ValueError("unexpected batch call ledger")
    if receipt["stopped_after_supervision_failure"]:
        raise ValueError("batch stopped after supervision failure")

    source_manifest = json.loads(git("show", f"{SOLVER}:docs/a/source-manifest.json"))
    oh = official_hash()
    if oh != manifest["official_code_hash"] or oh != source_manifest["official_code_hash"]:
        raise ValueError("official source hash mismatch")
    graph_raw = (graphs / "case_051.json").read_bytes()
    graph_hash = sha(graph_raw)
    if graph_hash != manifest["graph_sha256"]:
        raise ValueError("input graph hash mismatch")
    config_hash = sha((ROOT / "data/raw/a/official/data/config.txt").read_bytes())
    if config_hash != manifest["config_sha256"]:
        raise ValueError("config hash mismatch")

    baseline_dir = folder / "baseline/051"
    baseline_run_raw = git("show", f"{BASELINE}:{BASELINE_SOURCE}/run.json")
    baseline_result_raw = git("show", f"{BASELINE}:{BASELINE_SOURCE}/result.json.gz")
    if ((baseline_dir / "run.json").read_bytes() != baseline_run_raw or
            (baseline_dir / "result.json.gz").read_bytes() != baseline_result_raw):
        raise ValueError("copied singlecore baseline differs from fixed Git source")
    baseline_run = json.loads(baseline_run_raw)
    baseline_result_raw_json = gzip.decompress(baseline_result_raw)
    baseline_result = json.loads(baseline_result_raw_json)
    if (baseline_run["makespan_cycles"] != 607628 or baseline_result["makespan"] != 607628 or
            baseline_result["num_cores"] != 1 or baseline_run["graph_sha256"] != graph_hash or
            baseline_run["config_sha256"] != config_hash or
            baseline_run["official_code_hash"] != oh):
        raise ValueError("singlecore baseline identity mismatch")

    plans, rows, results, records, comparisons = {}, [], {}, [], []
    for variant, cores in CELLS:
        cell = run_dir / f"051-k{cores}-{variant}"
        row = json.loads((cell / "run.json").read_text(encoding="utf-8"))
        plan_path = cell / "case_051_multicore_res.json"
        plan_raw = plan_path.read_bytes()
        plan = json.loads(plan_raw)
        diagnostic = json.loads((cell / "diagnostics.json").read_text(encoding="utf-8"))
        result_raw = (cell / "e0_result.json").read_bytes()
        trace_raw = (cell / "e0_trace.json").read_bytes()
        log_raw = (cell / "e0_log.txt").read_bytes()
        result = json.loads(result_raw)
        if (row["status"] != "success" or row["case"] != "051" or row["cores"] != cores or
                row["variant"] != variant or row["graph_sha256"] != graph_hash or
                row["plan_sha256"] != sha(plan_raw) or set(plan) != {"node_to_subgraph", "core_schedules"} or
                result["scene"] != "A" or result["num_cores"] != cores or
                result["makespan"] != row["makespan_cycles"] or
                row["e0_result_sha256"] != sha(result_raw) or
                row["e0_trace_sha256"] != sha(trace_raw) or row["e0_log_sha256"] != sha(log_raw)):
            raise ValueError(f"cell artifact/identity mismatch: {variant}/k{cores}")
        solver = row["solver"]
        evaluator = row["e0"]
        if (solver["returncode"] != 0 or solver["timeout"] or
                evaluator["returncode"] != 0 or evaluator["timeout"] or
                row["calls"] != {"solver": 1, "E0": 1, "E1": 0, "E2": 0}):
            raise ValueError(f"cell call/process accounting mismatch: {variant}/k{cores}")
        pipes = {"PIPE_MTE2": 0, "PIPE_MTE3": 0}
        for task in result["step3_by_task"].values():
            for key in pipes:
                pipes[key] += task["pipe_op_counts"].get(key, 0)
        copy_ops = sum(pipes.values())
        scheduled = result["data_movement_bytes"]["scheduled_copy_bytes"]
        large_copies = (scheduled - 2 * copy_ops) // (COPY_BYTES - 2)
        if large_copies != ORIGINAL_LARGE_COPIES:
            raise ValueError(f"unexpected 32KiB copy count: {large_copies}")
        small_copies = copy_ops - large_copies
        task_count = sum(map(len, plan["core_schedules"]))
        if diagnostic["task_count"] != task_count:
            raise ValueError("diagnostic/plan task count mismatch")

        plans[(variant, cores)] = plan
        rows.append((variant, cores, row, diagnostic, result, cell,
                     copy_ops, large_copies, small_copies, task_count))
        results[(variant, cores)] = result

    same_mapping = allocation(plans[("control", 3)]) == allocation(plans[("paced", 3)])
    if not same_mapping or receipt["k3_control_paced_same_chain_to_core_allocation"] is not True:
        raise ValueError("k3 chain-to-core mapping is not paired")

    baseline_artifact = artifact(baseline_dir / "result.json.gz")
    baseline_info = {"graph_sha256": graph_hash, "config_sha256": config_hash,
                     "official_sha256": oh, "route": "E0",
                     "entrypoint": "singlecore_evaluate.evaluate_singlecore",
                     "result": baseline_artifact}
    singlecore_cycles = baseline_result["makespan"]
    missing = {
        "provenance.environment.gpu": "No GPU was used or measured for this CPU run.",
        "provenance.environment.ram_bytes": "Total physical RAM was not recorded in the frozen batch receipt; pre-start free RAM was checked separately.",
        "provenance.environment.threads": "OS thread count was not instrumented; the batch used two cell workers.",
        "provenance.environment.peak_rss_bytes": "Child peak RSS was not instrumented.",
        "provenance.measurement.seed": "The fixed structural construction is deterministic and has no RNG seed.",
    }
    for variant, cores, row, diagnostic, result, cell, copy_ops, large_copies, small_copies, task_count in rows:
        artifacts = {"run": artifact(cell / "run.json"),
                    "manifest": artifact(run_dir / "batch_manifest.json"),
                    "plan": artifact(cell / "case_051_multicore_res.json"),
                    "result": artifact(cell / "e0_result.json"),
                    "trace": artifact(cell / "e0_trace.json"),
                    "log": artifact(cell / "e0_log.txt")}
        movement = result["data_movement_bytes"]
        plan_hash = artifacts["plan"]["sha256"]
        record = {
            "attempt_id": f"fang-q1-stage-j-20260925-051-k{cores}-{variant}-r0",
            "revision": 1, "run_id": "fang-q1-stage-j-20260925",
            "algorithm_id": "q1-intact-chain-pacing",
            "algorithm_name": "完整链源核错峰构造",
            "variant": variant, "solver_commit": SOLVER,
            "parameters": {"cores": cores, "variant": variant, "tail_core": diagnostic["tail_core"],
                           "task_count": task_count, "tasks_per_core": [len(x) for x in plans[(variant, cores)]["core_schedules"]],
                           "e0_mte_copy_ops_count": copy_ops, "scheduled_32k_copy_count": large_copies,
                           "remaining_small_copy_count": small_copies,
                           "k3_chain_to_core_mapping_matches_control": same_mapping if cores == 3 else None,
                           "baseline_commit": BASELINE,
                           "batch_budget": {"solver": 3, "E0": 3, "E1": 0, "E2": 0,
                                            "retries": 0, "workers": 2, "solver_timeout_seconds": 30,
                                            "e0_timeout_seconds": 60, "wall_seconds": 180},
                           "batch_actual_calls": receipt["calls"]},
            "problem": "P1", "case_id": "051", "cores": cores, "status": "ok",
            "metrics": {"makespan_cycles": result["makespan"],
                        "solver_wall_seconds": row["solver"]["wall_seconds"],
                        "evaluation_wall_seconds": row["e0"]["wall_seconds"],
                        "ddr_bytes": movement["scheduled_copy_bytes"],
                        "extra_ddr_bytes": movement["added_copy_bytes"],
                        "spill_bytes": movement["spill_added_copy_bytes"], "cache_hit_rate": None},
            "evaluator": {"route": "E0", "commit": RUNNER,
                          "entrypoint": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"},
            "identity": {"graph_sha256": graph_hash, "config_sha256": config_hash,
                         "official_sha256": oh, "plan_sha256": plan_hash},
            "artifacts": artifacts, "runtime_id": "fang-windows-q1-stage-j-20260925",
            "observed_at": row["finished_at"],
            "timing": {"solver_includes_evaluation": False,
                       "evaluation_precision": "Cold solver and unchanged external E0 process wall seconds, measured separately",
                       "utc": "UTC ISO8601 Z"},
            "provenance": {
                "producer_session": SESSION,
                "task_url": "https://github.com/huaweibei123/huaweicup2026/issues/98",
                "solver": {"source": source(SOLVER, "src/q1_yuanzhifang/intact_pacing.py", "main"),
                           "authors": ["yuanzhifang30-sudo"],
                           "method": "Strict guarded full four-node PIPE_V chains. Control assigns one intact chain-bin Task per core each round. Paced splits only selected source-core chains from round two into phase 0/1 Tasks; tail ADD Task remains phase 2 on core 0.",
                           "references": ["https://github.com/huaweibei123/huaweicup2026/issues/98"],
                           "upstream": [source(SOLVER, "src/q1_yuanzhifang/construct.py", "build_schedule")],
                           "selected_algorithm_id": None, "selected_solver_commit": None},
                "runner": {"source": source(RUNNER, "src/q1_yuanzhifang/benchmark_j.py", "main"),
                           "argv": ["python", "-m", "src.q1_yuanzhifang.benchmark_j", "--graphs", "GRAPH_DIR",
                                    "--start-token", "STAGE-J-20260925-START", "--producer-session", SESSION],
                           "working_directory": "."},
                "environment": {"os": manifest["platform"], "cpu": manifest["cpu"], "gpu": None,
                                "ram_bytes": None, "python": manifest["python"],
                                "dependencies": "uv.lock sha256 " + sha((ROOT / "uv.lock").read_bytes()),
                                "threads": None, "workers": 2, "peak_rss_bytes": None},
                "measurement": {"started_at": row["started_at"], "finished_at": row["finished_at"],
                                "seed": None, "repeat_index": 0, "cold_start": True,
                                "solver_scope": "Full cold solver process through plan/diagnostic write and Windows Job cleanup.",
                                "evaluation_scope": "Separate unchanged official E0 CLI through result/trace/log write and Windows Job cleanup.",
                                "budget": {"wall_seconds": 180, "candidate_limit": 1,
                                           "stop_reason": "complete; three fixed cells; no retries"},
                                "calls": {"solver": 1, "E0": 1, "E1": 0, "E2": 0},
                                "offline_costs": "No per-case precomputation; frozen singlecore E0 denominator reused from the exact source commit with zero new baseline calls.",
                                "failure": None},
                "missing_reasons": missing},
            "notes": ["Three diagnostic falsification cells only; not a full P1 average.",
                      "The k3 control/paced pair uses identical chain-to-core mapping; k4 changes core count and is a transport comparison, not a paired causal estimate.",
                      f"E0 PIPE_MTE2+PIPE_MTE3 count={copy_ops}; derived 32KiB scheduled copies={large_copies}, remaining small copies={small_copies}."],
            "source_url": "https://github.com/huaweibei123/huaweicup2026/issues/98",
            "baseline": baseline_info, "cache_pair": None}
        records.append(record)
        comparisons.append({"variant": variant, "cores": cores,
                            "makespan_cycles": result["makespan"], "singlecore_cycles": singlecore_cycles,
                            "singlecore_speedup": singlecore_cycles / result["makespan"],
                            "solver_wall_seconds": row["solver"]["wall_seconds"],
                            "e0_wall_seconds": row["e0"]["wall_seconds"],
                            "scheduled_copy_bytes": movement["scheduled_copy_bytes"],
                            "extra_ddr_bytes": movement["added_copy_bytes"],
                            "spill_bytes": movement["spill_added_copy_bytes"],
                            "tasks": task_count, "mte_copy_ops": copy_ops,
                            "large_32k_copies": large_copies, "small_copies": small_copies,
                            "k3_same_chain_to_core_mapping": same_mapping if cores == 3 else "not paired"})

    if feed_path.exists():
        raise FileExistsError(feed_path)
    feed_path.parent.mkdir(parents=True, exist_ok=True)
    with feed_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"schema_version": 1, "submission_version": 1, "records": records},
                  stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    comparison_path = folder / "comparison.csv"
    if comparison_path.exists():
        raise FileExistsError(comparison_path)
    with comparison_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    print(json.dumps({"records": len(records), "feed": feed_path.as_posix(),
                      "calls": receipt["calls"], "k3_mapping_matches": same_mapping}))
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--feed", type=Path, required=True)
    args = parser.parse_args()
    export(args.graphs.resolve(), args.feed.resolve())


if __name__ == "__main__":
    main()
