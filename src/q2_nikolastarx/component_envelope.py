"""Whole-component ownership with bounded priority-frontier cohort merging.

No E0, no parameter grid. Certificates concern raw tensors in the submitted
priority order, not spill-free Step2/Step3 execution. See DAG_PILOT_DIAGNOSIS.md.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import heapq

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan

POOLS = ('L1', 'UB')


def _pool(tensor):
    return 'UB' if tensor['pos'] == 'DDR' else tensor['pos']


def _private_peak(index, job, private):
    """Inclusive original-op touch intervals, a conservative stage envelope."""
    first, last = {}, {}
    for position, u in enumerate(job):
        for t in set(index.inputs[u]) | set(index.outputs[u]):
            if t in private:
                first.setdefault(t, position)
                last[t] = position
    changes = defaultdict(Counter)
    for t in first:
        tensor = index.tensors[t]
        changes[first[t]][_pool(tensor)] += tensor['size']
        changes[last[t] + 1][_pool(tensor)] -= tensor['size']
    live, peak = Counter(), Counter()
    for position in range(len(job)):
        live.update(changes[position])
        for pool in POOLS:
            peak[pool] = max(peak[pool], live[pool])
    return dict(peak)


def _merge_heads(index, jobs):
    """Interleave only next op of each job; preserve its complete local order."""
    if len(jobs) == 1:
        return list(jobs[0])
    queues = defaultdict(list)
    pipe_free = Counter()
    offset = [0] * len(jobs)
    remaining = [sum(index.duration(u) for u in job) for job in jobs]

    def push(j, release):
        u = jobs[j][offset[j]]
        heapq.heappush(queues[index.ops[u]['pipe']], (release, -remaining[j], u, j))

    for j in range(len(jobs)):
        push(j, 0)
    result = []
    while any(queues.values()):
        choices = [(max(pipe_free[p], q[0][0]), q[0][1], q[0][2], q[0][3], p)
                   for p, q in queues.items() if q]
        start, _, u, j, pipe = min(choices)
        heapq.heappop(queues[pipe])
        finish = start + index.duration(u)
        pipe_free[pipe] = finish
        result.append(u)
        remaining[j] -= index.duration(u)
        offset[j] += 1
        if offset[j] < len(jobs[j]):
            push(j, finish)
    return result


def build(graph, cores, config):
    return build_from_index(DAGIndex(graph), cores, config)


def build_from_index(index, cores, config):
    """Reuse an immutable prepared index; semantics match build(graph, ...)."""
    graph = index.graph
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    if len(index.components) < cores:
        raise UnsupportedStructure('whole-component envelope requires at least as many components as cores')
    capacity = config['capacity']
    if set(capacity) != set(POOLS) or any(type(capacity[p]) is not int or capacity[p] < 0 for p in POOLS):
        raise ValueError('capacity must contain nonnegative integer L1 and UB bytes')
    components = index.components
    groups = index.assignment(cores)
    job_tensors = [{t for u in job for t in set(index.inputs[u]) | set(index.outputs[u])}
                   for job in components]
    sequences, core_detail = [], []
    for core, group in enumerate(groups):
        tensor_jobs = defaultdict(list)
        for j in group:
            for t in sorted(job_tensors[j]):
                tensor_jobs[t].append(j)
        shared = {t for t, js in tensor_jobs.items() if len(js) > 1}
        # Retain the existing deterministic component order. Shared-input
        # lifetime is measured across that order, not presumed to end at a
        # cohort boundary. No affinity sort or tunable lookahead is introduced.
        position = {j: p for p, j in enumerate(group)}
        first = defaultdict(list)
        last = defaultdict(list)
        for t in sorted(shared):
            indices = [position[j] for j in tensor_jobs[t]]
            first[min(indices)].append(t)
            last[max(indices)].append(t)
        peaks = {j: _private_peak(index, components[j], job_tensors[j] - shared)
                 for j in group}
        active = Counter()  # Shared input retained before this component position.
        cohort_shared = Counter()
        cohort_private = Counter()
        cohort = []
        sequence, records = [], []

        def close():
            nonlocal cohort, cohort_shared, cohort_private
            if not cohort:
                return
            envelope = {p: cohort_shared[p] + cohort_private[p] for p in POOLS}
            records.append({'components': list(cohort),
                            'shared_reserve_bytes': {p: cohort_shared[p] for p in POOLS},
                            'private_peak_sum_bytes': {p: cohort_private[p] for p in POOLS},
                            'raw_priority_envelope_bytes': envelope,
                            'within_capacity': all(envelope[p] <= capacity[p] for p in POOLS)})
            sequence.extend(_merge_heads(index, [components[j] for j in cohort]))
            cohort = []
            cohort_shared = Counter(active)
            cohort_private = Counter()

        for i, j in enumerate(group):
            new = Counter()
            for t in first[i]:
                new[_pool(index.tensors[t])] += index.tensors[t]['size']
            trial_shared = cohort_shared + new
            trial_private = cohort_private + Counter(peaks[j])
            if cohort and any(trial_shared[p] + trial_private[p] > capacity[p] for p in POOLS):
                close()
                trial_shared = Counter(active) + new
                trial_private = Counter(peaks[j])
            cohort.append(j)
            cohort_shared, cohort_private = trial_shared, trial_private
            active.update(new)
            for t in last[i]:
                active[_pool(index.tensors[t])] -= index.tensors[t]['size']
            if any(cohort_shared[p] + cohort_private[p] > capacity[p] for p in POOLS):
                # No false memory certificate: an oversized singleton is simply
                # closed, so it cannot inflate another component's frontier.
                close()
        close()
        sequences.append(sequence)
        core_detail.append({'core': core, 'components': len(group),
                            'shared_tensors': len(shared),
                            'cohorts': records,
                            'max_open_components_bound': max((len(r['components']) for r in records), default=0),
                            'all_raw_envelopes_fit': all(r['within_capacity'] for r in records)})
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
    derive_multicore_plan(graph, plan)
    return plan, {'selected_strategy': 'component_envelope', 'eligible_ops': len(index.ops),
                  'components': len(components), 'cores': cores,
                  'capacity_bytes': dict(capacity), 'per_core': core_detail,
                  'certificate_scope': 'raw tensor priority-prefix envelope and component open-count only',
                  'zero_spill_claim': False,
                  'limitations': ['shared input residency spans cohorts and is retained in reserves',
                                  'oversized singleton cohorts are emitted without a memory certificate',
                                  'no Step2/Step3 or global runtime feasibility guarantee']}


def main():
    """Matrix direct-solver CLI; only structural checks, zero online scores."""
    import argparse
    from datetime import datetime, timezone
    import hashlib
    import json
    from pathlib import Path
    import time
    from .baseline import ROOT
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config

    def dump(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT/'data/raw/a/official/data/config.txt')
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--wall', type=float, default=240)
    args = parser.parse_args()
    started = time.perf_counter()
    args.evidence.mkdir(parents=True, exist_ok=False)
    ledger = {'status': 'running', 'calls': {'E0': 0, 'E1': 0, 'E2': 0},
              'attempts': [], 'started_at': datetime.now(timezone.utc).isoformat(),
              'validation_scope': 'official structural validation; raw priority envelope only, not E0 or zero-spill'}
    try:
        graph = json.loads(args.graph.read_text())
        config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
        plan, detail = build(graph, args.cores, config)
        folder = args.evidence/'component_envelope'
        folder.mkdir()
        dump(folder/'plan.json', plan)
        raw = (folder/'plan.json').read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        ledger['attempts'].append({'name': 'component_envelope', 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter() - started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(raw)
        ledger.update(status='ok', selected='component_envelope', plan_sha256=digest,
                      stop_reason='single_structural_route_completed')
    except Exception as error:
        ledger.update(status='failed', error=repr(error))
    finally:
        ledger.update(finished_at=datetime.now(timezone.utc).isoformat(),
                      internal_wall_seconds=time.perf_counter()-started)
        dump(args.evidence/'solver.json', ledger)
    print(json.dumps({'status': ledger['status'], 'calls': ledger['calls'],
                      'internal_wall_seconds': ledger['internal_wall_seconds']}))
    if ledger['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
