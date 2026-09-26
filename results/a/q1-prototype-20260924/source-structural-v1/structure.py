"""Q1 structural candidate families, never a makespan evaluator.

Chain packets and export-protected cover contraction follow the Pro1 R3 ideas
archived in results/a/pro-research-20260924. This is a separate implementation.
All dependency edges include paths through excluded COPY operations.
"""
from __future__ import annotations

import heapq

from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)


def topological(nodes, successors, priority=None):
    degree = {v: 0 for v in nodes}
    for vs in successors.values():
        for v in vs:
            degree[v] += 1
    priority = priority or dict.fromkeys(nodes, 0)
    ready = [(-priority[v], v) for v in nodes if degree[v] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, v = heapq.heappop(ready)
        order.append(v)
        for u in sorted(successors[v]):
            degree[u] -= 1
            if degree[u] == 0:
                heapq.heappush(ready, (-priority[u], u))
    if len(order) != len(nodes):
        raise ValueError("Combined dependency and core-order graph contains a cycle")
    return order


def structural_partition(graph, cores, kind):
    """Whole weak components or nonbranching chains, critical-tail ordered."""
    ops = {op["id"]: op for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    nodes = sorted(ops)
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(nodes, full)
    parent = {v: v for v in nodes}

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for u in nodes:
        for v in sorted(succ[u]):
            if kind == "component" or (kind == "chain" and len(succ[u]) == 1 and len(pred[v]) == 1):
                a, b = find(u), find(v)
                parent[max(a, b)] = min(a, b)
    groups = {}
    for v in nodes:
        groups.setdefault(find(v), []).append(v)
    successors = {g: set() for g in groups}
    for u in nodes:
        for v in succ[u]:
            a, b = find(u), find(v)
            if a != b:
                successors[a].add(b)
    order = topological(groups, successors)
    # Compute sum is only a dispatch priority; local E0 compilation supplies
    # the duration estimate later. It does not claim M/V serialization.
    tail = {}
    for g in reversed(order):
        tail[g] = sum(max(1, ops[v]["cycles"]) for v in groups[g]) + max(
            (tail[h] for h in successors[g]), default=0)
    order = topological(groups, successors, tail)
    index = {g: i for i, g in enumerate(order)}
    plan = {"node_to_subgraph": {v: index[find(v)] for v in nodes},
            "core_schedules": [list(range(k, len(order), cores)) for k in range(cores)]}
    derive_multicore_plan(graph, plan)
    return plan


def fuse_covers(graph, plan, max_ops, protect_exports):
    """Contract same-core adjacent covers of the FULL augmented Task DAG.

    Absence of an alternative a->...->b path makes contraction acyclic.
    Export protection is a heuristic veto, not a guarantee of improvement.
    """
    view = derive_multicore_plan(graph, plan)
    groups = {g: set(vs) for g, vs in view["nodes_by_subgraph"].items()}
    orders = [list(vs) for vs in plan["core_schedules"]]
    owner = {g: k for k, vs in enumerate(orders) for g in vs}
    edges = set(view["dependency_pairs"])
    edges.update((a, b) for vs in orders for a, b in zip(vs, vs[1:]))
    merges = []
    changed = True
    while changed:
        changed = False
        successors = {g: set() for g in groups}
        for a, b in edges:
            successors[a].add(b)
        rank = {v: i for i, v in enumerate(topological(groups, successors))}
        for k, order in enumerate(orders):
            for a, b in zip(order, order[1:]):
                if len(groups[a]) + len(groups[b]) > max_ops:
                    continue
                if protect_exports and any(owner[v] != k for v in successors[a]):
                    continue
                pending = list(successors[a] - {b})
                seen = set()
                while pending:
                    v = pending.pop()
                    if v in seen or rank[v] > rank[b]:
                        continue
                    seen.add(v)
                    pending.extend(successors[v] - seen)
                if b in seen:
                    continue
                edges = {(a if u == b else u, a if v == b else v) for u, v in edges
                         if (a if u == b else u) != (a if v == b else v)}
                groups[a].update(groups.pop(b))
                order.remove(b)
                owner.pop(b)
                merges.append([a, b])
                changed = True
                break
            if changed:
                break
    result = {"node_to_subgraph": {v: g for g, vs in groups.items() for v in sorted(vs)},
              "core_schedules": orders}
    derive_multicore_plan(graph, result)
    return result, {"merges": merges, "max_ops": max_ops, "protect_exports": protect_exports}
