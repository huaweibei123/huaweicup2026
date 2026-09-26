"""A fixed component/DDR construction rule on top of frontier_gap.

The service inequality is a heuristic derived from an ideal execution bound,
not a machine-level proof for the frozen floating-point evaluator. This module
never reads saved scores and never runs Step2, Step3, E0, or a candidate search.
"""
from __future__ import annotations

from collections import Counter

from .construct import UnsupportedStructure, derive_multicore_plan
from .frontier_gap import build as frontier_build, compact_certificate
from .physical_frontier import certificate


def service_profile(index, plan, bandwidth):
    """Count mandatory P2 COPY instances without compiling or simulating tasks.

    Inputs are copied once per consuming core; terminal outputs once per
    producing core. Tensor core-pairs and direct cross-core edges each create
    two copies. An empty copy still costs one normalized service cycle.
    Integer division gives exact ceil(size/bandwidth) in this restricted domain.
    """
    if type(bandwidth) is not int or not 0 < bandwidth <= 2**31:
        raise UnsupportedStructure('component gate requires integer bandwidth')
    if any('logical_tid' in t for t in index.tensors.values()):
        raise UnsupportedStructure('component gate does not certify tensor aliases')
    if any(type(t['size']) is not int or not 0 <= t['size'] <= 2**31
           for t in index.tensors.values()):
        raise UnsupportedStructure('component gate requires 0..2^31 integer sizes')
    if any(type(op.get('cycles', 1)) is not int or not 0 <= op.get('cycles', 1) <= 2**31
           for op in index.ops.values()):
        raise UnsupportedStructure('component gate requires 0..2^31 integer eligible durations')
    view = derive_multicore_plan(index.graph, plan)
    mapping = view['mapping']
    if len(set(mapping.values())) != len(mapping):
        raise UnsupportedStructure('component gate requires singleton subgraphs')
    core_of = {u: view['core_by_subgraph'][sg] for u, sg in mapping.items()}
    core_work = [0] * view['num_cores']
    # Eligible operations exclude COPY_IN/COPY_OUT. Frozen _op_duration then
    # returns max(1, cycles), including non-COMPUTE eligible operation names.
    for u, op in index.ops.items():
        core_work[core_of[u]] += max(1, op.get('cycles', 1))
    counts, byte_counts, work = Counter(), Counter(), Counter()
    links = 0

    def add(kind, count, size):
        counts[kind] += count
        byte_counts[kind] += count * size
        work[kind] += count * max(1, (size + bandwidth - 1) // bandwidth)

    for tid, tensor in index.tensors.items():
        producer = index.producer.get(tid)
        producer_cores = {core_of[producer]} if producer is not None else set()
        consumer_cores = {core_of[u] for u in index.consumers[tid]}
        add('input', len(consumer_cores) if not producer_cores else 0, tensor['size'])
        add('output', len(producer_cores) if tid in index.final else 0, tensor['size'])
        cross = sum(src != dst for src in producer_cores for dst in consumer_cores)
        add('tensor_cross', 2 * cross, tensor['size'])
        links += cross
    for edge in index.graph['edges']:
        src, dst = edge['source'], edge['target']
        if src not in core_of or dst not in core_of or core_of[src] == core_of[dst]:
            continue
        size = max(0, int(edge.get('data_size', 0)))
        if size > 2**31:
            raise UnsupportedStructure('component gate requires direct copy sizes <=2^31')
        add('direct_cross', 2, size)
        links += 1
    whole = all(len({core_of[u] for u in component}) <= 1 for component in index.components)
    return {'base_copy_count': sum(counts.values()),
            'base_copy_bytes': sum(byte_counts.values()),
            'base_copy_service_cycles': sum(work.values()),
            'copy_count_by_kind': dict(counts), 'copy_bytes_by_kind': dict(byte_counts),
            'copy_service_by_kind': dict(work), 'cross_core_links': links,
            'whole_components': whole, 'compute_work_by_core': core_work,
            'max_core_compute_work_cycles': max(core_work, default=0)}


def consider_alternative(index, alternative, incumbent, bandwidth, capacity):
    """Return a diagnostic decision for a fixed ordered pair, without scoring.

    A false decision retains incumbent; it never proves incumbent is better.
    Keeping every component on one core also excludes dependencies contracted
    through original COPY nodes, beyond the explicit P2 cross-link count.
    """
    a = service_profile(index, alternative, bandwidth)
    b = service_profile(index, incumbent, bandwidth)
    if len(a['compute_work_by_core']) != len(b['compute_work_by_core']):
        raise ValueError('candidate pair must use the same supplied core count')
    result = {'choose_alternative': False, 'A': a, 'B': b,
              'ideal_U_A': a['max_core_compute_work_cycles'] + a['base_copy_service_cycles'],
              'ideal_L_B': b['base_copy_service_cycles'],
              'interpretation': 'ideal-model heuristic; not an official machine certificate',
              'online_E0_calls': 0}
    if not a['whole_components'] or a['cross_core_links']:
        return {**result, 'reason': 'alternative has a split component or cross-core dependency'}
    if result['ideal_U_A'] >= result['ideal_L_B']:
        return {**result, 'reason': 'sufficient ideal inequality did not trigger'}
    cert = certificate(index, alternative, capacity)
    result['alternative_capacity_certificate'] = compact_certificate(cert)
    if (cert['base_copy_count'] != a['base_copy_count']
            or cert['base_copy_bytes'] != a['base_copy_bytes']):
        raise AssertionError('independent COPY and physical-token counts disagree')
    if not cert['certified']:
        return {**result, 'reason': 'alternative lacks the local no-spill certificate'}
    return {**result, 'choose_alternative': True,
            'reason': 'whole-component capacity certificate and ideal U_A < L_B'}


def build(index, cores, bandwidth, delay, capacity):
    """Construct F1 once, then at most one fixed tensor_packet alternative.

    O(k^2 T + E + V) service arithmetic follows existing candidate construction;
    candidate graph validation and ordering costs remain part of solver wall.
    """
    incumbent, base = frontier_build(index, cores, bandwidth, delay, capacity)
    meta = {'strategy': 'component_gate', 'selected': 'component_gate_keep_frontier',
            'base': base, 'outer_plan_count': 1, 'online_E0_calls': 0,
            'count_scope': 'returned F1 plan plus optional tensor plan; F1 internal constructions excluded',
            'capacity_certified': base.get('capacity_certified', False)}
    # The word route was already checked by F1 and is the same tensor route.
    if base['selected'] == 'frontier_resource_word':
        return incumbent, {**meta, 'reason': 'F1 already selected the guarded resource word'}
    if base.get('word_fallback_reason'):
        return incumbent, {**meta, 'reason': 'the tensor word alternative already failed F1 capacity'}
    try:
        profile = service_profile(index, incumbent, bandwidth)
    except UnsupportedStructure as error:
        return incumbent, {**meta, 'reason': str(error)}
    if not profile['cross_core_links']:
        return incumbent, {**meta, 'reason': 'no cross-core COPY pressure to target'}
    alternative, alternative_meta = index.build_tensor_plan(cores, bandwidth, delay)
    decision = consider_alternative(index, alternative, incumbent, bandwidth, capacity)
    meta.update(outer_plan_count=2, alternative=alternative_meta)
    meta['decision'] = decision
    if decision['choose_alternative']:
        meta.update(selected='component_gate_choose_tensor', capacity_certified=True)
        return alternative, meta
    return incumbent, meta
