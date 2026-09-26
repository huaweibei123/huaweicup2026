"""Partition homogeneous jobs with explicit first-job shared-input setup cost.

The DP is exact for a serial-stage cold-setup flowshop, not for official COPY,
cache, capacity or overlapping computation pipes. Only one plan is built.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .active_stages import stage_structure
from .construct import SharingIndex, derive_multicore_plan
from .pipeline_stages import build as pipeline_build
from evaluation_validation import read_bandwidth_config


def partition(weights, setups, stages, jobs):
    """Exact cold-setup serial-stage objective, O(stages * positions**2)."""
    n = len(weights)
    if (not n or len(setups) != n or any(w <= 0 for w in weights)
            or any(q < 0 for q in setups) or not 1 <= stages <= n
            or type(jobs) is not int or jobs < 1):
        raise ValueError('positive weights, nonnegative setups, valid stages/jobs required')
    work, cold = [0], [0]
    for w, q in zip(weights, setups):
        work.append(work[-1] + w)
        cold.append(cold[-1] + q)
    dp = [[float('inf')] * (n + 1) for _ in range(stages + 1)]
    parent = [[None] * (n + 1) for _ in range(stages + 1)]
    dp[0][0] = 0
    for s in range(1, stages + 1):
        for end in range(s, n + 1):
            value, start = min(
                (max(dp[s-1][start], cold[end] + (jobs-1) * (work[end]-work[start])), start)
                for start in range(s-1, end))
            dp[s][end], parent[s][end] = value, start
    cuts, end = [n], n
    for s in range(stages, 0, -1):
        end = parent[s][end]
        cuts.append(end)
    cuts.reverse()
    return cuts, work[-1] + dp[stages][n]


def build(index, cores, bandwidth):
    if not 1 <= cores <= 5 or bandwidth <= 0:
        raise ValueError('official cores 1..5 and positive bandwidth required')
    views = stage_structure(index)
    jobs = index.components
    reason = None
    if (views is None or len(jobs[0]) > 512 or len(jobs) < cores
            or any(o['pipe'] not in ('PIPE_M', 'PIPE_V') or
                   type(o['cycles']) is not int or o['cycles'] <= 0
                   for o in index.ops.values())):
        reason = 'homogeneous_positive_compute_guard'
    else:
        common, producers, consumers = views
        positions = len(jobs[0])
        location = {u: pos for job in jobs for pos, u in enumerate(job)}
        by_position = [[] for _ in range(positions)]
        for tid in sorted(common):
            used = {location[u] for u in consumers[tid] if u in location}
            # Without this guard, prefix setup cost would depend on prior cuts.
            if len(used) != 1:
                reason = 'shared_input_reused_at_multiple_positions'
                break
            by_position[next(iter(used))].append(tid)
    if reason is not None:
        plan, detail = pipeline_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected='pipeline_fallback', reason=reason,
                          fallback=detail)

    weights = [index.duration(u) for u in jobs[0]]
    setup = [sum(math.ceil(index.sizes[t] / bandwidth) for t in tids)
             for tids in by_position]
    stages = min(cores, positions)
    cuts, model = partition(weights, setup, stages, len(jobs))
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(u)] for job in jobs for u in job[left:right]]
                 for left, right in zip(cuts, cuts[1:])]
    schedules.extend([] for _ in range(cores-stages))
    plan = dict(node_to_subgraph=mapping, core_schedules=schedules)
    derive_multicore_plan(index.graph, plan)

    core_by_op = {u: c for c, (left, right) in enumerate(zip(cuts, cuts[1:]))
                  for job in jobs for u in job[left:right]}
    cross_nets = [(t, p, c) for t, readers in consumers.items()
                  for p in {core_by_op[u] for u in producers[t] if u in core_by_op}
                  for c in {core_by_op[u] for u in readers if u in core_by_op}
                  if p != c]
    return plan, dict(
        guard=True, selected='pipeline_cold_setup', requested_cores=cores,
        active_cores=stages, jobs=len(jobs), positions=positions, cuts=cuts,
        stage_compute_cycles=[sum(weights[l:r]) for l, r in zip(cuts, cuts[1:])],
        stage_first_job_setup_cycles=[sum(setup[l:r]) for l, r in zip(cuts, cuts[1:])],
        shared_input_bytes_by_stage=[sum(index.sizes[t] for tids in by_position[l:r]
                                        for t in tids) for l, r in zip(cuts, cuts[1:])],
        modeled_cold_flowshop_cycles=model,
        crossing_tensor_net_copies=len(cross_nets),
        crossing_tensor_net_bytes=sum(index.sizes[t] for t, _, _ in cross_nets),
        assumption='serial stages; first-job shared-input setup only; not an E0 bound')


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
