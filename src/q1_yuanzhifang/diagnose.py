"""Read-only P1 computation/Task-gate lower bounds on existing plans.

Follows Pro4 R4A-10/11. No local compilation or E0/E1/E2 invocation.
The bound is plan-dependent; it is not a lower bound over all partitions.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from construct import OFFICIAL, topo, _build_op_adjacency
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order
from multicore_cut_evaluate_problem_1 import read_scene_a_config


def lower_bounds(graph, plan, waits):
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    # Task dependencies follow the official contracted graph in `view`, but
    # within a rebuilt Task an original COPY bridge is removed, not retained.
    # Use only original direct/tensor compute edges for its local critical path.
    # Counterexample and source: captain Q1_LOWER_BOUNDS.md @ 170132b127d6.
    full_pred, full_succ = _build_op_adjacency(graph)
    pred = {u: full_pred[u] & ops.keys() for u in ops}
    succ = {u: full_succ[u] & ops.keys() for u in ops}
    mapping = view["mapping"]
    local_path, loads, global_loads = {}, defaultdict(lambda: defaultdict(int)), defaultdict(int)
    for u in topo(ops, succ):
        task, cost, pipe = mapping[u], max(1, ops[u]["cycles"]), ops[u]["pipe"]
        local_path[u] = cost + max((local_path[p] for p in pred[u] if mapping[p] == task), default=0)
        loads[task][pipe] += cost
        global_loads[pipe] += cost
    duration = {t: max(max(loads[t].values(), default=0),
                       max((local_path[u] for u in view["nodes_by_subgraph"][t]), default=0))
                for t in view["subgraph_ids"]}
    owner = view["core_by_subgraph"]
    edges = {}
    for a, b in view["dependency_pairs"]:
        edges[a, b] = waits["task_cross_core_wait_cycles"] if owner[a] != owner[b] else 0
    for order in plan["core_schedules"]:
        for a, b in zip(order, order[1:]):
            edges[a, b] = max(edges.get((a, b), 0), waits["task_same_core_wait_cycles"])
    tsucc = {t: set() for t in duration}
    tpred = {t: set() for t in duration}
    for a, b in edges:
        tsucc[a].add(b)
        tpred[b].add(a)
    end, witness = {}, {}
    for t in topo(duration, tsucc):
        if tpred[t]:
            p = max(tpred[t], key=lambda p: (end[p] + edges[p, t], -p))
            start, witness[t] = end[p] + edges[p, t], p
        else:
            start, witness[t] = 0, None
        end[t] = start + duration[t]
    last = max(end, key=end.get) if end else None
    path = []
    while last is not None:
        path.append(last)
        last = witness[last]
    path.reverse()
    gate_cycles = sum(edges[a, b] for a, b in zip(path, path[1:]))
    return {"task_gate_lower_bound_cycles": max(end.values(), default=0),
            "global_pipe_work_lower_bound_cycles": max(global_loads.values(), default=0) / len(plan["core_schedules"]),
            "witness_tasks": path, "witness_compute_cycles": sum(duration[t] for t in path),
            "witness_gate_cycles": gate_cycles, "tasks_per_core": list(map(len, plan["core_schedules"])),
            "scope": "Task-gate bound is for this fixed plan only; global pipe bound applies to all plans at this core count. Neither includes DDR/spill."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("plan", type=Path)
    p.add_argument("--config", type=Path, default=OFFICIAL / "data/config.txt")
    args = p.parse_args()
    print(json.dumps(lower_bounds(json.loads(args.graph.read_bytes()), json.loads(args.plan.read_bytes()),
                                  read_scene_a_config(str(args.config))), indent=2))


if __name__ == "__main__":
    main()
