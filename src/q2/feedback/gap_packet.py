"""P2 TensorIndex adaptation of P3's guarded join/gap list construction.

Credit: P3 session 3d9c, a37eb931a22fb7df7e0d00d193538ce5289ae045,
gap_list.py and dag_list.py. This changes the index/fallback, not the claimed
ownership of the placement idea. No COPY contention or capacity simulation.
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path

from .capacity_window import build as capacity_build
from .construct import ROOT, derive_multicore_plan
from .gap_calendar import empty, earliest, reserve
from .tensor_packet import TensorIndex


def chain_dag(index, bandwidth, cross_delay):
    if any('logical_tid' in tensor for tensor in index.tensors.values()):
        return None
    edges = {}
    for tensor, producer in index.producer.items():
        for consumer in index.consumers[tensor]:
            if producer != consumer:
                edges.setdefault((producer, consumer), []).append(index.tensors[tensor]['size'])
    for consumer, predecessors in index.direct.items():
        for _, producer, size in predecessors:
            edges.setdefault((producer, consumer), []).append(size)
    if {(u, v) for u in index.ops for v in index.succ[u]} != edges.keys():
        return None  # A COPY-contracted relation is not assumed to be a physical tensor edge.
    if not (any(len(index.pred[u]) > 1 for u in index.ops)
            and any(len(index.succ[u]) > 1 for u in index.ops)):
        return None
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


def build(index, cores, bandwidth, cross_delay, capacity):
    if (type(cores) is not int or not 1 <= cores <= 5
            or type(bandwidth) not in (int, float) or not math.isfinite(bandwidth) or bandwidth <= 0
            or type(cross_delay) is not int or cross_delay < 0):
        raise ValueError('invalid fixed parameters')
    if set(capacity) != {'L1', 'UB'} or any(type(v) is not int or v < 0 for v in capacity.values()):
        raise ValueError('nonnegative integer L1 and UB capacity required')
    data = chain_dag(index, bandwidth, cross_delay)
    if data is None:
        plan, meta = capacity_build(index, cores, bandwidth, cross_delay, capacity)
        return plan, {'selected': 'gap_guard_capacity_fallback', 'fallback': meta,
                      'online_E0_calls': 0}
    chains, pred, succ, delay, order = data
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
    derive_multicore_plan(index.graph, plan)
    return plan, {'selected': 'join_gap_packet', 'chains': len(chains), 'paired_joins': paired,
                  'operations_inserted_before_tail': inserted, 'arithmetic_placement_choices': choices,
                  'modeled_compute_finish': max(finish.values(), default=0), 'online_E0_calls': 0,
                  'scope': 'Static communication/compute calendar; no capacity certificate, COPY contention, or optimality claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--config', type=Path, default=ROOT / 'data/raw/a/official/data/config.txt')
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
    plan, meta = build(TensorIndex(json.loads(args.graph.read_bytes())), args.cores,
                       config['bandwidth'], config['cross_core_copy_delay_cycles'], config['capacity'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
