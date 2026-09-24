"""Split components that exceed a per-pipe fair share, then schedule their DAG.

The fair-share test identifies a restriction of whole-component placement;
it is not a guarantee that splitting is profitable. Ready-list times are
compute/gate proxies, not E0 predictions or optimality certificates.
"""
from __future__ import annotations
from copy import deepcopy

import argparse
from collections import Counter
import heapq
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.heavy_suffix import construct as fallback_construct
from src.q1.sink_peel import peel_packets, PeelBudgetExceeded
from src.q1.bounded_tasks import split_large_tasks
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import read_required_settings, validate_task_order


def _pack(packets, ops, cores):
    weighted = []
    for nodes in packets:
        work = Counter()
        for u in nodes:
            work[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
        weighted.append((nodes, work))
    weighted.sort(key=lambda x: (-max(x[1].values()), -sum(x[1].values()), min(x[0])))
    loads, bins = [Counter() for _ in range(cores)], [[] for _ in range(cores)]
    for nodes, work in weighted:
        def score(c):
            after = [loads[c][p] + work[p] for p in loads[c].keys() | work.keys()]
            return max(after), sum(after), len(bins[c]), c
        c = min(range(cores), key=score)
        loads[c].update(work)
        bins[c].extend(nodes)
    return [b for b in bins if b]


def _place(tasks, successors, ops, cores, same_wait, cross_wait):
    """Assign a fixed acyclic quotient in topological order; no real simulation."""
    mapping = {u: t for t, nodes in enumerate(tasks) for u in nodes}
    pred = [set() for _ in tasks]
    succ = [set() for _ in tasks]
    for u, vs in successors.items():
        for v in vs:
            a, b = mapping[u], mapping[v]
            if a != b:
                pred[b].add(a)
                succ[a].add(b)
    weights = []
    for nodes in tasks:
        work = Counter()
        for u in nodes:
            work[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
        weights.append(max(work.values()))
    degree = list(map(len, pred))
    ready = [t for t, d in enumerate(degree) if not d]
    heapq.heapify(ready)
    order = []
    while ready:
        t = heapq.heappop(ready)
        order.append(t)
        for v in sorted(succ[t]):
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, v)
    if len(order) != len(tasks):
        raise AssertionError("Component-wave quotient is cyclic")
    tail = weights.copy()
    for t in reversed(order):
        tail[t] += max((tail[v] for v in succ[t]), default=0)
    degree = list(map(len, pred))
    ready = [(-tail[t], t) for t, d in enumerate(degree) if not d]
    heapq.heapify(ready)
    schedules, ends = [[] for _ in range(cores)], [0] * cores
    task_core, finishes, starts = {}, {}, {}
    placement_order = []
    while ready:
        _, t = heapq.heappop(ready)
        choices = []
        for c in range(cores):
            local = ends[c] + same_wait if schedules[c] else 0
            release = max((finishes[p] + (cross_wait if task_core[p] != c else 0)
                           for p in pred[t]), default=0)
            start = max(local, release)
            choices.append((start + weights[t], start, len(schedules[c]), c))
        finish, start, _, c = min(choices)
        schedules[c].append(t)
        task_core[t], finishes[t], starts[t], ends[c] = c, finish, start, finish
        placement_order.append(t)
        for v in sorted(succ[t]):
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, (-tail[v], v))
    # Every dependency and every appended core-order edge follows this one
    # topological placement rank, so the augmented Task graph stays acyclic.
    rank = {t: i for i, t in enumerate(placement_order)}
    assert all(rank[t] < rank[v] for t in range(len(tasks)) for v in succ[t])
    plan = {"node_to_subgraph": {u: mapping[u] for u in ops}, "core_schedules": schedules}
    return plan, dict(placement_order=placement_order, tasks_before_soft_chunks=len(tasks),
                     compute_gate_proxy_finish=max(ends),
                     task_compute_weight=weights,
                     task_start_proxy=[starts[t] for t in range(len(tasks))],
                     task_finish_proxy=[finishes[t] for t in range(len(tasks))])


def construct(graph, cores, *, max_rounds=64, max_sinks=64, fallback_candidate=None):
    fallback, base = (fallback_construct(graph, cores, max_rounds=max_rounds, max_sinks=max_sinks)
                      if fallback_candidate is None else deepcopy(fallback_candidate))
    info = dict(algorithm_id="q1-component-overload-list", variant="any-pipe-overload-quotient-ready-list",
                max_rounds=max_rounds, max_sinks=max_sinks, base=base, selected="heavy-suffix-fallback",
                scope="Direct structural proposal; proxy times omit DDR, FIFO and capacity")
    if cores == 1:
        return fallback, info
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
    unseen, components = set(ops), []
    for root in sorted(ops):
        if root not in unseen:
            continue
        unseen.remove(root)
        stack, nodes, work = [root], [], Counter()
        while stack:
            u = stack.pop()
            nodes.append(u)
            work[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
            for v in pred[u] | succ[u]:
                if v in unseen:
                    unseen.remove(v)
                    stack.append(v)
        components.append((sorted(nodes), work))
    if len(components) < cores:
        info["reason"] = "retain component-scarce route"
        return fallback, info
    total = Counter()
    for _, work in components:
        total.update(work)
    tasks, retained, split = [], [], []
    for nodes, work in components:
        overloaded = sorted(p for p, w in work.items()
                            if w > (total[p] + cores - 1) // cores)
        if not overloaded:
            retained.append(nodes)
            continue
        members = set(nodes)
        try:
            waves = peel_packets(members, {u: pred[u] & members for u in nodes},
                                 {u: succ[u] & members for u in nodes},
                                 max_rounds=max_rounds, max_sinks=max_sinks)
        except PeelBudgetExceeded:
            retained.append(nodes)
            continue
        if not any(len(wave) > 1 for wave in waves):
            retained.append(nodes)
            continue
        before = len(tasks)
        for wave in waves:
            tasks.extend(_pack(wave, ops, cores))
        split.append(dict(anchor=min(nodes), ops=len(nodes), overloaded_pipes=overloaded,
                          pipe_work=dict(work), waves=len(waves), tasks=len(tasks)-before))
    if not split:
        info["reason"] = "no overloaded component with independent suffix packets"
        return fallback, info
    # Independent retained components are ready from the start. They are not
    # appended to a global last wave, nor split just to manufacture parallelism.
    tasks.extend(_pack(retained, ops, cores))
    settings = read_required_settings(ROOT / "data/raw/a/official/data/config.txt", "multicore_scene_a",
                                      ("task_same_core_wait_cycles", "task_cross_core_wait_cycles"))
    proposal, placement = _place(tasks, succ, ops, cores,
                                settings["task_same_core_wait_cycles"], settings["task_cross_core_wait_cycles"])
    result, chunks = split_large_tasks(graph, proposal)
    validate_task_order(derive_multicore_plan(graph, result))
    info.update(selected="overload-list", total_pipe_work=dict(total), components=len(components),
                split_components=split, retained_components=len(retained), placement=placement, chunks=chunks,
                reason="some per-pipe whole-component loads exceed the K-core fair share")
    return result, info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("--cores", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--diagnostics", type=Path)
    a = p.parse_args()
    if a.output.exists() or (a.diagnostics and a.diagnostics.exists()):
        raise FileExistsError("Refuse to overwrite experiment artifacts")
    plan, info = construct(json.loads(a.graph.read_text()), a.cores)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as f:
        json.dump(plan, f, separators=(",", ":")); f.write("\n")
    if a.diagnostics:
        a.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        with a.diagnostics.open("x") as f:
            json.dump(info, f, indent=2); f.write("\n")
    print(json.dumps(info))


if __name__ == "__main__":
    main()
