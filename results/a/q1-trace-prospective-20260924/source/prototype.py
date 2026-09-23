"""First Q1 candidate portfolio; select only by the frozen official CLI.

The static local-duration schedule is a proposal, not a DDR-aware evaluator.
The starter uses topological intervals; --structural also tries chain packets,
whole components and acyclic same-core cover contractions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
sys.path.insert(0, str(OFFICIAL / "code"))

from evaluation_validation import read_evaluation_config  # noqa: E402
from multicore_cut_evaluate_problem_1 import (  # noqa: E402
    _build_scene_a_tasks, read_scene_a_config,
)
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes,
    _random_topological_order, generate_multicore_plan,
)
from structure import structural_partition, fuse_covers  # noqa: E402


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixed_blocks(graph, cores, seed, block_size):
    eligible = sorted(op["id"] for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"})
    _, full_succs = _build_op_adjacency(graph)
    preds, succs = _contract_excluded_copy_nodes(eligible, full_succs)
    rng = random.Random(seed)
    order = _random_topological_order(eligible, preds, succs, rng)
    mapping = {node: i // block_size for i, node in enumerate(order)}
    schedules = [[] for _ in range(cores)]
    for tid in sorted(set(mapping.values())):
        schedules[rng.randrange(cores)].append(tid)
    return {"node_to_subgraph": mapping, "core_schedules": schedules}


def place_by_local_duration(graph, partition, settings, waits):
    """Earliest estimated finish on compiled Task durations; exact E0 follows."""
    tasks, _, _, view = _build_scene_a_tasks(
        graph, partition, settings["bandwidth"], settings["capacity"])
    cores = [[] for _ in partition["core_schedules"]]
    core_end = [0] * len(cores)
    finish, assignment = {}, {}
    for tid in view["subgraph_ids"]:
        predecessors = view["subgraph_preds"][tid]
        assert all(p < tid for p in predecessors), "Expected topological intervals"
        duration = tasks[tid]["step3"]["makespan"]
        options = []
        for core in range(len(cores)):
            ready = core_end[core] + (waits["task_same_core_wait_cycles"] if cores[core] else 0)
            for pred in predecessors:
                ready = max(ready, finish[pred] + (
                    waits["task_cross_core_wait_cycles"] if assignment[pred] != core else 0))
            options.append((ready + duration, core))
        end, chosen = min(options)
        cores[chosen].append(tid)
        core_end[chosen] = finish[tid] = end
        assignment[tid] = chosen
    return {"node_to_subgraph": partition["node_to_subgraph"], "core_schedules": cores}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--structural", action="store_true", help="Add chain/component and protected cover candidates")
    args = parser.parse_args()
    if args.cores < 1 or args.block_size < 1 or args.timeout <= 0:
        parser.error("cores, block-size and timeout must be positive")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    graph_path = args.graph.resolve()
    graph = json.loads(graph_path.read_text())
    config = OFFICIAL / "data/config.txt"
    settings = read_evaluation_config(str(config))
    waits = read_scene_a_config(str(config))
    common = dict(num_cores=args.cores, seed=args.seed)
    baseline = generate_multicore_plan(graph, **common)
    partition = fixed_blocks(graph, args.cores, args.seed, args.block_size)
    eligible = [op["id"] for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"}]
    mono = {"node_to_subgraph": {n: 0 for n in eligible},
            "core_schedules": [[0] if eligible else []] + [[] for _ in range(args.cores - 1)]}
    candidates = [("official_stub", baseline), ("single_task", mono),
                  ("fixed_blocks_random_core", partition)]
    proposal_start = time.perf_counter()
    try:
        placed = place_by_local_duration(graph, partition, settings, waits)
        candidates.append(("fixed_blocks_local_finish", placed))
        proposal_error = None
    except (ValueError, RuntimeError) as exc:
        proposal_error = str(exc)
    proposal_seconds = time.perf_counter() - proposal_start
    structure_diagnostics = {}
    if args.structural:
        for kind in ("chain", "component"):
            start = time.perf_counter()
            try:
                structural = structural_partition(graph, args.cores, kind)
                structural = place_by_local_duration(graph, structural, settings, waits)
                candidates.append((kind + "_local_finish", structural))
                if kind == "chain":
                    for limit, protect in ((32, True), (128, True), (128, False)):
                        name = f"chain_cover{limit}_{'protected' if protect else 'unguarded'}"
                        fused, diagnostic = fuse_covers(graph, structural, limit, protect)
                        candidates.append((name, fused))
                        structure_diagnostics[name] = diagnostic
                structure_diagnostics[kind] = {"seconds": time.perf_counter() - start}
            except (ValueError, RuntimeError) as exc:
                structure_diagnostics[kind] = {"error": str(exc), "seconds": time.perf_counter() - start}
    results = []
    for name, plan in candidates:
        folder = out / name
        folder.mkdir()
        plan_path, result_path = folder / "plan.json", folder / "result.json"
        save(plan_path, plan)
        cmd = [sys.executable, "-B", str(OFFICIAL / "code/multicore_cut_evaluate_problem_1.py"),
               str(graph_path), str(plan_path), "--config", str(config), "-o", str(result_path),
               "--trace-output", str(folder / "trace.json"), "--log-output", str(folder / "summary.log")]
        start = time.perf_counter()
        row = {"candidate": name, "plan_sha256": sha(plan_path)}
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
            (folder / "stdout.txt").write_text(run.stdout)
            (folder / "stderr.txt").write_text(run.stderr)
            row.update(status="ok" if run.returncode == 0 else "evaluator_error", returncode=run.returncode)
            if run.returncode == 0:
                result = json.loads(result_path.read_text())
                row.update(makespan=result["makespan"], data_movement_bytes=result["data_movement_bytes"],
                           task_count=len(result["step3_by_task"]))
        except subprocess.TimeoutExpired:
            row["status"] = "timeout"
        row["official_cli_seconds"] = time.perf_counter() - start
        # Store portable commands instead of personal paths in committed receipts.
        row["command"] = ["python", "-B", "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
                          str(graph_path.relative_to(ROOT)), str(plan_path.relative_to(ROOT)),
                          "--config", "data/raw/a/official/data/config.txt", "-o", str(result_path.relative_to(ROOT)),
                          "--trace-output", str((folder / "trace.json").relative_to(ROOT)),
                          "--log-output", str((folder / "summary.log").relative_to(ROOT))]
        results.append(row)
    valid = [r for r in results if r["status"] == "ok"]
    best = min(valid, key=lambda r: r["makespan"]) if valid else None
    if best:
        save(out / "best_plan.json", json.loads((out / best["candidate"] / "plan.json").read_text()))
    manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_text())
    summary = {
        "scope": "Single public development case; local macOS CPU reproduction, not a general performance claim",
        "problem": 1, "graph": str(graph_path.relative_to(ROOT)), "graph_sha256": sha(graph_path),
        "config_sha256": sha(config), "official_code_hash": manifest["official_code_hash"],
        "prototype_sha256": sha(Path(__file__)), "uv_lock_sha256": sha(ROOT / "uv.lock"),
        "structure_sha256": sha(Path(__file__).with_name("structure.py")),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "prototype_working_tree": True, "python": sys.version, "platform": platform.platform(),
        "parameters": {"cores": args.cores, "seed": args.seed, "block_size": args.block_size, "timeout_seconds": args.timeout},
        "proposal_seconds": proposal_seconds, "proposal_error": proposal_error,
        "structure_diagnostics": structure_diagnostics,
        "selection": "minimum successful official Q1 CLI makespan; no proxy-based rejection",
        "best_candidate": best["candidate"] if best else None, "results": results,
    }
    save(out / "summary.json", summary)
    print(json.dumps({"best": summary["best_candidate"], "results": [
        {k: r.get(k) for k in ("candidate", "status", "makespan", "task_count")} for r in results]}, indent=2))


if __name__ == "__main__":
    main()
