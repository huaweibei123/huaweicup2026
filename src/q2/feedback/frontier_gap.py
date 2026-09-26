"""Structure-first gap scheduling with physical bucket capacity certificates.

The homogeneous M-V*-M word is constructed before the general gap calendar.
Otherwise, only capacity-failing, whole-component cores receive one bounded
reordering. No evaluator, historical score, graph ID, or score search is used.
This first stage does not implement Pro's proposed DDR queue predictor.
"""
from __future__ import annotations

from collections import Counter
import math

from .capacity_window import footprint, memory_window
from .construct import UnsupportedStructure, derive_multicore_plan
from .gap_packet import build as gap_build
from .physical_frontier import certificate


def compact_certificate(report):
    """Retain each peak witness; omit the full token table from solver stdout."""
    return {**report, 'cores': [
        {key: value for key, value in core.items() if key != 'tokens'}
        for core in report['cores']]}


def repair_whole_cores(index, plan, capacity, original_certificate):
    """One deterministic bounded candidate for each uncertified whole core.

    Shared-input signature groups may permit narrower lifetimes than a global
    permanent reservation. The *complete* resulting sequence must still pass
    the bucket envelope; overlapping groups never implicitly free a tensor.
    """
    inverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
    mapping = plan['node_to_subgraph']
    schedules = [list(order) for order in plan['core_schedules']]
    details = []
    for core, order in enumerate(schedules):
        record = {'core': core, 'changed': False}
        if original_certificate['cores'][core]['certified']:
            record['reason'] = 'original core has a capacity certificate'
            details.append(record)
            continue
        sequence = [inverse[sg] for sg in order]
        jobs = list(dict.fromkeys(index.owner[u] for u in sequence))
        if set(sequence) != {u for job in jobs for u in index.components[job]}:
            record['reason'] = 'split component outside the repair domain'
            details.append(record)
            continue
        width, _ = memory_window(index, jobs, capacity)
        if width:
            groups = [jobs]
            widths = [width]
        else:
            counts = Counter(t for job in jobs for t in index.external_by_job[job])
            shared = {t for t, count in counts.items() if count > 1}
            grouped = {}
            for job in jobs:
                signature = tuple(sorted(index.external_by_job[job] & shared))
                grouped.setdefault(signature, []).append(job)
            groups = list(grouped.values())
            widths = [memory_window(index, group, capacity)[0] for group in groups]
        record['group_widths'] = widths
        if any(width < 1 for width in widths):
            record['reason'] = 'a signature group cannot admit one job'
            details.append(record)
            continue
        candidate = []
        for group, width in zip(groups, widths):
            revised, _ = index.pipe_window(group, width, prefer_fill=False)
            candidate.extend(revised)
        peak = footprint(index, candidate)
        record['candidate_bucket_peak_bytes'] = peak
        if any(peak[pool] > capacity[pool] for pool in capacity):
            record['reason'] = 'full sequence still exceeds capacity'
        else:
            schedules[core] = [mapping[str(u)] for u in candidate]
            record['changed'] = candidate != sequence
            record['reason'] = 'full sequence certified'
        details.append(record)
    answer = {'node_to_subgraph': dict(mapping), 'core_schedules': schedules}
    derive_multicore_plan(index.graph, answer)
    return answer, details


def build(index, cores, bandwidth, delay, capacity):
    if (type(cores) is not int or not 1 <= cores <= 5
            or type(bandwidth) not in (int, float) or not math.isfinite(bandwidth) or bandwidth <= 0
            or type(delay) is not int or delay < 0
            or set(capacity) != {'L1', 'UB'}
            or any(type(v) is not int or v < 0 for v in capacity.values())):
        raise ValueError('invalid core count or fixed capacity')
    # Keep aliases on the previously defined route without extending a proof.
    if any('logical_tid' in tensor for tensor in index.tensors.values()):
        plan, meta = gap_build(index, cores, bandwidth, delay, capacity)
        return plan, {'selected': 'frontier_alias_guard_unchanged', 'base': meta,
                      'capacity_certified': False, 'online_E0_calls': 0}
    word_failure = None
    try:
        index.word_descriptor()
    except UnsupportedStructure:
        pass
    else:
        plan, word_meta = index.build(cores, 'resource_word')
        cert = certificate(index, plan, capacity)
        if cert['certified']:
            return plan, {'selected': 'frontier_resource_word', 'word': word_meta,
                          'certificate': compact_certificate(cert),
                          'capacity_certified': True, 'online_E0_calls': 0}
        word_failure = 'resource word exceeds the physical bucket envelope'

    plan, meta = gap_build(index, cores, bandwidth, delay, capacity)
    original = certificate(index, plan, capacity)
    if original['certified']:
        return plan, {'selected': 'frontier_gap_certified_unchanged', 'base': meta,
                      'word_fallback_reason': word_failure,
                      'certificate': compact_certificate(original),
                      'capacity_certified': True, 'online_E0_calls': 0}
    candidate, details = repair_whole_cores(index, plan, capacity, original)
    changed = any(item['changed'] for item in details)
    final = certificate(index, candidate, capacity) if changed else original
    for item in details:
        if item['changed'] and not final['cores'][item['core']]['certified']:
            raise AssertionError('repaired core failed the physical token certificate')
    return candidate, {'selected': 'frontier_gap_capacity_repair' if changed else 'frontier_gap_unresolved',
                       'base': meta, 'word_fallback_reason': word_failure,
                       'repair': details, 'certificate': compact_certificate(final),
                       'capacity_certified': final['certified'], 'online_E0_calls': 0,
                       'scope': 'capacity stage only; split-component pressure may remain; no DDR timing or Makespan guarantee'}
