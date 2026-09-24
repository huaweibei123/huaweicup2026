# Adapted from Fang's fixed a37eb931a22fb7df7e0d00d193538ce5289ae045:
# gap_list.py + chain_dag from dag_list.py. Preserve placement/tie-breaking.
# This adapter accepts our Index and rejects unsupported shapes; it does not
# silently invoke Fang's separate fallback. See docs/a/q3/GENERAL_GAP.md.
"""Place ready chains and released joins into existing per-pipe idle gaps.

Every candidate is arithmetic in a fixed computation/transfer model. The
official COPY, cache, and capacity system remains outside this model.
"""
from __future__ import annotations

import heapq

from .construct import UnsupportedStructure, derive_multicore_plan
from .gap_calendar import empty, earliest, reserve
from multicore_cut_evaluate_problem_1 import _original_tensor_views
import math


def chain_dag(index, bandwidth, cross_delay):
    sizes_by_id = {t["id"]: t["size"] for t in index.graph["tensors"]}
    producers, consumers, direct = _original_tensor_views(index.graph)
    edges = {}
    for t, readers in consumers.items():
        for u in producers[t] & index.ops.keys():
            for v in readers & index.ops.keys():
                if u != v:
                    edges.setdefault((u, v), []).append(sizes_by_id[t])
    for e in direct:
        u, v = e['source'], e['target']
        if u in index.ops and v in index.ops:
            edges.setdefault((u, v), []).append(e.get('data_size', 0))
    physical = {(u, v) for u in index.ops for v in index.succ[u]}
    if physical != edges.keys():
        return None
    if not (any(len(index.succ[u]) > 1 for u in index.ops)
            and any(len(index.pred[u]) > 1 for u in index.ops)):
        return None
    chains, owner = [], {}
    for root in index.order:
        if root in owner:
            continue
        job = []
        u = root
        while True:
            owner[u] = len(chains)
            job.append(u)
            if len(index.succ[u]) != 1:
                break
            v = next(iter(index.succ[u]))
            if len(index.pred[v]) != 1:
                break
            u = v
        chains.append(job)
    pred = {j: set() for j in range(len(chains))}
    succ = {j: set() for j in range(len(chains))}
    delay = {}
    for (u, v), sizes in edges.items():
        a, b = owner[u], owner[v]
        if a == b:
            continue
        pred[b].add(a)
        succ[a].add(b)
        # Static all-miss service estimate. A transfer can overlap other work;
        # this number is not an E0 duration or a valid general lower bound.
        delay[a, b] = max(delay.get((a, b), 0), cross_delay +
                          2 * sum(max(1, math.ceil(s / bandwidth)) for s in sizes))
    return chains, pred, succ, delay


def construct(index, cores, bandwidth, cross_delay):
    if type(cores) is not int or not 1 <= cores <= 5 or bandwidth <= 0 or cross_delay < 0:
        raise ValueError('invalid fixed parameters')
    data = chain_dag(index, bandwidth, cross_delay)
    if data is None or any(o['pipe'] not in ('PIPE_M', 'PIPE_V') or
                           type(o['cycles']) is not int or o['cycles'] < 0
                           for o in index.ops.values()):
        raise UnsupportedStructure('requires fork/join M/V DAG with exact original compute edges')
    chains, pred, succ, delay = data
    rank = {}
    for j in reversed(range(len(chains))):
        rank[j] = sum(index.duration(u) for u in chains[j]) + max(
            (rank[v] for v in succ[j]), default=0)
    degree = {j: len(ps) for j, ps in pred.items()}
    ready = [(-rank[j], min(chains[j]), j) for j, d in degree.items() if not d]
    heapq.heapify(ready)
    calendars = [dict.fromkeys(('PIPE_M', 'PIPE_V'), empty()) for _ in range(cores)]
    placement, finish, starts = {}, {}, {}
    schedules = [[] for _ in range(cores)]
    paired, inserted = 0, 0
    last_finish = [dict.fromkeys(('PIPE_M', 'PIPE_V'), 0) for _ in range(cores)]

    def place(j, core, calendar, temporary=None):
        at, cuts = 0, 0
        for p in pred[j]:
            pc, end = (temporary[1:3] if temporary is not None and p == temporary[0]
                       else (placement[p], finish[p]))
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
        join = (candidate if candidate is not None and len(pred[candidate]) > 1
                and pred[candidate] - {j} <= placement.keys() else None)
        best = None
        for c in range(cores):
            end, cuts, calendar, entries = place(j, c, calendars[c])
            if join is None:
                item = ((end, cuts, c), [(j, c, end, calendar, entries)])
                if best is None or item[0] < best[0]:
                    best = item
            else:
                for d in range(cores):
                    final, other_cuts, joined, other_entries = place(
                        join, d, calendar if c == d else calendars[d], (j, c, end))
                    item = ((final, end, cuts + other_cuts, c, d),
                            [(j, c, end, calendar, entries),
                             (join, d, final, joined, other_entries)])
                    if best is None or item[0] < best[0]:
                        best = item
        chosen = best[1]
        paired += join is not None
        for v, c, end, calendar, entries in chosen:
            placement[v], finish[v], calendars[c] = c, end, calendar
            for u, pipe, start, stop in entries:
                inserted += start < last_finish[c][pipe]
                last_finish[c][pipe] = max(last_finish[c][pipe], stop)
                starts[u] = start
                schedules[c].append(u)
        for v, *_ in chosen:
            for u in succ[v]:
                degree[u] -= 1
                if degree[u] == 0 and u not in placement:
                    heapq.heappush(ready, (-rank[u], min(chains[u]), u))
    if len(placement) != len(chains):
        raise ValueError('incomplete gap-insertion construction')
    mapping = {str(u): s for s, u in enumerate(index.order)}
    plan = dict(node_to_subgraph=mapping, core_schedules=[
        [mapping[str(u)] for u in sorted(seq, key=lambda u: (starts[u], mapping[str(u)]))]
        for seq in schedules])
    derive_multicore_plan(index.graph, plan)
    return plan, dict(guard=True, selected='dag_join_gap_list', strategy='dag_join_gap_list', cores=cores,
                     upstream_commit='a37eb931a22fb7df7e0d00d193538ce5289ae045',
                     official_e0_calls=0,
                     chains=len(chains), paired_joins=paired, operations_inserted_before_tail=inserted,
                     modeled_compute_finish=max(finish.values(), default=0),
                     cross_chain_edges=sum(placement[u] != placement[v] for u, v in delay),
                     assumption='persistent idle calendars; no official COPY/cache/capacity simulation')
