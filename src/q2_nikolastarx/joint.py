"""Keep a strong assignment and construct singleton priority schedules.

This is a compute-DAG heuristic, not a FIFO/memory feasibility certificate.
The matching official P2 evaluator remains the acceptance oracle.
"""
from __future__ import annotations

import heapq
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from schedule_step3 import op_pipe  # noqa: E402


class FixedAssignment:
    def __init__(self, graph: dict, parent: dict):
        view = derive_multicore_plan(graph, parent)
        self.graph = graph
        self.parent = parent
        self.ids = list(view["mapping"])
        self.cores = view["num_cores"]
        self.owner = {op: view["core_by_subgraph"][sg]
                      for op, sg in view["mapping"].items()}
        self.ops = {op["id"]: op for op in graph["ops"] if op["id"] in self.owner}
        _, full = _build_op_adjacency(graph)
        self.preds, self.succs = _contract_excluded_copy_nodes(self.ids, full)
        self.topo = self.order("id")
        self.tail = {}
        for op in reversed(self.topo):
            self.tail[op] = max(1, self.ops[op]["cycles"]) + max(
                (self.tail[s] for s in self.succs[op]), default=0)

    def order(self, policy: str) -> list[int]:
        if policy not in {"id", "critical32", "critical", "earliest_start"}:
            raise ValueError(f"unknown policy: {policy}")
        degree = {op: len(self.preds[op]) for op in self.ids}
        ready = [op for op in self.ids if degree[op] == 0]
        heapq.heapify(ready)
        finish = {}
        available = defaultdict(int)
        ordered = []

        def start(op):
            return max(available[self.owner[op], op_pipe(self.ops[op])],
                       max((finish[p] for p in self.preds[op]), default=0))

        while ready:
            if policy == "id":
                op = heapq.heappop(ready)
            elif policy == "critical32":
                # Reproduce Fang's ready-window restriction for a controlled
                # assignment x ordering experiment, not a new claimed policy.
                window = [heapq.heappop(ready) for _ in range(min(32, len(ready)))]
                op = min(window, key=lambda n: (-self.tail[n], n))
                for other in window:
                    if other != op:
                        heapq.heappush(ready, other)
            else:
                key = (lambda n: (-self.tail[n], n)) if policy == "critical" else (
                    lambda n: (start(n), -self.tail[n], n))
                op = min(ready, key=key)
                ready.remove(op)
                heapq.heapify(ready)
            if policy == "earliest_start":
                finish[op] = start(op) + max(1, self.ops[op]["cycles"])
                available[self.owner[op], op_pipe(self.ops[op])] = finish[op]
            ordered.append(op)
            for successor in sorted(self.succs[op]):
                degree[successor] -= 1
                if degree[successor] == 0:
                    heapq.heappush(ready, successor)
        if len(ordered) != len(self.ids):
            raise ValueError("contracted compute graph contains a cycle")
        return ordered

    def build(self, policy: str) -> dict:
        order = self.order(policy)
        # Stable singleton IDs and original mapping insertion order for every
        # policy. Only schedules change between these singleton candidates.
        identity = {op: i for i, op in enumerate(self.ids)}
        schedules = [[] for _ in range(self.cores)]
        for op in order:
            schedules[self.owner[op]].append(identity[op])
        plan = {"node_to_subgraph": {str(op): identity[op] for op in self.ids},
                "core_schedules": schedules}
        derive_multicore_plan(self.graph, plan)
        return plan
