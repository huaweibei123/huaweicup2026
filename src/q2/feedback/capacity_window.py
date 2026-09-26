"""Bound component admission by a conservative per-core memory envelope.

Refines shared-component routes using a heavy-component guard and memory.
Resource-word and existing general packet routes stay semantically unchanged.
No evaluator, spill planner, candidate-score loop or graph-ID rule is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from .construct import PIPES, ROOT, derive_multicore_plan
from .tensor_packet import TensorIndex


def footprint(index, sequence, excluded=()):
    """Peak whole-tensor bytes with all touches of a bucket simultaneous.

    Original DDR tensors become UB in P2. COPY_IN/OUT attached to a compute
    bucket do not move the first/last bucket of that tensor. This envelope
    deliberately includes both consumed and produced buffers before freeing.
    """
    excluded = set(excluded)
    first, last = {}, {}
    for position, u in enumerate(sequence):
        for tid in set(index.inputs[u]) | set(index.outputs[u]):
            if tid not in excluded:
                first.setdefault(tid, position)
                last[tid] = position
    adds = [{'L1': 0, 'UB': 0} for _ in sequence]
    frees = [{'L1': 0, 'UB': 0} for _ in sequence]
    for tid, start in first.items():
        tensor = index.tensors[tid]
        where = 'UB' if tensor['pos'] == 'DDR' else tensor['pos']
        adds[start][where] += tensor['size']
        frees[last[tid]][where] += tensor['size']
    live, peak = {'L1': 0, 'UB': 0}, {'L1': 0, 'UB': 0}
    for incoming, outgoing in zip(adds, frees):
        for where in live:
            live[where] += incoming[where]
            peak[where] = max(peak[where], live[where])
            live[where] -= outgoing[where]
    if any(live.values()):
        raise AssertionError('all envelope tensors must be released')
    return peak


def memory_window(index, jobs, capacity):
    """S + W*P bounds every prefix when at most W whole jobs are open.

    S reserves every input shared by multiple jobs on this core for the entire
    schedule. P is the largest private per-job footprint, separately per pool.
    This is conservative: rejected cores retain their original priorities.
    """
    counts = Counter(t for j in jobs for t in index.external_by_job[j])
    shared = {t for t, count in counts.items() if count > 1}
    reserved = {'L1': 0, 'UB': 0}
    for tid in shared:
        tensor = index.tensors[tid]
        where = 'UB' if tensor['pos'] == 'DDR' else tensor['pos']
        reserved[where] += tensor['size']
    peaks = [footprint(index, index.components[j], shared) for j in jobs]
    private = {where: max((p[where] for p in peaks), default=0) for where in capacity}
    width = index.window_size(jobs)
    for where in capacity:
        spare = capacity[where] - reserved[where]
        if spare < 0:
            width = 0
        elif private[where]:
            width = min(width, spare // private[where])
    return width, {'shared_reservation_bytes': reserved,
                   'private_peak_bytes': private,
                   'capacity_bytes': dict(capacity),
                   'window': width,
                   'envelope_bytes': {p: reserved[p] + width * private[p] for p in capacity}}


def build(index, cores, bandwidth, delay, capacity):
    if (set(capacity) != {'L1', 'UB'}
            or any(type(v) is not int or v < 0 for v in capacity.values())):
        raise ValueError('nonnegative integer L1 and UB capacity required')
    plan, original = index.build_tensor_plan(cores, bandwidth, delay)
    if original['selected'] == 'shared_cohorts':
        total_peak = max(sum(w[p] for w in index.work) for p in PIPES)
        target = (total_peak + cores - 1) // cores
        heavy = [j for j, work in enumerate(index.work)
                 if max(work.values()) > target]
        if heavy:
            # A few small repeated components must not prevent the existing
            # packet decomposition from exposing a dominant component's DAG.
            sequences, packet = index.packet_eft(cores, bandwidth, delay)
            mapping = plan['node_to_subgraph']
            answer = {'node_to_subgraph': mapping,
                      'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
            derive_multicore_plan(index.graph, answer)
            return answer, {'selected': 'heavy_component_packet_override',
                            'heavy_components': len(heavy), 'base': original,
                            'packet': packet, 'online_E0_calls': 0,
                            'scope': 'avoid whole-cohort routing across a dominant component; no spill certificate'}
    if (original['selected'] not in {'shared_stages', 'shared_cohorts'}
            or any('logical_tid' in t for t in index.tensors.values())):
        return plan, {'selected': 'capacity_window_guard_unchanged', 'base': original,
                      'online_E0_calls': 0}
    inverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
    mapping = plan['node_to_subgraph']
    schedules, details = [], []
    for schedule in plan['core_schedules']:
        sequence = [inverse[sg] for sg in schedule]
        # All components on these two routes are entirely assigned to one core.
        jobs = list(dict.fromkeys(index.owner[u] for u in sequence))
        if set(sequence) != {u for j in jobs for u in index.components[j]}:
            raise AssertionError('memory admission requires whole-component placement')
        if not jobs:
            schedules.append([])
            details.append({'window': 0, 'changed': False, 'reason': 'empty core'})
            continue
        width, detail = memory_window(index, jobs, capacity)
        if width < 1:
            schedules.append(schedule)
            details.append({**detail, 'changed': False,
                            'reason': 'conservative reservation cannot certify one job'})
            continue
        revised, clock = index.pipe_window(jobs, width, prefer_fill=False)
        observed_envelope = footprint(index, revised)
        if any(observed_envelope[p] > capacity[p] for p in capacity):
            raise AssertionError('admission envelope violated by generated priorities')
        schedules.append([mapping[str(u)] for u in revised])
        details.append({**detail, 'changed': revised != sequence,
                        'bucket_footprint_bytes': observed_envelope,
                        'priority_coordinates': clock})
    answer = {'node_to_subgraph': mapping, 'core_schedules': schedules}
    derive_multicore_plan(index.graph, answer)
    return answer, {'selected': 'capacity_window', 'base': original,
                    'cores': cores, 'core_details': details, 'online_E0_calls': 0,
                    'scope': 'sequential bucket memory envelope; no makespan or hardware optimality claim'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--config', type=Path, default=ROOT / 'data/raw/a/official/data/config.txt')
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
    plan, meta = build(TensorIndex(json.loads(args.graph.read_bytes())), args.cores,
                       config['bandwidth'], config['cross_core_copy_delay_cycles'], config['capacity'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n',
                           encoding='utf-8', newline='\n')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
