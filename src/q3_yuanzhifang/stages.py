"""Guarded stage alignment for homogeneous serial jobs sharing the same weights.

Adapts the time-band idea in archived Pro2 r02, using identical op positions
instead of sweeping band widths. Output is still the official two-field plan.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .construct import SharingIndex, derive_multicore_plan
from multicore_cut_evaluate_problem_1 import _original_tensor_views


def aligned_plan(index, cores):
    jobs = index.components
    common = set.intersection(*index.inputs) if jobs else set()
    if not common or not all(all(v in index.succ[u] for u, v in zip(job, job[1:]))
                             for job in jobs):
        return None, {'guard': False, 'reason': 'no common input or non-serial jobs'}
    _, consumers, _ = _original_tensor_views(index.graph)
    by_op = {u: [] for u in index.ops}
    for t in sorted(common):
        for u in consumers[t]:
            if u in by_op:
                by_op[u].append(t)
    signatures = [tuple((index.ops[u]['pipe'], index.duration(u), tuple(by_op[u]))
                        for u in job) for job in jobs]
    if len(set(signatures)) != 1:
        return None, {'guard': False, 'reason': 'different stage or shared-input signature'}
    groups = index.assignment(cores)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = []
    for group in groups:
        # Each job advances exactly one original op per layer. The common
        # input consumers are now contiguous in the public priority order.
        seq = [jobs[j][pos] for pos in range(len(jobs[0])) for j in group]
        schedules.append([mapping[str(u)] for u in seq])
    plan = {'node_to_subgraph': mapping, 'core_schedules': schedules}
    derive_multicore_plan(index.graph, plan)
    return plan, {'guard': True, 'selected': 'shared_stages', 'cores': cores,
                  'components': len(jobs), 'stages': len(jobs[0]),
                  'common_input_bytes': sum(index.sizes[t] for t in common)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    if not 1 <= args.cores <= 5:
        raise ValueError('cores must be 1..5')
    index = SharingIndex(json.loads(args.graph.read_text(encoding='utf-8')))
    plan, meta = aligned_plan(index, args.cores)
    if plan is None:
        plan, base = index.build_variant(args.cores, 'baseline')
        meta.update(fallback=base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
