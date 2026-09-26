"""Place ready chains and released joins into existing per-pipe idle gaps.

Every candidate is arithmetic in a fixed computation/transfer model. The
official COPY, cache, and capacity system remains outside this model.
"""
from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path

from .active_stages import build as fallback_build
from .construct import SharingIndex, derive_multicore_plan
from .dag_list import chain_dag
from .gap_calendar import empty, earliest, reserve
from evaluation_validation import read_bandwidth_config, read_required_settings


def build(index, cores, bandwidth, cross_delay):
    if not 1 <= cores <= 5 or bandwidth <= 0 or cross_delay < 0:
        raise ValueError('invalid fixed parameters')
    data = chain_dag(index, bandwidth, cross_delay)
    if data is None or any(o['pipe'] not in ('PIPE_M', 'PIPE_V') or
                           type(o['cycles']) is not int or o['cycles'] < 0
                           for o in index.ops.values()):
        plan, meta = fallback_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected='structural_fallback', fallback=meta)
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
    return plan, dict(guard=True, selected='dag_join_gap_list', cores=cores,
                     chains=len(chains), paired_joins=paired, operations_inserted_before_tail=inserted,
                     modeled_compute_finish=max(finish.values(), default=0),
                     cross_chain_edges=sum(placement[u] != placement[v] for u, v in delay),
                     assumption='persistent idle calendars; no official COPY/cache/capacity simulation')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[2] /
                    'data/raw/a/official/data/config.txt')
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    index = SharingIndex(json.loads(args.graph.read_text(encoding='utf-8')))
    fixed = read_required_settings(args.config, 'multicore_scene_b', ('cross_core_copy_delay_cycles',))
    plan, meta = build(index, args.cores, read_bandwidth_config(args.config),
                       fixed['cross_core_copy_delay_cycles'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
