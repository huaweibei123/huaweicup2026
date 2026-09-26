"""Analytical P2 lower bounds and graph census; zero evaluator calls.

Bounds relax placement, extra COPY, FIFO, capacity and competition. The proof
domain is nonempty graphs with at most one original producer per tensor, as in
the frozen 100 cases. See THEORY_REVIEW.md for spill/FIFO causality conditions.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

from .construct import Index, PIPES, ROOT
from .energetic import pipe_bound


def graph_bounds(graph, cores, bandwidth=60, energetic=False):
    index = Index(graph)
    if not index.ops:
        raise ValueError("bound proof requires nonempty eligible operations")
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, (int, float)) or not math.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError("positive finite bandwidth required")
    cores = tuple(cores)
    if not cores or any(type(k) is not int or not 1 <= k <= 5 for k in cores):
        raise ValueError("official core counts must be integers in 1..5")
    original = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    if any('logical_tid' in t for t in tensors.values()):
        raise ValueError('bound proof requires original tensors without logical aliases')
    producers, consumers = defaultdict(set), defaultdict(set)
    guaranteed_pred = {u: set() for u in index.ops}
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in original and v in tensors:
            producers[v].add(u)
        if u in tensors and v in original:
            consumers[u].add(v)
        if u in index.ops and v in index.ops and u != v:
            guaranteed_pred[v].add(u)
    if any(len(ops) > 1 for ops in producers.values()):
        raise ValueError("bound proof requires at most one original producer per tensor")
    input_delay, output_delay = defaultdict(int), defaultdict(int)
    mandatory_in, mandatory_out = [], []
    for tid, tensor in tensors.items():
        prod = producers[tid] & index.ops.keys()
        cons = consumers[tid] & index.ops.keys()
        duration = max(1, math.ceil(tensor["size"] / bandwidth))
        for op in cons:
            guaranteed_pred[op].update(prod - {op})
        if cons and not prod:
            mandatory_in.append((tid, duration, tensor["size"]))
            for op in cons:
                input_delay[op] = max(input_delay[op], duration)
        has_original_out = any(original[op]["op"] == "COPY_OUT" for op in consumers[tid])
        if prod and (has_original_out or not cons):
            mandatory_out.append((tid, duration, tensor["size"]))
            for op in prod:
                output_delay[op] = max(output_delay[op], duration)
    finish, compute_finish = {}, {}
    for op in index.order:
        work = index.duration(op)
        finish[op] = max(input_delay[op], max((finish[p] for p in guaranteed_pred[op]), default=0)) + work
        compute_finish[op] = max((compute_finish[p] for p in guaranteed_pred[op]), default=0) + work
    chain = max((finish[o] + output_delay[o] for o in index.ops), default=0)
    jobs_by_pipe = defaultdict(list)
    if energetic:
        guaranteed_succ = {u: set() for u in index.ops}
        for u, parents in guaranteed_pred.items():
            for parent in parents:
                guaranteed_succ[parent].add(u)
        tail = {}
        for u in reversed(index.order):
            tail[u] = max(output_delay[u], max(
                (index.duration(v) + tail[v] for v in guaranteed_succ[u]), default=0))
        for u in index.order:
            work = index.duration(u)
            jobs_by_pipe[index.ops[u]['pipe']].append((finish[u] - work, tail[u], work))
    totals = {pipe: sum(w[pipe] for w in index.work) for pipe in PIPES}
    compulsory_ddr = sum(d for _, d, _ in mandatory_in + mandatory_out)
    by_core = {}
    for k in cores:
        load_bound = max((work + k - 1) // k for work in totals.values())
        by_core[str(k)] = {"pipe_work": load_bound, "path_with_endpoint_copies": chain,
                           "compulsory_ddr_work": compulsory_ddr,
                           "lower_bound_cycles": max(load_bound, chain, compulsory_ddr)}
        if energetic:
            certificates = {p: pipe_bound(jobs, k) for p, jobs in jobs_by_pipe.items()}
            strongest = max(c['lower_bound_cycles'] for c in certificates.values())
            by_core[str(k)]['release_tail_pipe_certificates'] = certificates
            by_core[str(k)]['lower_bound_cycles'] = max(
                by_core[str(k)]['lower_bound_cycles'], strongest)
    return {"eligible_ops": len(index.ops), "components": len(index.components),
            "max_component_ops": max(map(len, index.components)),
            "pipe_work_cycles": totals, "compute_critical_path": max(compute_finish.values()),
            "contracted_edges_not_used_in_bound": sum(len(index.pred[u] - guaranteed_pred[u]) for u in index.ops),
            "compulsory_copy_bytes": sum(size for _, _, size in mandatory_in + mandatory_out),
            "sources": sum(not index.pred[o] for o in index.ops),
            "sinks": sum(not index.succ[o] for o in index.ops),
            "joins": sum(len(index.pred[o]) > 1 for o in index.ops),
            "forks": sum(len(index.succ[o]) > 1 for o in index.ops),
            "indegree_histogram": dict(sorted(Counter(map(len, index.pred.values())).items())),
            "outdegree_histogram": dict(sorted(Counter(map(len, index.succ.values())).items())),
            "by_core": by_core}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--energetic", action="store_true",
                        help="Add exact release/tail threshold pipe-work bounds")
    args = parser.parse_args()
    start = time.perf_counter()
    from evaluation_validation import read_required_settings
    config = ROOT / "data/raw/a/official/data/config.txt"
    bandwidth = read_required_settings(config, "bandwidth", ("bandwidth",))["bandwidth"]
    config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    rows = []
    for path in sorted((ROOT / "data/raw/a/official/data").glob("case_*.json")):
        raw = path.read_bytes()
        case = path.stem[-3:]
        baseline = json.loads((ROOT / "results/benchmark-board/official-singlecore-20260924" / case / "run.json").read_bytes())
        if hashlib.sha256(raw).hexdigest() != baseline["graph_sha256"]:
            raise ValueError("graph/baseline identity mismatch")
        if config_hash != baseline["config_sha256"]:
            raise ValueError("config/baseline identity mismatch")
        row = {"case_id": case, "graph_sha256": baseline["graph_sha256"],
               "baseline_cycles": baseline["makespan_cycles"],
               **graph_bounds(json.loads(raw), range(1, 6), bandwidth, args.energetic)}
        for k, bounds in row["by_core"].items():
            bounds["speedup_upper_bound"] = row["baseline_cycles"] / bounds["lower_bound_cycles"]
        rows.append(row)
    if len(rows) != 100:
        raise ValueError("requires all 100 official cases")
    result = {"scope": "Analytical relaxations only, no construction/E0/E1/E2 calls. Bounds require the frozen P2 source, nonempty eligible graph, at most one original producer per tensor, fixed DDR bandwidth 60 and one slot per pipe. See THEORY_REVIEW.md for spill/FIFO causality; not an attainability proof.",
              "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "method": "release_tail_pipe_thresholds" if args.energetic else "basic_resource_and_path",
              "config_sha256": config_hash,
              "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                for p in ('src/q2/feedback/bounds.py', 'src/q2/feedback/energetic.py',
                                          'src/q2/feedback/construct.py')},
              "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
              "rows": rows, "wall_seconds": time.perf_counter() - start,
              "mean_speedup_upper_bounds": {str(k): sum(r["by_core"][str(k)]["speedup_upper_bound"] for r in rows) / 100 for k in range(1, 6)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"graphs": 100, "wall_seconds": result["wall_seconds"], "mean_speedup_upper_bounds": result["mean_speedup_upper_bounds"]}))


if __name__ == "__main__":
    main()
