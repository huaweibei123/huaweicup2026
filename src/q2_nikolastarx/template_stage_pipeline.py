"""Deterministic contiguous template-stage pipeline for independent jobs.

Priorities are not official start times. This module does no scoring or search.
"""
from __future__ import annotations

from fractions import Fraction

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .shared_input_wave import _recognize
from .zero_spill_intervals import certify


def _cut_template(index, template_ops, cores):
    """Exact minimax contiguous per-pipe normalized work partition.

    Tie-break by smaller previous cut; O(cores * stages**2 * pipes).
    """
    pipes = sorted({index.ops[u]['pipe'] for u in template_ops})
    n = len(template_ops)
    k = min(cores, n)
    prefix = {p: [0] for p in pipes}
    for u in template_ops:
        for p in pipes:
            prefix[p].append(prefix[p][-1] +
                             (index.duration(u) if index.ops[u]['pipe'] == p else 0))
    total = {p: prefix[p][-1] for p in pipes}

    def stage_cost(a, b):
        return max((Fraction(prefix[p][b] - prefix[p][a], total[p])
                    for p in pipes if total[p]), default=Fraction(0))

    costs = [[Fraction(0)] * (n + 1) for _ in range(n + 1)]
    for a in range(n):
        for b in range(a + 1, n + 1):
            costs[a][b] = stage_cost(a, b)
    dp = [[None] * (n + 1) for _ in range(k + 1)]
    previous = [[None] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = Fraction(0)
    for count in range(1, k + 1):
        for b in range(count, n + 1):
            choices = ((max(dp[count - 1][a], costs[a][b]), a)
                       for a in range(count - 1, b) if dp[count - 1][a] is not None)
            dp[count][b], previous[count][b] = min(choices)
    bounds = [n]
    b = n
    for count in range(k, 0, -1):
        b = previous[count][b]
        bounds.append(b)
    bounds.reverse()
    return bounds, dp[k][n], pipes, prefix, total


def _build_from_index(index, cores: int, config: dict, *, job_major: bool) -> tuple[dict, dict]:
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    by_job, shared, anchor = _recognize(index)
    if not by_job or not by_job[0]:
        raise UnsupportedStructure('empty template')
    # _recognize interns signatures in the first job; recover that job's actual
    # topological order, then reuse its signature positions in every job.
    template_ops = [u for u in index.components[0]]
    signature_of_first = {u: sig for sig, u in by_job[0].items()}
    signature_order = [signature_of_first[u] for u in template_ops]
    if len(signature_order) != len(by_job[0]):
        raise UnsupportedStructure('template does not cover first component')
    for job, row in enumerate(by_job):
        position = {row[sig]: i for i, sig in enumerate(signature_order)}
        if len(position) != len(index.components[job]) or any(
                position[u] >= position[v]
                for u in index.components[job] for v in index.succ[u]
                if v in position):
            raise UnsupportedStructure('template order is not topological in every job')
    bounds, objective, pipes, prefix, total = _cut_template(index, template_ops, cores)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    rows = [[] for _ in range(cores)]
    owner_of_signature = {}
    for core, (a, b) in enumerate(zip(bounds, bounds[1:])):
        for q in range(a, b):
            sig = signature_order[q]
            owner_of_signature[sig] = core
        if job_major:
            for job in range(len(by_job)):
                for q in range(a, b):
                    rows[core].append(mapping[str(by_job[job][signature_order[q]])])
        else:
            for q in range(a, b):
                for job in range(len(by_job)):
                    rows[core].append(mapping[str(by_job[job][signature_order[q]])])
    plan = {'node_to_subgraph': mapping, 'core_schedules': rows}
    derive_multicore_plan(index.graph, plan)
    # Count actual cores per external shared input, not merely template intent.
    core_by_op = {by_job[job][sig]: core
                  for sig, core in owner_of_signature.items()
                  for job in range(len(by_job))}
    shared_cores = {}
    for tid in shared:
        shared_cores[tid] = sorted({core_by_op[by_job[job][anchor[tid]]]
                                  for job in range(len(by_job))})
    if any(len(owners) != 1 for owners in shared_cores.values()):
        raise AssertionError('shared input split over cores')
    capacity = certify(index.graph, plan, config)
    stage_work = [
        {p: prefix[p][b] - prefix[p][a] for p in pipes}
        for a, b in zip(bounds, bounds[1:])
    ]
    return plan, {
        'selected_strategy': ('template_job_pipeline' if job_major
                              else 'template_stage_pipeline'),
        'priority_order': 'job_major' if job_major else 'stage_major',
        'jobs': len(by_job), 'template_ops': len(signature_order),
        'active_cores': len(bounds) - 1, 'requested_cores': cores,
        'template_bounds': bounds, 'per_job_stage_pipe_work': stage_work,
        'total_per_job_pipe_work': total,
        'normalized_minimax_work': str(objective),
        'shared_inputs': len(shared), 'shared_input_core_count_max': 1,
        'zero_spill_diagnostic': capacity,
        'official_score_available': False,
        'limitations': ['fixed owner by template stage, not a Step3 time schedule',
                        'zero-spill diagnostic may reject or exceed capacity',
                        'no shared DDR, COPY queue, or Makespan prediction'],
    }


def build(graph: dict, cores: int, config: dict) -> tuple[dict, dict]:
    return build_from_index(DAGIndex(graph), cores, config)


def build_from_index(index, cores: int, config: dict) -> tuple[dict, dict]:
    """Original stage-major priority; retained as the default API."""
    return _build_from_index(index, cores, config, job_major=False)


def build_job_pipeline_from_index(index, cores: int, config: dict) -> tuple[dict, dict]:
    """Within each fixed stage owner, finish one job's local segment at a time."""
    return _build_from_index(index, cores, config, job_major=True)


def build_job_pipeline(graph: dict, cores: int, config: dict) -> tuple[dict, dict]:
    return build_job_pipeline_from_index(DAGIndex(graph), cores, config)
