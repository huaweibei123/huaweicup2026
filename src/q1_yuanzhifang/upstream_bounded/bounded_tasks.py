"""Direct P1 frontier construction with bounded independent-component Tasks.

Only oversized Tasks are split, and only between independent compute
components. This bounds common Task sizes without splitting a dependence
chain. It is a compilation-cost heuristic, not a capacity or timing guarantee.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from .tree_frontier import construct as frontier  # noqa: E402
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import validate_task_order  # noqa: E402


def split_large_tasks(graph, plan, trigger_ops=4096, chunk_ops=1024):
    if type(trigger_ops) is not int or type(chunk_ops) is not int or not 1 <= chunk_ops <= trigger_ops:
        raise ValueError("Require integer 1 <= chunk_ops <= trigger_ops")
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    large = {t for t, nodes in view["nodes_by_subgraph"].items() if len(nodes) > trigger_ops}
    info = {"trigger_ops": trigger_ops, "chunk_ops": chunk_ops, "split_tasks": [],
            "oversize_indivisible_components": [], "tasks_before": len(view["subgraph_ids"])}
    if not large:
        info["tasks_after"] = info["tasks_before"]
        return plan, info
    mapping = dict(view["mapping"])
    _, full = _build_op_adjacency(graph)
    _, succ = _contract_excluded_copy_nodes(sorted(mapping), full)
    parent = {u: u for u in mapping if mapping[u] in large}

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for u in parent:
        for v in succ[u]:
            if mapping[v] == mapping[u]:
                a, b = find(u), find(v)
                if a != b:
                    parent[max(a, b)] = min(a, b)
    groups = defaultdict(lambda: defaultdict(list))
    for u in parent:
        groups[mapping[u]][find(u)].append(u)
    replacements = {}
    next_id = max(view["subgraph_ids"]) + 1
    for task in sorted(large):
        components = sorted(groups[task].values(), key=lambda ns: (-len(ns), min(ns)))
        bins = []
        for nodes in components:
            if len(nodes) > chunk_ops:
                info["oversize_indivisible_components"].append({"task": task, "ops": len(nodes)})
            chosen = next((b for b in bins if len(b) + len(nodes) <= chunk_ops), None)
            if chosen is None:
                chosen = []
                bins.append(chosen)
            chosen.extend(nodes)
        assigned = [task]
        for nodes in bins[1:]:
            assigned.append(next_id)
            for u in nodes:
                mapping[u] = next_id
            next_id += 1
        replacements[task] = assigned
        info["split_tasks"].append({"original_task": task, "new_tasks": assigned,
                                    "chunk_compute_ops": list(map(len, bins))})
    # Replacing a vertex by a chain at its original position preserves the
    # augmented Task DAG: all old inter-Task edges retain their block order.
    result = {
        "node_to_subgraph": {u: mapping[int(u)] for u in plan["node_to_subgraph"]},
        "core_schedules": [[part for t in order for part in replacements.get(t, [t])]
                           for order in plan["core_schedules"]],
    }
    after = derive_multicore_plan(graph, result)
    validate_task_order(after)
    info["tasks_after"] = len(after["subgraph_ids"])
    return result, info


def construct(graph, cores, packet_factor=4, trigger_ops=4096, chunk_ops=1024):
    initial, base = frontier(graph, cores, packet_factor)
    plan, chunks = split_large_tasks(graph, initial, trigger_ops, chunk_ops)
    return plan, {"algorithm_id": "q1-bounded-component-tasks", "variant": "frontier-then-independent-chunks",
                  "base": base, "chunks": chunks,
                  "scope": "Structural validation only; bounds on common Task size are not E0, spill or runtime guarantees"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cores", type=int, required=True)
    p.add_argument("--packet-factor", type=int, default=4)
    p.add_argument("--trigger-ops", type=int, default=4096)
    p.add_argument("--chunk-ops", type=int, default=1024)
    p.add_argument("--diagnostics", type=Path)
    args = p.parse_args()
    if args.output.exists() or (args.diagnostics and args.diagnostics.exists()):
        raise FileExistsError("Refuse to overwrite experiment artifacts")
    plan, d = construct(json.loads(args.graph.read_text()), args.cores, args.packet_factor,
                        args.trigger_ops, args.chunk_ops)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(plan, f, separators=(",", ":"))
        f.write("\n")
    if args.diagnostics:
        args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        with args.diagnostics.open("x") as f:
            json.dump(d, f, indent=2)
            f.write("\n")
    print(json.dumps(d))


if __name__ == "__main__":
    main()
