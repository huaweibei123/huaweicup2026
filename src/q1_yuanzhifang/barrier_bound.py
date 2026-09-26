"""Universal P1 computation bounds using comparable-vertex barriers.

No plan, Task compiler, or evaluator. COPY bridges are NOT contracted.
See BARRIER_BOUND.md for the gate-capacity proof and assumptions.
"""
from __future__ import annotations

from collections import defaultdict
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from construct import OFFICIAL, topo, _build_op_adjacency
from multicore_cut_evaluate_problem_1 import read_scene_a_config


def gate_capacity_inverse(work, cores, lag, ends):
    """Minimum D with W <= D+(k-1)*max(D-ends*lag,0)."""
    if any(type(x) is not int for x in (work, cores, lag, ends)):
        raise ValueError("Integer work, capacity, lag and endpoint count required")
    if work < 0 or cores < 1 or lag < 0 or ends not in (0, 1, 2):
        raise ValueError("Invalid resource-bound argument")
    loss = ends * lag
    return work if work <= loss else (work + (cores - 1) * loss + cores - 1) // cores


def comparable_barriers(order, pred, succ):
    """Linear scans: unique prefix sink AND unique suffix source."""
    sinks, prefix = set(), set()
    for u in order:
        sinks.difference_update(pred[u]); sinks.add(u)
        if len(sinks) == 1:
            prefix.add(u)
    sources, result = set(), []
    for u in reversed(order):
        sources.difference_update(succ[u]); sources.add(u)
        if len(sources) == 1 and u in prefix:
            result.append(u)
    return list(reversed(result))


def lower_bound(graph, cores, cross_wait=1000):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    if type(cross_wait) is not int or cross_wait < 0:
        raise ValueError("cross_wait must be a nonnegative integer")
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    full_pred, full_succ = _build_op_adjacency(graph)
    pred = {u: full_pred[u] & ops.keys() for u in ops}
    succ = {u: full_succ[u] & ops.keys() for u in ops}
    order = topo(ops, succ)
    owner, components = {}, []
    for u in order:
        if u in owner:
            continue
        owner[u] = len(components)
        stack, members = [u], []
        while stack:
            v = stack.pop(); members.append(v)
            for w in pred[v] | succ[v]:
                if w not in owner:
                    owner[w] = owner[u]; stack.append(w)
        components.append([])
    for u in order:
        components[owner[u]].append(u)
    duration = {u: max(1, ops[u]["cycles"]) for u in ops}
    global_work = defaultdict(int)
    for u in order:
        global_work[ops[u]["pipe"]] += duration[u]
    reports = []
    for nodes in components:
        barriers = comparable_barriers(nodes, pred, succ)
        barrier_set = set(barriers)
        segments, pending, previous = [], [], None

        def flush(next_barrier):
            loads, longest = defaultdict(int), {}
            members = set(pending)
            for u in pending:
                loads[ops[u]["pipe"]] += duration[u]
                longest[u] = duration[u] + max((longest[v] for v in pred[u] if v in members), default=0)
            ends = int(previous is not None) + int(next_barrier is not None)
            pipe_bounds = {p: gate_capacity_inverse(w, cores, cross_wait, ends) for p, w in loads.items()}
            path = max(longest.values(), default=0)
            segments.append({"previous_barrier": previous, "next_barrier": next_barrier,
                             "compute_ops": len(pending), "pipe_work_cycles": dict(loads),
                             "pipe_gate_bounds_cycles": pipe_bounds, "internal_cp_cycles": path,
                             "interval_lower_bound_cycles": max([path, *pipe_bounds.values()])})

        for u in nodes:
            if u in barrier_set:
                flush(u); previous = u; pending = []
            else:
                pending.append(u)
        flush(None)
        barrier_work = sum(duration[u] for u in barriers)
        reports.append({"anchor": min(nodes), "compute_ops": len(nodes), "barriers": barriers,
                        "barrier_compute_cycles": barrier_work, "segments": segments,
                        "lower_bound_cycles": barrier_work + sum(x["interval_lower_bound_cycles"] for x in segments)})
    load = max(((w + cores - 1) // cores for w in global_work.values()), default=0)
    return {"cores": cores, "cross_core_wait_cycles": cross_wait,
            "global_pipe_load_bound_cycles": load,
            "lower_bound_cycles": max([load, *(x["lower_bound_cycles"] for x in reports)]),
            "components": reports,
            "scope": "All legal P1 plans under retained compute dependencies and fixed Task cross-core gates; no COPY bridge contraction. Ignores DDR, spill, same-core waits, FIFO. Not achievable performance or full optimality proof."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graphs", nargs="+", type=Path)
    p.add_argument("--cores", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    p.add_argument("--config", type=Path, default=OFFICIAL / "data/config.txt")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    waits = read_scene_a_config(str(args.config))
    rows = []
    for path in args.graphs:
        raw = path.read_bytes(); graph = json.loads(raw)
        rows.append({"input_name": path.name, "input_sha256": hashlib.sha256(raw).hexdigest(),
                     "bounds": [lower_bound(graph, k, waits["task_cross_core_wait_cycles"]) for k in args.cores]})
    report = {"kind": "universal_barrier_gate_lower_bounds_not_performance", "schema_version": 1,
              "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
              "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(report, out, ensure_ascii=False, indent=2); out.write("\n")
    print(json.dumps([{ "input": row["input_name"], "bounds": {b["cores"]: b["lower_bound_cycles"] for b in row["bounds"]}} for row in rows]))


if __name__ == "__main__":
    main()
