"""Partition identical shared-input chains into contiguous pipeline stages.

The DP solves a copy-free, single-server-per-stage abstraction exactly.
It is a construction hypothesis for E0, not an E0 optimality claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .active_stages import build as active_build, stage_structure
from .construct import SharingIndex, derive_multicore_plan
from evaluation_validation import read_bandwidth_config


def partition(weights, stages):
    """Exact minimum largest contiguous segment sum, O(stages * n**2)."""
    n = len(weights)
    if not n or any(w <= 0 for w in weights) or not 1 <= stages <= n:
        raise ValueError('positive weights and 1 <= stages <= len(weights) required')
    prefix = [0]
    for w in weights:
        prefix.append(prefix[-1] + w)
    inf = float('inf')
    dp = [[inf] * (n + 1) for _ in range(stages + 1)]
    parent = [[None] * (n + 1) for _ in range(stages + 1)]
    dp[0][0] = 0
    for s in range(1, stages + 1):
        for end in range(s, n + 1):
            value, start = min((max(dp[s-1][start], prefix[end] - prefix[start]), start)
                               for start in range(s-1, end))
            dp[s][end], parent[s][end] = value, start
    cuts, end = [n], n
    for s in range(stages, 0, -1):
        end = parent[s][end]
        cuts.append(end)
    cuts.reverse()
    return cuts, dp[stages][n]


def build(index, cores, bandwidth):
    if not 1 <= cores <= 5:
        raise ValueError('official requested cores must be 1..5')
    views = stage_structure(index)
    jobs = index.components
    # Bound DP overhead independently of graph IDs; ordinary guarded chains
    # here have 3 or 124 positions. Longer chains retain the existing method.
    if views is None or len(jobs[0]) > 512 or len(jobs) < cores:
        plan, meta = active_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected='active_fallback', fallback=meta)
    positions = len(jobs[0])
    stages = min(cores, positions)
    weights = [index.duration(u) for u in jobs[0]]
    cuts, bottleneck = partition(weights, stages)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(u)] for job in jobs for u in job[left:right]]
                 for left, right in zip(cuts, cuts[1:])]
    schedules.extend([] for _ in range(cores - stages))
    plan = dict(node_to_subgraph=mapping, core_schedules=schedules)
    derive_multicore_plan(index.graph, plan)
    core_by_op = {job[pos]: c for job in jobs for c in range(stages)
                  for pos in range(cuts[c], cuts[c+1])}
    common, producers, consumers = views
    shared_bytes = [sum(index.sizes[t] for t in common
                        if any(core_by_op.get(u) == c for u in consumers[t]))
                    for c in range(stages)]
    cross_nets = [(t, p, c) for t, readers in consumers.items()
                  for p in {core_by_op[u] for u in producers[t] if u in core_by_op}
                  for c in {core_by_op[u] for u in readers if u in core_by_op}
                  if p != c]
    return plan, dict(
        guard=True, selected='pipeline_stages', requested_cores=cores,
        active_cores=stages, jobs=len(jobs), positions=positions, cuts=cuts,
        stage_compute_cycles=[sum(weights[l:r]) for l, r in zip(cuts, cuts[1:])],
        bottleneck_cycles=bottleneck,
        ideal_flowshop_cycles=sum(weights) + (len(jobs)-1) * bottleneck,
        shared_input_bytes_by_stage=shared_bytes,
        crossing_tensor_net_copies=len(cross_nets),
        crossing_tensor_net_bytes=sum(index.sizes[t] for t, _, _ in cross_nets),
        assumption='copy-free serial-server flowshop; not an E0 lower or upper bound')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[2] /
                    'data/raw/a/official/data/config.txt')
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    index = SharingIndex(json.loads(args.graph.read_text(encoding='utf-8')))
    plan, meta = build(index, args.cores, read_bandwidth_config(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
