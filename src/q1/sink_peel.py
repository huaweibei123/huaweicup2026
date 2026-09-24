"""Bounded sink-exclusive suffix waves for P1; structural candidate, no scorer.

Within the active DAG, vertices reaching exactly one active sink form disjoint
sink-exclusive packets. All other vertices form a predecessor-closed prefix.
Peel the packets, recurse on that prefix, then schedule waves in reverse peel
order. This keeps whole multi-branch output regions together, not just chains.
"""
from __future__ import annotations
from copy import deepcopy

from collections import Counter, deque

from src.q1.bounded_tasks import construct as bounded_construct
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import validate_task_order


class PeelBudgetExceeded(ValueError):
    """The bounded structural decomposition declined the input."""


def peel_packets(ids, pred, succ, *, max_rounds=64, max_sinks=64):
    """Return forward waves of independent packets, each a sorted list of IDs.

    Inputs must describe one complete DAG (typically COPY-contracted compute).
    No graph evaluation, Task compilation, timing simulation or score occurs.
    A budget exception discards the whole decomposition, never a partial plan.
    """
    for value in (max_rounds, max_sinks):
        if type(value) is not int or value < 1:
            raise ValueError("decomposition budgets must be positive integers")
    ids = sorted(ids)
    indegree = {u: len(pred[u]) for u in ids}
    queue = deque(u for u in ids if indegree[u] == 0)
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in sorted(succ[u]):
            indegree[v] -= 1
            if not indegree[v]:
                queue.append(v)
    if len(order) != len(ids):
        raise ValueError("Cyclic compute graph")
    active, peeled = set(ids), []
    while active:
        if len(peeled) >= max_rounds:
            raise PeelBudgetExceeded("round budget exceeded")
        sinks = [u for u in ids if u in active and not (succ[u] & active)]
        if len(sinks) > max_sinks:
            raise PeelBudgetExceeded("sink-width budget exceeded")
        masks = {u: 1 << i for i, u in enumerate(sinks)}
        for u in reversed(order):
            if u not in active:
                continue
            mask = masks.get(u, 0)
            for v in succ[u]:
                if v in active:
                    mask |= masks[v]
            masks[u] = mask
        packets = {}
        for u in ids:
            if u in active:
                mask = masks[u]
                if mask and mask & (mask - 1) == 0:
                    packets.setdefault(mask, []).append(u)
        if not packets:
            raise AssertionError("Every nonempty DAG has at least one sink")
        wave = list(packets.values())
        peeled.append(wave)
        active.difference_update(u for packet in wave for u in packet)
    return list(reversed(peeled))


def construct(graph, cores, *, max_rounds=64, max_sinks=64, fallback_candidate=None):
    """Build a legal Task-order candidate; E0 feasibility/quality remain untested."""
    for value in (max_rounds, max_sinks):
        if type(value) is not int or value < 1:
            raise ValueError("decomposition budgets must be positive integers")
    fallback, base = (bounded_construct(graph, cores) if fallback_candidate is None
                      else deepcopy(fallback_candidate))
    info = {"algorithm_id": "q1-sink-peel", "variant": "exclusive-suffix-waves",
            "selected": "bounded04", "base": base,
            "max_rounds": max_rounds, "max_sinks": max_sinks,
            "scope": "Task-order proof only; no spill, performance or E0 feasibility guarantee"}
    if (cores == 1 or base["base"]["selected"] != "component-pack"
            or base["base"]["base"]["components"] >= cores):
        info["reason"] = "existing bounded04 structural route retained"
        return fallback, info
    ops = {op["id"]: op for op in graph["ops"]
           if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
    try:
        waves = peel_packets(ops, pred, succ, max_rounds=max_rounds, max_sinks=max_sinks)
    except PeelBudgetExceeded as exc:
        info["reason"] = str(exc)
        return fallback, info
    if not any(len(wave) > 1 for wave in waves):
        info["reason"] = "no independent suffix packets; single sink remains indivisible"
        return fallback, info
    mapping, node_wave, schedules, details = {}, {}, [[] for _ in range(cores)], []
    next_task = 0
    for wave_index, wave in enumerate(waves):
        packets = []
        for packet in wave:
            work = Counter()
            for u in packet:
                work[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
            packets.append((packet, work))
        packets.sort(key=lambda x: (-max(x[1].values()), -sum(x[1].values()), x[0][0]))
        loads, bins = [Counter() for _ in range(cores)], [[] for _ in range(cores)]
        for packet, work in packets:
            def key(k):
                after = [loads[k][p] + work[p] for p in loads[k].keys() | work.keys()]
                return max(after), sum(after), len(bins[k]), k
            core = min(range(cores), key=key)
            bins[core].extend(packet)
            loads[core].update(work)
        for core, nodes in enumerate(bins):
            if nodes:
                schedules[core].append(next_task)
                for u in nodes:
                    mapping[u], node_wave[u] = next_task, wave_index
                next_task += 1
        details.append({"packets": len(wave), "packet_ops": sorted(map(len, wave)),
                        "core_ops": list(map(len, bins)),
                        "pipe_work_by_core": [dict(sorted(x.items())) for x in loads]})
    # Edges never go backward, and different packets in a wave cannot interact.
    for u in ops:
        for v in succ[u]:
            if mapping[u] != mapping[v] and node_wave[u] >= node_wave[v]:
                raise AssertionError("Cross-Task edge does not advance a wave")
    plan = {"node_to_subgraph": {u: mapping[u] for u in ops}, "core_schedules": schedules}
    validate_task_order(derive_multicore_plan(graph, plan))
    info.update(selected="sink-peel", waves=details, wave_count=len(waves), tasks=next_task)
    return plan, info
