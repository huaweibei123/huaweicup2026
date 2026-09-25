"""Guarded P2 chain/join lookahead and gap-calendar candidate.

Adapted from Fang P2 feedback/gap_packet.py at 71616ac7c4c7fca56e37e2d3245dd13725316d82;
placement concept and calendar originate in P3 session 3d9c, a37eb931a22fb7df7e0d00d193538ce5289ae045.
Static COPY delays omit contention, capacity, and spill; they are not bounds.
"""
from __future__ import annotations

from collections import defaultdict
import heapq
import math

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .gap_calendar import empty, earliest, reserve


def _chain_dag(index, bandwidth, cross_delay):
    if any('logical_tid' in tensor for tensor in index.tensors.values()):
        raise UnsupportedStructure('logical_tid tensor is outside physical guard')
    original = {op['id'] for op in index.graph['ops']}
    producers = defaultdict(set)
    for edge in index.graph['edges']:
        if edge['source'] in original and edge['target'] in index.tensors:
            producers[edge['target']].add(edge['source'])
    if any(len(ps) > 1 for ps in producers.values()):
        raise UnsupportedStructure('physical tensor has multiple original producers')
    edges = {}
    for tid, ps in index.producers.items():
        for producer in ps:
            for consumer in index.consumers[tid]:
                if producer != consumer:
                    edges.setdefault((producer, consumer), []).append(index.tensors[tid]['size'])
    for consumer, predecessors in index.direct_inputs.items():
        for producer, size in predecessors:
            edges.setdefault((producer, consumer), []).append(size)
    contracted = {(u, v) for u in index.ops for v in index.succ[u]}
    if contracted != edges.keys():
        raise UnsupportedStructure('eligible physical/direct edges differ from contracted DAG')
    if not (any(len(index.pred[u]) > 1 for u in index.ops)
            and any(len(index.succ[u]) > 1 for u in index.ops)):
        raise UnsupportedStructure('requires both fork and join')
    chains, owner = [], {}
    for root in index.order:
        if root in owner:
            continue
        chain, u = [], root
        while True:
            owner[u] = len(chains)
            chain.append(u)
            if len(index.succ[u]) != 1:
                break
            v = next(iter(index.succ[u]))
            if len(index.pred[v]) != 1:
                break
            u = v
        chains.append(chain)
    pred, succ = [set() for _ in chains], [set() for _ in chains]
    delay = {}
    for (u, v), sizes in edges.items():
        a, b = owner[u], owner[v]
        if a != b:
            pred[b].add(a)
            succ[a].add(b)
            delay[a, b] = max(delay.get((a, b), 0), cross_delay +
                              2 * sum(max(1, math.ceil(size / bandwidth)) for size in sizes))
    degree = [len(ps) for ps in pred]
    ready = [j for j, count in enumerate(degree) if not count]
    heapq.heapify(ready)
    order = []
    while ready:
        j = heapq.heappop(ready)
        order.append(j)
        for v in sorted(succ[j]):
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, v)
    if len(order) != len(chains):
        raise ValueError('serial-chain contraction has a cycle')
    return chains, pred, succ, delay, order


def _build_with_witness(graph, cores, config):
    """Construct one singleton plan and its fixed static-calendar witness."""
    bandwidth = config['bandwidth']
    cross_delay = config['cross_core_copy_delay_cycles']
    if (type(cores) is not int or not 1 <= cores <= 5
            or type(bandwidth) not in (int, float) or not math.isfinite(bandwidth) or bandwidth <= 0
            or type(cross_delay) is not int or cross_delay < 0):
        raise ValueError('invalid fixed parameters')
    index = DAGIndex(graph)
    chains, pred, succ, delay, order = _chain_dag(index, bandwidth, cross_delay)
    rank = {}
    for j in reversed(order):
        rank[j] = sum(index.duration(u) for u in chains[j]) + max(
            (rank[v] for v in succ[j]), default=0)
    degree = [len(ps) for ps in pred]
    ready = [(-rank[j], min(chains[j]), j) for j, count in enumerate(degree) if not count]
    heapq.heapify(ready)
    pipes = sorted({op['pipe'] for op in index.ops.values()})
    calendars = [dict.fromkeys(pipes, empty()) for _ in range(cores)]
    placement, finish, starts = {}, {}, {}
    schedules = [[] for _ in range(cores)]
    last_finish = [dict.fromkeys(pipes, 0) for _ in range(cores)]
    paired = inserted = choices = 0

    def place(j, core, calendar, temporary=None):
        at = cuts = 0
        for p in pred[j]:
            pc, end = temporary[1:3] if temporary is not None and p == temporary[0] else (placement[p], finish[p])
            at = max(at, end + (delay[p, j] if pc != core else 0))
            cuts += pc != core
        updated, entries = dict(calendar), []
        for u in chains[j]:
            pipe, duration = index.ops[u]['pipe'], index.duration(u)
            start = earliest(updated[pipe], at, duration)
            updated[pipe] = reserve(updated[pipe], start, duration)
            at = start + duration
            entries.append((u, pipe, start, at))
        return at, cuts, updated, entries

    while ready:
        _, _, j = heapq.heappop(ready)
        if j in placement:
            continue
        candidate = next(iter(succ[j])) if len(succ[j]) == 1 else None
        join = candidate if (candidate is not None and len(pred[candidate]) > 1
                             and pred[candidate] - {j} <= placement.keys()) else None
        best = None
        for core in range(cores):
            end, cuts, calendar, entries = place(j, core, calendars[core])
            if join is None:
                item = ((end, cuts, core), [(j, core, end, calendar, entries)])
                choices += 1
                if best is None or item[0] < best[0]:
                    best = item
            else:
                for target in range(cores):
                    final, other_cuts, joined, other_entries = place(
                        join, target, calendar if core == target else calendars[target], (j, core, end))
                    item = ((final, end, cuts + other_cuts, core, target),
                            [(j, core, end, calendar, entries), (join, target, final, joined, other_entries)])
                    choices += 1
                    if best is None or item[0] < best[0]:
                        best = item
        paired += join is not None
        for v, core, end, calendar, entries in best[1]:
            placement[v], finish[v], calendars[core] = core, end, calendar
            for u, pipe, start, stop in entries:
                inserted += start < last_finish[core][pipe]
                last_finish[core][pipe] = max(last_finish[core][pipe], stop)
                starts[u] = start
                schedules[core].append(u)
        for v, *_ in best[1]:
            for successor in succ[v]:
                degree[successor] -= 1
                if degree[successor] == 0 and successor not in placement:
                    heapq.heappush(ready, (-rank[successor], min(chains[successor]), successor))
    if len(placement) != len(chains):
        raise ValueError('incomplete join/gap construction')
    mapping = {str(u): position for position, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping, 'core_schedules': [
        [mapping[str(u)] for u in sorted(sequence, key=lambda u: (starts[u], mapping[str(u)]))]
        for sequence in schedules]}
    derive_multicore_plan(graph, plan)
    meta = {'selected': 'join_gap_candidate', 'chains': len(chains), 'paired_joins': paired,
                  'operations_inserted_before_tail': inserted, 'arithmetic_placement_choices': choices,
                  'choice_bound': len(chains) * cores * cores,
                  'modeled_compute_finish': max(finish.values(), default=0), 'online_E0_calls': 0,
                  'scope': 'Static communication/compute calendar; no capacity, COPY contention, or optimality claim.'}
    witness = {'chains': chains, 'placement': placement, 'starts': starts,
               'delays': delay, 'mapping': mapping}
    return plan, meta, witness


def build_with_witness(graph, cores, config):
    return _build_with_witness(graph, cores, config)


def build(graph, cores, config):
    """Preserve the original two-value candidate API and behavior."""
    plan, meta, _ = _build_with_witness(graph, cores, config)
    return plan, meta
