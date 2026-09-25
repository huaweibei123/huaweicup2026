"""Deterministic topological contiguous-block baseline, not an optimized search."""
from __future__ import annotations

import argparse
import heapq
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official/code"


def contiguous_plan(graph: dict, cores: int) -> dict:
    if cores < 1:
        raise ValueError("cores must be positive")
    # Frozen structural helpers only: no Q2 evaluation or mutable external checkout.
    sys.path.insert(0, str(OFFICIAL))
    try:
        from stub_multicore_cut_and_schedule import (
            _build_op_adjacency, _contract_excluded_copy_nodes,
            derive_multicore_plan,
        )
        from evaluation_validation import validate_graph
    finally:
        sys.path.pop(0)
    validate_graph(graph)
    eligible = sorted(o["id"] for o in graph["ops"]
                      if o["op"] not in {"COPY_IN", "COPY_OUT"})
    _, full_succs = _build_op_adjacency(graph)
    preds, succs = _contract_excluded_copy_nodes(eligible, full_succs)
    degree = {op: len(preds[op]) for op in eligible}
    ready = [op for op in eligible if degree[op] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        op = heapq.heappop(ready)
        order.append(op)
        for successor in sorted(succs[op]):
            degree[successor] -= 1
            if degree[successor] == 0:
                heapq.heappush(ready, successor)
    if len(order) != len(eligible):
        raise ValueError("non-COPY dependency graph has a cycle")
    weights = {o["id"]: max(1, o["cycles"]) for o in graph["ops"]}
    total = sum(weights[op] for op in order)
    mapping, schedules = {}, [[] for _ in range(cores)]
    prefix = 0
    for op in order:
        # Integer cumulative-work thresholds; no assumed real Task cost.
        core = min(cores - 1, prefix * cores // max(1, total))
        if not schedules[core]:
            schedules[core].append(core)
        mapping[str(op)] = core
        prefix += weights[op]
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    derive_multicore_plan(graph, plan)  # Structural validity, NOT Q2 execution proof.
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    plan = contiguous_plan(graph, args.cores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
