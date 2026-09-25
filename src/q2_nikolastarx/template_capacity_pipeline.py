"""Capacity-guarded contiguous template partition with job-major priorities.

No official task builder, Step2, E0, E2, or Makespan prediction is run.
"""
from __future__ import annotations

from fractions import Fraction

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .shared_input_wave import _recognize
from .zero_spill_intervals import certify


class _RangeMax:
    def __init__(self, n):
        self.n = n
        self.value = [0] * (4 * n)
        self.lazy = [0] * (4 * n)

    def add(self, left, right, amount, node=1, lo=0, hi=None):
        if hi is None:
            hi = self.n - 1
        if left <= lo and hi <= right:
            self.value[node] += amount
            self.lazy[node] += amount
            return
        mid = (lo + hi) // 2
        if left <= mid:
            self.add(left, right, amount, node * 2, lo, mid)
        if right > mid:
            self.add(left, right, amount, node * 2 + 1, mid + 1, hi)
        self.value[node] = self.lazy[node] + max(self.value[node * 2],
                                                  self.value[node * 2 + 1])

    @property
    def maximum(self):
        return self.value[1]


def _segment_bounds(index, template_ops, shared):
    """Return all [a,b) shared+one-job private upper bounds by pool."""
    n = len(template_ops)
    by_op = []
    tensor_info = {t: (('UB' if data['pos'] == 'DDR' else data['pos']),
                       data['size']) for t, data in index.tensors.items()}
    for u in template_ops:
        by_op.append(set(index.inputs[u]) | set(index.outputs[u]))
    bounds = [[None] * (n + 1) for _ in range(n)]
    for a in range(n):
        trees = {p: _RangeMax(n) for p in ('L1', 'UB')}
        last_touch = {}
        shared_sum = {'L1': 0, 'UB': 0}
        for b in range(a, n):
            for tid in by_op[b]:
                pool, size = tensor_info[tid]
                if pool not in trees or type(size) is not int or size < 0:
                    raise UnsupportedStructure('tensor pool/size outside capacity guard')
                if tid in shared:
                    if tid not in last_touch:
                        shared_sum[pool] += size
                elif tid in last_touch:
                    trees[pool].add(last_touch[tid] + 1, b, size)
                else:
                    trees[pool].add(b, b, size)
                last_touch[tid] = b
            bounds[a][b + 1] = {p: shared_sum[p] + trees[p].maximum
                                 for p in ('L1', 'UB')}
    return bounds


def build_from_index(index, cores: int, config: dict) -> tuple[dict, dict]:
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    capacity = config['capacity']
    if set(capacity) != {'L1', 'UB'} or any(
            type(capacity[p]) is not int or capacity[p] < 0 for p in ('L1', 'UB')):
        raise UnsupportedStructure('requires nonnegative integer L1/UB capacities')
    by_job, shared, anchor = _recognize(index)
    template = index.components[0]
    n = len(template)
    signatures = {u: sig for sig, u in by_job[0].items()}
    sig_order = [signatures[u] for u in template]
    for row in by_job:
        position = {row[sig]: q for q, sig in enumerate(sig_order)}
        if any(position[u] >= position[v] for u in position
               for v in index.succ[u] if v in position):
            raise UnsupportedStructure('template order is not job-topological')
    upper = _segment_bounds(index, template, set(shared))
    pipes = sorted({index.ops[u]['pipe'] for u in template})
    prefix = {p: [0] for p in pipes}
    for u in template:
        for p in pipes:
            prefix[p].append(prefix[p][-1] +
                             (index.duration(u) if index.ops[u]['pipe'] == p else 0))
    total = {p: prefix[p][-1] for p in pipes}
    k = min(cores, n)
    dp = [[None] * (n + 1) for _ in range(k + 1)]
    prev = [[None] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = Fraction(0)
    for count in range(1, k + 1):
        for b in range(count, n + 1):
            choices = []
            for a in range(count - 1, b):
                if dp[count - 1][a] is None or any(
                        upper[a][b][p] > capacity[p] for p in ('L1', 'UB')):
                    continue
                score = max(Fraction(prefix[p][b] - prefix[p][a], total[p])
                            for p in pipes if total[p])
                choices.append((max(dp[count - 1][a], score), a))
            if choices:
                dp[count][b], prev[count][b] = min(choices)
    feasible = next((count for count in range(k, 0, -1)
                     if dp[count][n] is not None), None)
    if feasible is None:
        raise UnsupportedStructure('no capacity-feasible contiguous template partition')
    cuts = [n]
    b = n
    for count in range(feasible, 0, -1):
        b = prev[count][b]
        cuts.append(b)
    cuts.reverse()
    mapping = {str(u): i for i, u in enumerate(index.order)}
    rows = [[] for _ in range(cores)]
    for core, (a, b) in enumerate(zip(cuts, cuts[1:])):
        for job in range(len(by_job)):
            for q in range(a, b):
                rows[core].append(mapping[str(by_job[job][sig_order[q]])])
    plan = {'node_to_subgraph': mapping, 'core_schedules': rows}
    derive_multicore_plan(index.graph, plan)
    checked = certify(index.graph, plan, config)
    if not checked['supported'] or not checked['zero_spill_certificate']:
        raise UnsupportedStructure('independent certificate disagrees with segment bound')
    return plan, {'selected_strategy': 'template_capacity_job_pipeline',
                  'jobs': len(by_job), 'template_ops': n, 'active_cores': feasible,
                  'template_bounds': cuts, 'normalized_minimax_work': str(dp[feasible][n]),
                  'segment_upper_bounds_bytes': [upper[a][b]
                                                 for a, b in zip(cuts, cuts[1:])],
                  'shared_inputs': len(shared), 'zero_spill_diagnostic': checked,
                  'official_score_available': False,
                  'limitations': ['pre-Step2 capacity only; no Makespan guarantee',
                                  'no shared DDR/COPY queue or Step3 model']}


def build(graph: dict, cores: int, config: dict) -> tuple[dict, dict]:
    return build_from_index(DAGIndex(graph), cores, config)
