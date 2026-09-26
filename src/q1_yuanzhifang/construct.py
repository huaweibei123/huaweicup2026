"""Deterministic P1 antichain packing; no evaluator or score-based search.

Components may be packed together because there are no computational paths
between them. Chain packets can instead be packed at equal quotient depth.
Every resulting dependency points to a later depth, so global level order
projected onto cores is an acyclic structural witness. This is NOT a proof of
execution feasibility, memory feasibility, or makespan improvement.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import heapq
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
sys.path.insert(0, str(OFFICIAL / "code"))
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import validate_task_order  # noqa: E402


def topo(nodes, successors):
    degree = dict.fromkeys(nodes, 0)
    for neighbours in successors.values():
        for v in neighbours:
            degree[v] += 1
    ready = [v for v in nodes if degree[v] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(successors[u]):
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    if len(order) != len(nodes):
        raise ValueError("Cyclic computational or quotient graph")
    return order


def packets(graph, mode):
    ops = {o["id"]: o for o in graph["ops"]
           if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
    order = topo(ops, succ)
    parent = {u: u for u in ops}

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for u in order:
        for v in sorted(succ[u]):
            if mode == "component-pack" or (len(succ[u]) == 1 and len(pred[v]) == 1):
                a, b = find(u), find(v)
                parent[max(a, b)] = min(a, b)
    groups = defaultdict(list)
    for u in sorted(ops):
        groups[find(u)].append(u)
    edges = {g: set() for g in groups}
    for u in order:
        for v in succ[u]:
            a, b = find(u), find(v)
            if a != b:
                edges[a].add(b)
    degree_order = topo(groups, edges)
    depth = dict.fromkeys(groups, 0)
    for u in degree_order:
        for v in edges[u]:
            depth[v] = max(depth[v], depth[u] + 1)
    return ops, groups, edges, depth, {u: find(u) for u in ops}


def construct(graph, cores, variant="chain-wave"):
    if isinstance(cores, bool) or not isinstance(cores, int) or cores < 1:
        raise ValueError("cores must be a positive integer")
    if variant not in {"chain-wave", "component-pack", "structural-switch"}:
        raise ValueError("Unknown construction variant")
    selected = variant
    if variant == "structural-switch":
        data = packets(graph, "component-pack")
        # A weak-component packing with fewer components than cores cannot
        # populate all cores. Otherwise preserve complete independent units.
        # This is a graph-only heuristic, not a makespan dominance theorem.
        selected = "component-pack" if len(data[1]) >= cores else "chain-wave"
        if selected == "chain-wave":
            data = packets(graph, selected)
    else:
        data = packets(graph, variant)
    ops, groups, edges, depth, packet_of = data
    # Per-pipe work totals are ranking heuristics, not E0 scores or an
    # execution model of the packet's internal critical path.
    work = {}
    for g, nodes in groups.items():
        loads = defaultdict(int)
        for u in nodes:
            loads[ops[u]["pipe"]] += ops[u]["cycles"]
        work[g] = dict(loads)
    tensor_ids = {t["id"] for t in graph["tensors"]}
    sizes = {t["id"]: t["size"] for t in graph["tensors"]}
    inputs = defaultdict(set)
    producers = defaultdict(set)
    consumers = defaultdict(set)
    for e in graph["edges"]:
        u, v = e["source"], e["target"]
        if u in ops and v in tensor_ids:
            producers[v].add(packet_of[u])
        elif u in tensor_ids and v in ops:
            consumers[u].add(packet_of[v])
    for t, gs in consumers.items():
        for g in gs - producers[t]:
            inputs[g].add(t)
    layers = defaultdict(list)
    for g in groups:
        layers[depth[g]].append(g)
    mapping, schedules, packet_core = {}, [[] for _ in range(cores)], {}
    previous_work = [0] * cores
    next_id = 0
    packet_pred = {g: set() for g in groups}
    for g, successors in edges.items():
        for v in successors:
            packet_pred[v].add(g)
    diagnostics = []
    for level in sorted(layers):
        bins = [[] for _ in range(cores)]
        loads = [defaultdict(int) for _ in range(cores)]
        shared = [set() for _ in range(cores)]
        layer_groups = sorted(layers[level], key=lambda g: (-sum(work[g].values()), g))
        for g in layer_groups:
            def key(k):
                combined = dict(loads[k])
                for pipe, cost in work[g].items():
                    combined[pipe] = combined.get(pipe, 0) + cost
                # Criticality/load first. Repeated input and remote predecessor
                # counts only break compute-load ties; no invented score weight.
                return (previous_work[k] + max(combined.values(), default=0),
                        sum(sizes[t] for t in inputs[g] - shared[k]),
                        sum(packet_core[p] != k for p in packet_pred[g]), k)
            k = min(range(cores), key=key)
            bins[k].append(g)
            shared[k].update(inputs[g])
            for pipe, cost in work[g].items():
                loads[k][pipe] += cost
            packet_core[g] = k
        for k, gs in enumerate(bins):
            if not gs:
                continue
            task = next_id
            next_id += 1
            for g in gs:
                for u in groups[g]:
                    mapping[u] = task
            schedules[k].append(task)
            previous_work[k] += max(loads[k].values(), default=0)
            diagnostics.append({"task": task, "core": k, "depth": level,
                                "packets": len(gs), "ops": sum(len(groups[g]) for g in gs)})
    plan = {"node_to_subgraph": {u: mapping[u] for u in sorted(mapping)},
            "core_schedules": schedules}
    validate_task_order(derive_multicore_plan(graph, plan))
    return plan, {"variant": variant, "selected_variant": selected, "packet_count": len(groups),
                  "levels": len(layers), "task_count": next_id, "tasks": diagnostics,
                  "scope": "Structural DAG validation only; final E0 required"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--cores", type=int, default=4)
    p.add_argument("--variant", choices=["chain-wave", "component-pack", "structural-switch"], default="chain-wave")
    p.add_argument("--diagnostics", type=Path)
    args = p.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    plan, diagnostics = construct(graph, args.cores, args.variant)
    # Never silently overwrite an experiment's final candidate.
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")
    if args.diagnostics:
        with args.diagnostics.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(diagnostics, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()
