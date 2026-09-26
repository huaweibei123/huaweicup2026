"""Choose active cores analytically for strictly homogeneous shared-input chains.

The model compares compute load with all-miss, zero-spill COPY service demand.
It is a candidate construction heuristic, not a proof of actual makespan.
No official evaluator is called and no candidate schedules are trial-scored.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .construct import SharingIndex, derive_multicore_plan
from multicore_cut_evaluate_problem_1 import _original_tensor_views
from evaluation_validation import read_bandwidth_config


def stage_structure(index):
    jobs = index.components
    common = set.intersection(*index.inputs) if jobs else set()
    if not common or not all(all(v in index.succ[u] for u, v in zip(job, job[1:]))
                             for job in jobs):
        return None
    producers, consumers, _ = _original_tensor_views(index.graph)
    by_op = {u: [] for u in index.ops}
    for t in sorted(common):
        for u in consumers[t]:
            if u in by_op:
                by_op[u].append(t)
    signatures = [tuple((index.ops[u]['pipe'], index.duration(u), tuple(by_op[u]))
                        for u in job) for job in jobs]
    if len(set(signatures)) != 1:
        return None
    return common, producers, consumers


def resource_choices(index, cores, bandwidth, views):
    """At most k direct arithmetic models; no timeline or E0 evaluation."""
    if bandwidth <= 0 or not 1 <= cores <= 5:
        raise ValueError('positive bandwidth and 1..5 requested cores required')
    _, producers, consumers = views
    original_ops = {op['id']: op for op in index.graph['ops']}
    outputs = {t: {index.owner[u] for u in readers if u in index.owner}
               for t, readers in producers.items()
               if any(u in index.ops for u in readers)
               and (not any(u in index.ops for u in consumers[t])
                    or any(original_ops[u]['op'] == 'COPY_OUT' for u in consumers[t]))}
    rows = []
    for active in range(1, min(cores, len(index.components)) + 1):
        groups = index.assignment(active)
        core_by_job = {j: c for c, group in enumerate(groups) for j in group}
        compute = max(sum(index.work[j][p] for j in group)
                      for group in groups for p in range(len(index.pipes)))
        inputs = [set().union(*(index.inputs[j] for j in group)) for group in groups]
        in_service = sum(math.ceil(index.sizes[t] / bandwidth) for ts in inputs for t in ts)
        out_service = sum(len({core_by_job[j] for j in jobs}) * math.ceil(index.sizes[t] / bandwidth)
                          for t, jobs in outputs.items())
        ingress_bytes = sum(index.sizes[t] for ts in inputs for t in ts)
        rows.append(dict(active_cores=active, compute_pipe_load=compute,
                         all_miss_copy_service=in_service + out_service,
                         ingress_bytes=ingress_bytes,
                         model_cycles=max(compute, in_service + out_service)))
    return rows


def build(index, cores, bandwidth):
    views = stage_structure(index)
    if views is None:
        plan, meta = index.build_variant(cores, 'baseline')
        return plan, dict(guard=False, selected='baseline', fallback=meta)
    choices = resource_choices(index, cores, bandwidth, views)
    choice = min(choices, key=lambda row: (row['model_cycles'], row['ingress_bytes'], row['active_cores']))
    active = choice['active_cores']
    groups = index.assignment(active)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(index.components[j][pos])]
                  for pos in range(len(index.components[0])) for j in group]
                 for group in groups]
    schedules.extend([] for _ in range(cores - active))
    plan = dict(node_to_subgraph=mapping, core_schedules=schedules)
    derive_multicore_plan(index.graph, plan)
    return plan, dict(guard=True, selected='active_stages', requested_cores=cores,
                     active_cores=active, common_input_bytes=sum(index.sizes[t] for t in views[0]),
                     choices=choices, assumption='all-miss zero-spill service model; not an optimality guarantee')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[2] / 'data/raw/a/official/data/config.txt')
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    if not 1 <= args.cores <= 5:
        raise ValueError('official requested cores must be 1..5')
    index = SharingIndex(json.loads(args.graph.read_text(encoding='utf-8')))
    plan, meta = build(index, args.cores, read_bandwidth_config(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
