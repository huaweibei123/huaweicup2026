"""Price a ready chain together with the join it releases.

One deterministic construction, at most k**2 placement pairs per released join.
The model excludes shared COPY contention, Cache and capacity effects.
"""
from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path

from .active_stages import build as fallback_build
from .construct import SharingIndex, derive_multicore_plan
from .dag_list import chain_dag
from evaluation_validation import read_bandwidth_config, read_required_settings


def build(index, cores, bandwidth, cross_delay):
    if not 1 <= cores <= 5 or bandwidth <= 0 or cross_delay < 0:
        raise ValueError('invalid fixed parameters')
    data = chain_dag(index, bandwidth, cross_delay)
    if data is None:
        plan, detail = fallback_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected='structural_fallback', fallback=detail)
    chains, pred, succ, delay = data
    rank = {}
    for j in reversed(range(len(chains))):
        rank[j] = sum(index.duration(u) for u in chains[j]) + max(
            (rank[v] for v in succ[j]), default=0)
    degree = {j: len(ps) for j, ps in pred.items()}
    ready = [(-rank[j], min(chains[j]), j) for j, d in degree.items() if not d]
    heapq.heapify(ready)
    availability = [dict.fromkeys(index.pipes, 0) for _ in range(cores)]
    placement, finish = {}, {}
    schedules = [[] for _ in range(cores)]
    paired = 0

    def append_model(j, core, clocks, temporary=None):
        release, cuts = 0, 0
        for p in pred[j]:
            pc, end = (temporary[1:3] if temporary is not None and p == temporary[0]
                       else (placement[p], finish[p]))
            release = max(release, end + (delay[p, j] if pc != core else 0))
            cuts += pc != core
        updated = dict(clocks)
        end = release
        for u in chains[j]:
            pipe = index.ops[u]['pipe']
            end = max(end, updated[pipe]) + index.duration(u)
            updated[pipe] = end
        return end, cuts, updated

    while ready:
        _, _, j = heapq.heappop(ready)
        if j in placement:
            continue
        candidate_join = next(iter(succ[j])) if len(succ[j]) == 1 else None
        join = (candidate_join if candidate_join is not None
                and len(pred[candidate_join]) > 1
                and pred[candidate_join] - {j} <= placement.keys() else None)
        choices = []
        for c in range(cores):
            end, cuts, clocks = append_model(j, c, availability[c])
            if join is None:
                choices.append(((end, cuts, sum(clocks.values()), c),
                                [(j, c, end, clocks)]))
            else:
                for d in range(cores):
                    final, join_cuts, joined = append_model(
                        join, d, clocks if c == d else availability[d], (j, c, end))
                    choices.append(((final, end, cuts + join_cuts, c, d),
                                    [(j, c, end, clocks), (join, d, final, joined)]))
        _, selected = min(choices, key=lambda item: item[0])
        paired += join is not None
        for v, c, end, clocks in selected:
            placement[v], finish[v] = c, end
            availability[c] = clocks
            schedules[c].extend(chains[v])
        for v, _, _, _ in selected:
            for u in succ[v]:
                degree[u] -= 1
                if degree[u] == 0 and u not in placement:
                    heapq.heappush(ready, (-rank[u], min(chains[u]), u))
    if len(placement) != len(chains):
        raise ValueError('incomplete chain/join construction')
    mapping = {str(u): s for s, u in enumerate(index.order)}
    plan = dict(node_to_subgraph=mapping,
                core_schedules=[[mapping[str(u)] for u in seq] for seq in schedules])
    derive_multicore_plan(index.graph, plan)
    return plan, dict(guard=True, selected='dag_join_list', cores=cores,
                     chains=len(chains), paired_joins=paired,
                     modeled_compute_finish=max(finish.values(), default=0),
                     cross_chain_edges=sum(placement[u] != placement[v] for u, v in delay),
                     assumption='incremental per-pipe model; no shared COPY, Cache or capacity simulation')


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
