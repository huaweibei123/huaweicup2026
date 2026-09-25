"""Conditional pre-Step2 zero-spill certificate for singleton P2 priorities.

No P2 task builder, Step2, E0, or E2 is called here. The certificate uses the
frozen P2 pre-Step2 COPY placement rules and Step2 alloc-before-free semantics.
It is not a Makespan, memory-credit, or Step3 execution guarantee.
"""
from __future__ import annotations

from collections import defaultdict

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan

# Import direct first: it installs the frozen official code directory.
from multicore_cut_evaluate_problem_1 import _original_tensor_views


def certify(graph: dict, plan: dict, config: dict) -> dict:
    """Return support status and exact pre-Spill closed-touch peaks, in bytes.

    A supported False result makes no assertion about Step2. A supported True
    result with zero_spill_certificate False only says the unspilled priority
    trace exceeds capacity: Step2 may insert spill or fail, and E2 can still
    be worth running.
    """
    try:
        return _certify(graph, plan, config)
    except (UnsupportedStructure, ValueError, KeyError) as error:
        return {'supported': False, 'reason': str(error), 'peaks': None,
                'per_core': None, 'zero_spill_certificate': None,
                'scope': 'No claim outside the guarded singleton pre-Step2 domain.'}


def _certify(graph: dict, plan: dict, config: dict) -> dict:
    capacity = config['capacity']
    if (set(capacity) != {'L1', 'UB'} or any(type(capacity[p]) is not int
        or capacity[p] < 0 for p in ('L1', 'UB'))):
        raise UnsupportedStructure('capacity must contain nonnegative integer L1 and UB bytes')
    try:
        index = DAGIndex(graph)
        view = derive_multicore_plan(graph, plan)
    except Exception as error:
        raise UnsupportedStructure('official graph/plan structural validation failed') from error
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise UnsupportedStructure('requires singleton subgraphs')
    tensors = {t['id']: t for t in graph['tensors']}
    if any('logical_tid' in t for t in tensors.values()):
        raise UnsupportedStructure('logical_tid aliases are outside guard')
    eligible = set(index.ops)
    producers, consumers, direct_edges = _original_tensor_views(graph)
    owner = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
    if set(owner) != eligible:
        raise UnsupportedStructure('plan does not cover eligible operations')
    inverse = {sg: u for u, sg in view['mapping'].items()}
    rows = [[inverse[sg] for sg in row] for row in plan['core_schedules']]
    if len(rows) != view['num_cores']:
        raise UnsupportedStructure('core count differs from validated plan')
    position = {u: i for row in rows for i, u in enumerate(row)}
    modeled_pairs = set()
    intervals = [[] for _ in rows]
    tensor_counts = [0 for _ in rows]
    direct_counts = [0 for _ in rows]
    for tid, tensor in tensors.items():
        size = tensor['size']
        pos = 'UB' if tensor['pos'] == 'DDR' else tensor['pos']
        if type(size) is not int or size < 0 or pos not in ('L1', 'UB'):
            raise UnsupportedStructure('tensor size/position outside guard')
        sources = producers[tid] & eligible
        targets = consumers[tid] & eligible
        if len(sources) > 1:
            raise UnsupportedStructure('multiple eligible producers of a physical tensor')
        for u in sources:
            for v in targets:
                if u != v:
                    modeled_pairs.add((u, v))
        by_core = defaultdict(list)
        for u in sources | targets:
            by_core[owner[u]].append(position[u])
        for core, touches in by_core.items():
            intervals[core].append((pos, min(touches), max(touches), size))
            tensor_counts[core] += 1
    for edge in direct_edges:
        u, v = edge['source'], edge['target']
        if u not in eligible or v not in eligible:
            continue
        modeled_pairs.add((u, v))
        size = edge.get('data_size', 0)
        if type(size) is not int or size < 0:
            raise UnsupportedStructure('direct edge size outside guard')
        if owner[u] != owner[v]:
            for endpoint in (u, v):
                core = owner[endpoint]
                intervals[core].append(('UB', position[endpoint], position[endpoint], size))
                direct_counts[core] += 1
    contracted = {(u, v) for u in eligible for v in index.succ[u]}
    if modeled_pairs != contracted:
        raise UnsupportedStructure('contracted-only COPY path or unrepresented eligible dependency')
    for u, v in modeled_pairs:
        if owner[u] == owner[v] and position[u] >= position[v]:
            raise UnsupportedStructure('same-core priority is not local topological order')

    details = []
    for core, row in enumerate(rows):
        change = {'L1': [0] * (len(row) + 1), 'UB': [0] * (len(row) + 1)}
        for pool, first, last, size in intervals[core]:
            change[pool][first] += size
            change[pool][last + 1] -= size
        live = {'L1': 0, 'UB': 0}
        peak = {'L1': 0, 'UB': 0}
        peak_at = {'L1': None, 'UB': None}
        for step in range(len(row)):
            for pool in ('L1', 'UB'):
                live[pool] += change[pool][step]
                if live[pool] > peak[pool]:
                    peak[pool], peak_at[pool] = live[pool], row[step]
        details.append({'core': core, 'eligible_operations': len(row),
                        'tensor_intervals': tensor_counts[core],
                        'cross_direct_point_intervals': direct_counts[core],
                        'peak_bytes': peak, 'peak_at_original_op': peak_at,
                        'fits_capacity': all(peak[p] <= capacity[p] for p in ('L1', 'UB'))})
    supported_peaks = [d['peak_bytes'] for d in details]
    return {'supported': True, 'reason': None, 'peaks': supported_peaks,
            'per_core': details,
            'zero_spill_certificate': all(d['fits_capacity'] for d in details),
            'capacity_bytes': dict(capacity),
            'scope': ('Exact Step2 no-spill test under guarded singleton P2 pre-Step2 task rules; '
                      'not a Step3, shared-DDR, or Makespan guarantee.')}
