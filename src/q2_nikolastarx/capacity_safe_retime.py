"""Fixed-owner adjacent retime preserving a guarded singleton zero-spill seed.

This is an order repair toward a target, not a Makespan estimator or optimizer.
No official task builder, Step2, E0, or E2 is called.
"""
from __future__ import annotations

from collections import defaultdict

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .zero_spill_intervals import certify, _original_tensor_views


def retime(graph: dict, seed: dict, target: dict, config: dict) -> tuple[dict, dict]:
    """Try at most two sweeps of adjacent target-inversion swaps.

    Raises UnsupportedStructure on a guard failure; input plans are untouched.
    The returned plan has the seed mapping and owner, and a zero-spill priority.
    """
    first = certify(graph, seed, config)
    if not first['supported'] or not first['zero_spill_certificate']:
        raise UnsupportedStructure('seed needs a supported zero-spill certificate')
    desired = certify(graph, target, config)
    if not desired['supported']:
        raise UnsupportedStructure('target is outside the certificate domain')
    seed_view = derive_multicore_plan(graph, seed)
    target_view = derive_multicore_plan(graph, target)
    if seed_view['mapping'] != target_view['mapping']:
        raise UnsupportedStructure('mapping must be identical')
    if seed_view['core_by_subgraph'] != target_view['core_by_subgraph']:
        raise UnsupportedStructure('owner must be identical')

    index = DAGIndex(graph)
    eligible = set(index.ops)
    mapping = seed_view['mapping']
    inverse = {sg: op for op, sg in mapping.items()}
    rows = [[inverse[sg] for sg in row] for row in seed['core_schedules']]
    wanted = [[inverse[sg] for sg in row] for row in target['core_schedules']]
    rank = [{op: i for i, op in enumerate(row)} for row in wanted]
    owner = {op: core for core, row in enumerate(rows) for op in row}
    positions = [{op: i for i, op in enumerate(row)} for row in rows]
    capacity = config['capacity']
    producers, consumers, directs = _original_tensor_views(graph)
    tensor_info = {t['id']: (('UB' if t['pos'] == 'DDR' else t['pos']), t['size'])
                   for t in graph['tensors']}
    touches = [defaultdict(set) for _ in rows]
    by_op = [defaultdict(set) for _ in rows]
    for tid in tensor_info:
        for op in (producers[tid] | consumers[tid]) & eligible:
            core = owner[op]
            touches[core][tid].add(positions[core][op])
            by_op[core][op].add(tid)
    direct_bytes = [defaultdict(int) for _ in rows]
    for edge in directs:
        u, v = edge['source'], edge['target']
        if u in owner and v in owner and owner[u] != owner[v]:
            direct_bytes[owner[u]][u] += edge.get('data_size', 0)
            direct_bytes[owner[v]][v] += edge.get('data_size', 0)
    live = []
    for core, row in enumerate(rows):
        delta = {'L1': [0] * (len(row) + 1), 'UB': [0] * (len(row) + 1)}
        for tid, points in touches[core].items():
            pool, size = tensor_info[tid]
            delta[pool][min(points)] += size
            delta[pool][max(points) + 1] -= size
        for op, size in direct_bytes[core].items():
            i = positions[core][op]
            delta['UB'][i] += size
            delta['UB'][i + 1] -= size
        state = {'L1': [], 'UB': []}
        for pool in state:
            current = 0
            for amount in delta[pool][:-1]:
                current += amount
                state[pool].append(current)
        live.append(state)

    attempts = accepted = dependency_rejections = capacity_rejections = 0

    def try_swap(core: int, i: int) -> None:
        nonlocal attempts, accepted, dependency_rejections, capacity_rejections
        row = rows[core]
        u, v = row[i], row[i + 1]
        if rank[core][u] <= rank[core][v]:
            return
        attempts += 1
        if v in index.succ[u] or u in index.succ[v]:
            dependency_rejections += 1
            return
        new = {pool: [live[core][pool][i], live[core][pool][i + 1]]
               for pool in ('L1', 'UB')}
        for tid in by_op[core][u] ^ by_op[core][v]:
            pool, size = tensor_info[tid]
            points = touches[core][tid]
            old_first, old_last = min(points), max(points)
            origin = i if tid in by_op[core][u] else i + 1
            moved = i + 1 if origin == i else i
            changed = (points - {origin}) | {moved}
            new_first, new_last = min(changed), max(changed)
            for offset in (0, 1):
                j = i + offset
                new[pool][offset] += size * (
                    int(new_first <= j <= new_last) - int(old_first <= j <= old_last))
        du, dv = direct_bytes[core][u], direct_bytes[core][v]
        new['UB'][0] += dv - du
        new['UB'][1] += du - dv
        if any(new[pool][offset] > capacity[pool]
               for pool in ('L1', 'UB') for offset in (0, 1)):
            capacity_rejections += 1
            return
        for tid in by_op[core][u] ^ by_op[core][v]:
            origin = i if tid in by_op[core][u] else i + 1
            points = touches[core][tid]
            points.remove(origin)
            points.add(i + 1 if origin == i else i)
        for pool in ('L1', 'UB'):
            live[core][pool][i:i + 2] = new[pool]
        row[i], row[i + 1] = v, u
        positions[core][u], positions[core][v] = i + 1, i
        accepted += 1

    for core, row in enumerate(rows):
        for i in range(len(row) - 1):
            try_swap(core, i)
        for i in range(len(row) - 2, -1, -1):
            try_swap(core, i)
    result = {'node_to_subgraph': dict(seed['node_to_subgraph']),
              'core_schedules': [[mapping[op] for op in row] for row in rows]}
    return result, {'attempts': attempts, 'accepted': accepted,
                    'dependency_rejections': dependency_rejections,
                    'capacity_rejections': capacity_rejections,
                    'target_reached': result['core_schedules'] == target['core_schedules'],
                    'zero_spill_invariant': True,
                    'model_limit': 'guarded pre-Step2 zero spill only; no Makespan claim'}
