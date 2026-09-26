"""Direct communication-aware list construction for fork/join computation DAGs.

Coarsen only maximal serial chains. Place each ready chain at its earliest
modeled finish on a core, retaining per-pipe order. This model omits COPY pool
contention and capacity; only unchanged E0 establishes actual quality/legality.
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path

from .active_stages import build as stage_build
from .construct import SharingIndex, derive_multicore_plan
from multicore_cut_evaluate_problem_1 import _original_tensor_views
from evaluation_validation import read_bandwidth_config, read_required_settings


def chain_dag(index, bandwidth, cross_delay):
    producers, consumers, direct = _original_tensor_views(index.graph)
    edges = {}
    for t, readers in consumers.items():
        for u in producers[t] & index.ops.keys():
            for v in readers & index.ops.keys():
                if u != v:
                    edges.setdefault((u, v), []).append(index.sizes[t])
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


def build(index, cores, bandwidth, cross_delay):
    if not 1 <= cores <= 5 or bandwidth <= 0 or cross_delay < 0:
        raise ValueError('invalid fixed parameters')
    data = chain_dag(index, bandwidth, cross_delay)
    if data is None:
        plan, meta = stage_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected='structural_fallback', fallback=meta)
    chains, pred, succ, delay = data
    # Chains are created in the original topological order; edge endpoints
    # therefore increase in this chain order.
    weight = [sum(index.duration(u) for u in chain) for chain in chains]
    rank = {}
    for j in reversed(range(len(chains))):
        rank[j] = weight[j] + max((rank[v] for v in succ[j]), default=0)
    degree = {j: len(ps) for j, ps in pred.items()}
    ready = [(-rank[j], min(chains[j]), j) for j in degree if not degree[j]]
    heapq.heapify(ready)
    availability = [dict.fromkeys(index.pipes, 0) for _ in range(cores)]
    placement, finish, schedules = {}, {}, [[] for _ in range(cores)]
    while ready:
        _, _, j = heapq.heappop(ready)
        choices = []
        for core in range(cores):
            at = max((finish[p] + (delay[p, j] if placement[p] != core else 0)
                      for p in pred[j]), default=0)
            clocks = dict(availability[core])
            for u in chains[j]:
                pipe = index.ops[u]['pipe']
                at = max(at, clocks[pipe]) + index.duration(u)
                clocks[pipe] = at
            cuts = sum(placement[p] != core for p in pred[j])
            choices.append((at, cuts, sum(clocks.values()), core, clocks))
        end, _, _, core, clocks = min(choices, key=lambda choice: choice[:4])
        placement[j], finish[j] = core, end
        availability[core] = clocks
        schedules[core].extend(chains[j])
        for v in succ[j]:
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, (-rank[v], min(chains[v]), v))
    if len(placement) != len(chains):
        raise ValueError('chain condensation cycle')
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = dict(node_to_subgraph=mapping,
                core_schedules=[[mapping[str(u)] for u in seq] for seq in schedules])
    derive_multicore_plan(index.graph, plan)
    return plan, dict(guard=True, selected='dag_chain_list', cores=cores,
                     chains=len(chains), longest_chain_ops=max(map(len, chains)),
                     modeled_compute_finish=max(finish.values(), default=0),
                     cross_chain_edges=sum(placement[u] != placement[v] for u, v in delay),
                     warning='No E0, capacity, or shared COPY-pool simulation inside the model')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[2] / 'data/raw/a/official/data/config.txt')
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    index = SharingIndex(json.loads(args.graph.read_text(encoding='utf-8')))
    cross = read_required_settings(args.config, 'multicore_scene_b', ('cross_core_copy_delay_cycles',))
    plan, meta = build(index, args.cores, read_bandwidth_config(args.config), cross['cross_core_copy_delay_cycles'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
