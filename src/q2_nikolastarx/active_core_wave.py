"""Choose active cores from a compute/input-traffic relaxation, then build once.

The model optimum is not an official makespan certificate. Memory bounds cover
raw priority touch intervals only, not COPY lowering or Step2/Step3 execution.
"""
from collections import Counter
import math

from . import component_envelope, shared_input_wave
from .direct import UnsupportedStructure


def choose_cores(jobs, budget, work, shared_bytes, private_bytes, bandwidth,
                 critical_path=0, minimum=1):
    """Minimize max(ceil(jobs/q)*work, ceil(input(q)/B), critical_path).

    Compute decreases and input traffic increases with q. Only the two sides
    of their first crossing need examination; normalize plateaus to fewer
    active cores. O(log(budget)) arithmetic, no constructed/scored candidates.
    """
    values = (jobs, budget, work, shared_bytes, private_bytes, bandwidth,
              critical_path, minimum)
    if any(type(v) is not int for v in values):
        raise ValueError('relaxation requires integer arguments')
    if not (jobs >= budget >= minimum >= 1 and bandwidth > 0
            and min(work, shared_bytes, private_bytes, critical_path) >= 0):
        raise ValueError('invalid workload or core domain')

    def compute(q):
        return ((jobs + q - 1) // q) * work

    def transfer(q):
        return (q * shared_bytes + private_bytes + bandwidth - 1) // bandwidth

    def cost(q):
        return max(compute(q), transfer(q), critical_path)

    lo, hi = minimum, budget + 1
    while lo < hi:
        mid = (lo + hi) // 2
        if compute(mid) <= transfer(mid):
            hi = mid
        else:
            lo = mid + 1
    candidates = [q for q in (lo - 1, lo) if minimum <= q <= budget]
    optimum = min(cost(q) for q in candidates)
    # Among minimizers, take the earliest compute-feasible point. Transfer is
    # nondecreasing, so moving left from a minimizer preserves feasibility.
    q = minimum if work == 0 else max(minimum, (jobs + optimum // work - 1) // (optimum // work))
    assert minimum <= q <= budget and cost(q) == optimum
    return q, {'model_objective_cycles': optimum,
               'compute_load_cycles': compute(q), 'input_service_cycles': transfer(q),
               'critical_path_cycles': critical_path, 'crossing_candidates': candidates}


def choose_from_index(index, cores, config):
    """Read workload/lifetime statistics and select a count; emit no plan."""
    if type(cores) is not int or not 1 <= cores <= len(index.components):
        raise ValueError('requires 1 <= cores <= components')
    if any(type(op['cycles']) is not int or op['cycles'] <= 0
           or op['pipe'] not in ('PIPE_M', 'PIPE_V') for op in index.ops.values()):
        raise UnsupportedStructure('active-core model requires positive integer M/V work')
    bandwidth = config['bandwidth']
    if (type(bandwidth) not in (int, float) or not math.isfinite(bandwidth)
            or bandwidth <= 0 or int(bandwidth) != bandwidth):
        raise UnsupportedStructure('active-core model requires positive integral bandwidth')
    capacity = config['capacity']
    if set(capacity) != {'L1', 'UB'} or any(type(v) is not int or v < 0 for v in capacity.values()):
        raise ValueError('invalid capacities')
    by_job, waves, anchor = shared_input_wave._recognize(index)
    shared = set(waves)
    if any(index.tensors[t]['pos'] not in ('L1', 'UB') for t in shared):
        raise UnsupportedStructure('shared inputs must target L1 or UB')
    work = Counter()
    finish = {}
    for u in index.components[0]:
        work[index.ops[u]['pipe']] += index.duration(u)
        finish[u] = index.duration(u) + max((finish[v] for v in index.pred[u]), default=0)
    external = {t for u in index.ops for t in index.inputs[u] if not index.producers[t]}
    shared_max, private_peak = Counter(), Counter()
    for t in shared:
        p = shared_input_wave._pool(index.tensors[t])
        shared_max[p] = max(shared_max[p], index.tensors[t]['size'])
    # Private aliasing and ID-dependent closure order may differ between jobs.
    # Scan every actual single-job projection instead of extrapolating job 0.
    for j, job in enumerate(index.components):
        private = {t for u in job for t in index.inputs[u] + index.outputs[u]} - shared
        sequence = shared_input_wave._sequence(index, [j], by_job, waves, anchor)
        peak = component_envelope._private_peak(index, sequence, private)
        for p in capacity:
            private_peak[p] = max(private_peak[p], peak.get(p, 0))
    jobs = len(index.components)
    allowed = jobs
    for p in capacity:
        room = capacity[p] - shared_max[p]
        if room < 0:
            allowed = 0
        elif private_peak[p]:
            allowed = min(allowed, room // private_peak[p])
    required = (jobs + allowed - 1) // allowed if allowed else cores + 1
    if required > cores:
        selected, model = cores, {'capacity_guard': 'no certified reduction; retain requested cores'}
    else:
        selected, model = choose_cores(
            jobs, cores, max(work.values()), sum(index.tensors[t]['size'] for t in shared),
            sum(index.tensors[t]['size'] for t in external - shared), int(bandwidth),
            max(finish.values()), required)
    return selected, {'requested_cores': cores, 'active_cores': selected,
                  'components': jobs, 'per_job_pipe_work': dict(work),
                  'shared_input_bytes': sum(index.tensors[t]['size'] for t in shared),
                  'private_input_bytes': sum(index.tensors[t]['size'] for t in external - shared),
                  'raw_private_peak_max': dict(private_peak),
                  'raw_shared_wave_max': dict(shared_max),
                  'raw_capacity_jobs_per_core_bound': allowed,
                  'core_choice': model, 'official_optimality_claim': False}


def build_from_index(index, cores, config):
    selected, choice = choose_from_index(index, cores, config)
    plan, detail = shared_input_wave.build_from_index(index, selected, config)
    plan['core_schedules'].extend([] for _ in range(cores - selected))
    return plan, {**detail, **choice, 'cores': cores, 'selected_strategy': 'active_core_shared_wave'}
