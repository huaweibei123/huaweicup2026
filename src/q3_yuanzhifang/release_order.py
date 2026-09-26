"""Reorder cross-pipe priorities while preserving every M/V FIFO chain.

Original ownership and same-pipe order stay fixed. Sort local priorities by
earliest start in the actual compute-plus-FIFO DAG with fixed cross delay.
This may change COPY queue priorities; E0 alone determines its benefit.
"""
from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path

from .construct import SharingIndex, derive_multicore_plan
from .join_list import build as join_build
from evaluation_validation import read_bandwidth_config, read_required_settings
from multicore_cut_evaluate_problem_1 import _original_tensor_views


def reorder(index, plan, cross_delay):
    if any(o['pipe'] not in ('PIPE_M', 'PIPE_V') for o in index.ops.values()):
        raise ValueError('only original M/V operations are supported')
    view = derive_multicore_plan(index.graph, plan)
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise ValueError('singleton subgraphs required')
    inverse = {s: int(u) for u, s in plan['node_to_subgraph'].items()}
    sequences = [[inverse[s] for s in seq] for seq in plan['core_schedules']]
    owner = {u: c for c, seq in enumerate(sequences) for u in seq}
    producers, consumers, direct = _original_tensor_views(index.graph)
    edges = {(u, v) for t, readers in consumers.items()
             for u in producers[t] & index.ops.keys() for v in readers & index.ops.keys() if u != v}
    edges.update((e['source'], e['target']) for e in direct
                 if e['source'] in index.ops and e['target'] in index.ops)
    if edges != {(u, v) for u in index.ops for v in index.succ[u]}:
        raise ValueError('COPY contraction adds unproved computation dependencies')
    adjacency = {u: {} for u in index.ops}
    for u, v in edges:
        adjacency[u][v] = cross_delay if owner[u] != owner[v] else 0
    for seq in sequences:
        last = {}
        for u in seq:
            pipe = index.ops[u]['pipe']
            if pipe in last:
                adjacency[last[pipe]].setdefault(u, 0)
            last[pipe] = u
    degree = dict.fromkeys(index.ops, 0)
    for targets in adjacency.values():
        for v in targets:
            degree[v] += 1
    ready = [u for u, d in degree.items() if not d]
    heapq.heapify(ready)
    start = dict.fromkeys(index.ops, 0)
    seen = 0
    while ready:
        u = heapq.heappop(ready)
        seen += 1
        for v, delay in adjacency[u].items():
            start[v] = max(start[v], start[u]+index.duration(u)+delay)
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, v)
    if seen != len(index.ops):
        raise ValueError('original computation and current FIFO contain a cycle')
    changed = 0
    output = []
    for seq in sequences:
        rank = {u: r for r, u in enumerate(seq)}
        ordered = sorted(seq, key=lambda u: (start[u], rank[u]))
        # A positive-duration FIFO edge makes start strictly increasing.
        for pipe in ('PIPE_M', 'PIPE_V'):
            assert [u for u in seq if index.ops[u]['pipe'] == pipe] == [
                u for u in ordered if index.ops[u]['pipe'] == pipe]
        changed += sum(u != v for u, v in zip(seq, ordered))
        output.append([plan['node_to_subgraph'][str(u)] for u in ordered])
    result = dict(node_to_subgraph=plan['node_to_subgraph'], core_schedules=output)
    derive_multicore_plan(index.graph, result)
    return result, dict(changed_priority_positions=changed, computation_fifo_preserved=True,
                        fixed_computation_delay_bound=max(
                            (start[u]+index.duration(u) for u in start), default=0))


def build(index, cores, bandwidth, cross_delay):
    plan, base = join_build(index, cores, bandwidth, cross_delay)
    if not base['guard']:
        return plan, dict(guard=False, selected='structural_fallback', fallback=base)
    plan, detail = reorder(index, plan, cross_delay)
    return plan, dict(guard=True, selected='dag_join_release_order', base_join=base, **detail)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[2] /
                    'data/raw/a/official/data/config.txt')
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    x = SharingIndex(json.loads(args.graph.read_text(encoding='utf-8')))
    fixed = read_required_settings(args.config, 'multicore_scene_b', ('cross_core_copy_delay_cycles',))
    plan, detail = build(x, args.cores, read_bandwidth_config(args.config),
                         fixed['cross_core_copy_delay_cycles'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':'))+'\n', encoding='utf-8')
    print(json.dumps(detail, sort_keys=True))


if __name__ == '__main__':
    main()
