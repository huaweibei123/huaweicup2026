"""Capacity-guarded contiguous template cut for an ideal finite-job tandem.

The scalar flow-shop objective is not an official Makespan prediction. This
module does not call E0/E2 or the P2 task builder.
"""
from __future__ import annotations

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .shared_input_wave import _recognize
from .template_capacity_pipeline import _segment_bounds
from .zero_spill_intervals import certify

MAX_TEMPLATE_OPS = 256
MAX_TRANSITIONS = 2_000_000


def _prune(labels):
    """Keep (max stage, min sum) Pareto labels and lexicographic cut ties."""
    best_for_max = {}
    for maximum, total, cuts in labels:
        candidate = (total, cuts)
        if maximum not in best_for_max or candidate < best_for_max[maximum]:
            best_for_max[maximum] = candidate
    result = []
    lowest_sum = None
    best_cuts_at_sum = None
    for maximum, (total, cuts) in sorted(best_for_max.items()):
        if (lowest_sum is None or total < lowest_sum or
                (total == lowest_sum and cuts < best_cuts_at_sum)):
            result.append((maximum, total, cuts))
            lowest_sum = total
            best_cuts_at_sum = cuts
    return result


def build_from_index(index, cores: int, config: dict) -> tuple[dict, dict]:
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    capacity = config['capacity']
    if set(capacity) != {'L1', 'UB'} or any(
            type(capacity[p]) is not int or capacity[p] < 0 for p in ('L1', 'UB')):
        raise UnsupportedStructure('requires nonnegative integer L1/UB capacities')
    delay = config['cross_core_copy_delay_cycles']
    if type(delay) is not int or delay < 0:
        raise UnsupportedStructure('requires nonnegative integer cross-core delay')
    by_job, shared, anchor = _recognize(index)
    template = index.components[0]
    n = len(template)
    if n > MAX_TEMPLATE_OPS:
        raise UnsupportedStructure('template exceeds exact DP size guard')
    sig_of = {u: sig for sig, u in by_job[0].items()}
    sig_order = [sig_of[u] for u in template]
    for row in by_job:
        pos = {row[sig]: q for q, sig in enumerate(sig_order)}
        if len(pos) != n or any(pos[u] >= pos[v] for u in pos
                                for v in index.succ[u] if v in pos):
            raise UnsupportedStructure('template order not topological in every job')
    upper = _segment_bounds(index, template, set(shared))
    pipes = sorted({index.ops[u]['pipe'] for u in template})
    prefix = {p: [0] for p in pipes}
    for u in template:
        for p in pipes:
            prefix[p].append(prefix[p][-1] +
                             (index.duration(u) if index.ops[u]['pipe'] == p else 0))
    stage = [[0] * (n + 1) for _ in range(n)]
    feasible = [[False] * (n + 1) for _ in range(n)]
    for a in range(n):
        for b in range(a + 1, n + 1):
            feasible[a][b] = all(upper[a][b][p] <= capacity[p]
                                 for p in ('L1', 'UB'))
            stage[a][b] = max(prefix[p][b] - prefix[p][a] for p in pipes)
    kmax = min(cores, n)
    # A label is (max_segment_duration, sum_segment_durations, cut_tuple).
    dp = [[[] for _ in range(n + 1)] for _ in range(kmax + 1)]
    dp[0][0] = [(0, 0, (0,))]
    transitions = 0
    for count in range(1, kmax + 1):
        for b in range(count, n + 1):
            candidates = []
            for a in range(count - 1, b):
                if not feasible[a][b]:
                    continue
                duration = stage[a][b]
                for maximum, total, cuts in dp[count - 1][a]:
                    transitions += 1
                    if transitions > MAX_TRANSITIONS:
                        raise UnsupportedStructure('exact DP transition budget exceeded')
                    candidates.append((max(maximum, duration), total + duration,
                                       cuts + (b,)))
            dp[count][b] = _prune(candidates)
    jobs = len(by_job)
    choices = [(total + (jobs - 1) * maximum + (count - 1) * delay,
                count, cuts, maximum, total)
               for count in range(1, kmax + 1)
               for maximum, total, cuts in dp[count][n]]
    if not choices:
        raise UnsupportedStructure('no capacity-feasible contiguous template partition')
    objective, active, cuts, maximum, total = min(choices)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    rows = [[] for _ in range(cores)]
    for core, (a, b) in enumerate(zip(cuts, cuts[1:])):
        for job in range(jobs):
            for q in range(a, b):
                rows[core].append(mapping[str(by_job[job][sig_order[q]])])
    plan = {'node_to_subgraph': mapping, 'core_schedules': rows}
    derive_multicore_plan(index.graph, plan)
    checked = certify(index.graph, plan, config)
    if not checked['supported'] or not checked['zero_spill_certificate']:
        raise UnsupportedStructure('independent capacity certificate disagrees')
    return plan, {
        'selected_strategy': 'template_finite_job_pipeline',
        'jobs': jobs, 'template_ops': n, 'requested_cores': cores,
        'active_cores': active, 'template_bounds': list(cuts),
        'scalar_segment_cycles': [stage[a][b] for a, b in zip(cuts, cuts[1:])],
        'scalar_sum_cycles': total, 'scalar_bottleneck_cycles': maximum,
        'scalar_flowshop_objective_cycles': objective,
        'dp_transitions': transitions,
        'segment_upper_bounds_bytes': [upper[a][b] for a, b in zip(cuts, cuts[1:])],
        'zero_spill_diagnostic': checked,
        'official_score_available': False,
        'limitations': ['scalar serial-stage tandem only, not official Makespan',
                        'COPY service, shared DDR, multiple Pipes and Step3 omitted'],
    }


def build(graph: dict, cores: int, config: dict) -> tuple[dict, dict]:
    return build_from_index(DAGIndex(graph), cores, config)
