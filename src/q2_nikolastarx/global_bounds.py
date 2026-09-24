"""Static, assignment-independent P2 certificates; never calls an evaluator.

Proofs and the restricted precedence domain are in OPTIMALITY_BOUNDS.md.
These bounds do not claim attainable schedules or a bound on solver wall time.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official/code"
sys.path.insert(0, str(OFFICIAL))
from evaluation_validation import validate_graph  # noqa: E402
from multicore_cut_evaluate_problem_1 import (  # noqa: E402
    _copy_traffic_bytes, _original_tensor_views,
)
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes,
)

PIPES = ("PIPE_MTE2", "PIPE_MTE3", "PIPE_M", "PIPE_V")
SOURCES = (
    "evaluation_validation.py", "stub_multicore_cut_and_schedule.py",
    "multicore_cut_evaluate_problem_1.py", "multicore_cut_evaluate_problem_2.py",
    "schedule_step2.py", "schedule_step3.py",
)


def _ceil_div(n, k):
    return (n + k - 1) // k


def indivisible_work_bound(durations, cores):
    """Necessary load on k identical slots; jobs cannot split across slots.

    For m=(q-1)k+1 largest jobs, some slot has >=q of them. The q smallest
    in those m give a lower bound on that slot's load. No jobs are summed
    twice within a witness; different witnesses are combined by max only.
    """
    ordered = sorted(durations, reverse=True)
    prefix = [0]
    for duration in ordered:
        prefix.append(prefix[-1] + duration)
    best = {"cycles": _ceil_div(prefix[-1], cores), "kind": "total_work"}
    for q in range(1, _ceil_div(len(ordered), cores) + 1):
        m = (q - 1) * cores + 1
        value = prefix[m] - prefix[m - q]
        if value > best["cycles"]:
            best = {"cycles": value, "kind": "indivisible_pigeonhole",
                    "largest_jobs": m, "jobs_on_one_core": q,
                    "smallest_q_sum": value}
    return best


def _window_bound(nodes, duration, head, tail, cores):
    """O(n log n) selected energetic inequalities, no search over plans.

    For each head (then tail) threshold, take every operation above it.
    All selected intervals fit inside [min head, C - min tail].
    """
    best = {"cycles": 0}
    for kind, left, right in (("head", head, tail), ("tail", tail, head)):
        ordered = sorted(nodes, key=lambda u: (-left[u], u))
        work, minimum_other, count, i = 0, None, 0, 0
        while i < len(ordered):
            threshold = left[ordered[i]]
            while i < len(ordered) and left[ordered[i]] == threshold:
                node = ordered[i]
                work += duration[node]
                minimum_other = (right[node] if minimum_other is None
                                 else min(minimum_other, right[node]))
                count += 1
                i += 1
            value = threshold + _ceil_div(work, cores) + minimum_other
            if value > best["cycles"]:
                best = {"cycles": value, "threshold_kind": kind,
                        "threshold": threshold, "minimum_other": minimum_other,
                        "selected_ops": count, "selected_pipe_work": work}
    return best


def certify(graph, core_counts=(1, 2, 3, 4, 5)):
    """Return graph-wide necessary bounds or an explicit invalid-input abstention.

    The graph must pass the frozen official input validator. Only the work
    bounds are certified when a tensor has multiple eligible producers.
    Contracted edges through removed original COPY nodes are never assumed.
    """
    try:
        validate_graph(graph)
        if any(not isinstance(op.get("op"), str) for op in graph["ops"]):
            raise ValueError("every operation must have a string op type")
        if not core_counts or any(type(k) is not int or k < 1 for k in core_counts):
            raise ValueError("core counts must be positive integers")
    except (TypeError, ValueError, KeyError) as error:
        return {"supported": False, "reason": str(error)}
    ops = {o["id"]: o for o in graph["ops"]
           if o["op"] not in ("COPY_IN", "COPY_OUT")}
    duration = {u: max(1, op["cycles"]) for u, op in ops.items()}
    producers, consumers, _ = _original_tensor_views(graph)
    _, original_succ = _build_op_adjacency(graph)
    _, contracted = _contract_excluded_copy_nodes(ops, original_succ)
    succ = {u: original_succ[u] & ops.keys() for u in ops}
    pred = {u: set() for u in ops}
    for u in ops:
        for v in succ[u]:
            pred[v].add(u)
    removed_only = sorted((u, v) for u in ops for v in contracted[u] - succ[u])
    multi = sorted(t["id"] for t in graph["tensors"]
                   if len(producers.get(t["id"], set()) & ops.keys()) > 1)
    precedence_supported = not multi
    head, tail, critical_path, path_witness = {}, {}, None, []
    if precedence_supported:
        degree = {u: len(pred[u]) for u in ops}
        ready = [u for u in ops if degree[u] == 0]
        heapq.heapify(ready)
        order, previous = [], {}
        while ready:
            u = heapq.heappop(ready)
            order.append(u)
            source = max(pred[u], key=lambda v: (head[v] + duration[v], -v),
                         default=None)
            previous[u] = source
            head[u] = 0 if source is None else head[source] + duration[source]
            for v in succ[u]:
                degree[v] -= 1
                if degree[v] == 0:
                    heapq.heappush(ready, v)
        for u in reversed(order):
            tail[u] = max((duration[v] + tail[v] for v in succ[u]), default=0)
        last = max(ops, key=lambda u: (head[u] + duration[u], -u), default=None)
        critical_path = 0 if last is None else head[last] + duration[last]
        while last is not None:
            path_witness.append(last)
            last = previous[last]
        path_witness.reverse()
    groups = {pipe: [u for u in ops if ops[u]["pipe"] == pipe] for pipe in PIPES}
    work = {pipe: sum(duration[u] for u in groups[pipe]) for pipe in PIPES}
    mandatory_inputs, mandatory_outputs = [], []
    original_ops = {o["id"]: o for o in graph["ops"]}
    for tensor in graph["tensors"]:
        tid = tensor["id"]
        prod = producers.get(tid, set()) & ops.keys()
        cons = consumers.get(tid, set()) & ops.keys()
        if cons and not prod:
            mandatory_inputs.append((tid, tensor["size"]))
        has_copy_out = any(original_ops[u]["op"] == "COPY_OUT"
                           for u in consumers.get(tid, set()))
        if prod and (has_copy_out or not cons):
            mandatory_outputs.append((tid, tensor["size"]))
    mandatory_bytes = sum(size for _, size in mandatory_inputs + mandatory_outputs)
    original_bytes = _copy_traffic_bytes(graph)
    records = []
    for cores in core_counts:
        load = {p: indivisible_work_bound([duration[u] for u in groups[p]], cores)
                for p in PIPES}
        windows = ({p: _window_bound(groups[p], duration, head, tail, cores)
                    for p in PIPES} if precedence_supported else None)
        value = max([critical_path or 0] + [x["cycles"] for x in load.values()]
                    + ([x["cycles"] for x in windows.values()] if windows else []))
        records.append({"cores": cores, "makespan_lower_bound_cycles": value,
                        "pipe_load_bounds": load, "pipe_window_bounds": windows})
    return {
        "supported": True, "eligible_ops": len(ops), "pipe_work": work,
        "precedence_supported": precedence_supported,
        "precedence_domain": "at most one eligible producer per original tensor",
        "multiple_eligible_producer_tensor_ids": multi,
        "removed_copy_only_contracted_edge_count": len(removed_only),
        "removed_copy_only_contracted_edge_examples": removed_only[:8],
        "retained_compute_critical_path_cycles": critical_path,
        "critical_path_witness_op_ids": path_witness,
        "mandatory_boundary_io": {
            "input_tensor_count": len(mandatory_inputs),
            "output_tensor_count": len(mandatory_outputs),
            "scheduled_copy_bytes_lower_bound": mandatory_bytes,
            "original_graph_copy_bytes": original_bytes,
            "added_copy_bytes_lower_bound": mandatory_bytes - original_bytes,
            "ddr_time_bound_certified": False,
            "note": "Exact byte accounting; no floating DDR service-time bound asserted.",
        },
        "by_core_count": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph_directory", type=Path)
    parser.add_argument("--cores", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    records = []
    for path in sorted(args.graph_directory.glob("case_*.json")):
        raw = path.read_bytes()
        records.append({"graph_file": path.name,
                        "graph_sha256": hashlib.sha256(raw).hexdigest(),
                        **certify(json.loads(raw), args.cores)})
    data = {
        "scope": "Static necessary bounds only; E0/E1/E2 calls = 0; no optimality claim",
        "proof_document": "docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md",
        "official_source_sha256": {p: hashlib.sha256((OFFICIAL / p).read_bytes()).hexdigest()
                                   for p in SOURCES},
        "certificate_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "records": records,
        "static_wall_seconds": time.perf_counter() - started,
    }
    with args.output.open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
