"""Candidate-conditioned P2 bounds in an exact service model.

This is not a global optimum bound and not a floating-point E0 certificate.
The fixed candidate must be valid and execute successfully; evaluating these
necessary bounds does not establish either execution success or no spill.
No construction, task compilation, Step2, Step3, or evaluator is called.
"""
from __future__ import annotations

from collections import defaultdict, deque

from .component_gate import service_profile
from .construct import PIPES, UnsupportedStructure


def _longest_path(nodes, successors, duration):
    degree = dict.fromkeys(nodes, 0)
    for edges in successors.values():
        for edge in edges:
            degree[edge['target']] += 1
    ready = deque(u for u in nodes if not degree[u])
    release = dict.fromkeys(nodes, 0)
    finish, predecessor = {}, {}
    while ready:
        u = ready.popleft()
        finish[u] = release[u] + duration[u]
        for edge in successors[u]:
            v = edge['target']
            earliest = finish[u] + edge['lag_cycles']
            # Parallel incoming edges constrain the maximum release, not a sum.
            if earliest > release[v]:
                release[v] = earliest
                predecessor[v] = edge
            degree[v] -= 1
            if degree[v] == 0:
                ready.append(v)
    if len(finish) != len(nodes):
        raise UnsupportedStructure('necessary physical/FIFO dependencies contain a cycle')
    last = max(nodes, key=lambda u: finish[u], default=None)
    path_ops, path_edges = [], []
    cursor = last
    while cursor is not None:
        path_ops.append(cursor)
        edge = predecessor.get(cursor)
        if edge is None:
            break
        path_edges.append(edge)
        cursor = edge['source']
    return {'cycles': finish[last] if last is not None else 0,
            'ops': list(reversed(path_ops)), 'edges': list(reversed(path_edges))}


def candidate_lower_bound(index, plan, bandwidth, delay):
    """Return max(DDR work, per-core/Pipe work, physical plus FIFO path).

    Only original eligible-to-eligible direct edges and real tensor producer/
    consumer pairs are used. Reachability contracted through excluded original
    COPY nodes and whole core_schedules order are deliberately not path edges.
    The singleton core order is projected separately onto each Pipe; adjacent
    eligible ops on that Pipe have a zero-lag FIFO edge. The augmented graph
    gets its own topological/cycle check, since its order can differ from the
    input graph order. A detected necessary-dependency cycle rejects the bound.
    """
    if type(delay) is not int or not 0 <= delay <= 2**31:
        raise UnsupportedStructure('ideal bound requires 0..2^31 integer delay')
    profile = service_profile(index, plan, bandwidth)
    # service_profile already validates this exact plan through the official
    # derive_multicore_plan. Rebuild only its small ownership maps here.
    mapping = {int(u): sg for u, sg in plan['node_to_subgraph'].items()}
    core_by_subgraph = {sg: c for c, order in enumerate(plan['core_schedules']) for sg in order}
    core_of = {u: core_by_subgraph[sg] for u, sg in mapping.items()}
    loads = [dict.fromkeys(PIPES, 0) for _ in plan['core_schedules']]
    duration = {u: max(1, op.get('cycles', 1)) for u, op in index.ops.items()}
    for u, op in index.ops.items():
        loads[core_of[u]][op['pipe']] += duration[u]
    successors = defaultdict(list)
    physical_pairs = set()
    position = {u: i for i, u in enumerate(index.order)}
    arc_count = 0

    def add(src, dst, size, kind, identity):
        nonlocal arc_count
        if position[src] >= position[dst]:
            raise UnsupportedStructure('physical dependency is not in DAG order')
        cross = core_of[src] != core_of[dst]
        lag = 2 * max(1, (size + bandwidth - 1) // bandwidth) + delay if cross else 0
        successors[src].append({'source': src, 'target': dst, 'kind': kind,
                                'identity': identity, 'cross_core': cross,
                                'lag_cycles': lag})
        physical_pairs.add((src, dst))
        arc_count += 1

    for tid in sorted(index.tensors):
        producer = index.producer.get(tid)
        if producer is not None:
            for consumer in sorted(index.consumers[tid]):
                add(producer, consumer, index.tensors[tid]['size'], 'tensor', tid)
    for edge_id, edge in enumerate(index.graph['edges']):
        src, dst = edge['source'], edge['target']
        if src in core_of and dst in core_of:
            add(src, dst, max(0, int(edge.get('data_size', 0))), 'direct', edge_id)

    physical_path = _longest_path(index.order, successors, duration)
    node_of = {sg: u for u, sg in mapping.items()}
    fifo_count = 0
    for core, order in enumerate(plan['core_schedules']):
        previous = {}
        for sg in order:
            u = node_of[sg]
            pipe = index.ops[u]['pipe']
            if pipe in previous:
                successors[previous[pipe]].append({
                    'source': previous[pipe], 'target': u, 'kind': 'pipe_fifo',
                    'identity': [core, pipe], 'cross_core': False, 'lag_cycles': 0})
                fifo_count += 1
            previous[pipe] = u
    fifo_path = _longest_path(index.order, successors, duration)
    pipe = max((value for core in loads for value in core.values()), default=0)
    ddr = profile['base_copy_service_cycles']
    return {
        'scope': 'fixed-candidate ideal-model necessary bound; not global optimum or machine certificate',
        'requires_successful_execution': True,
        'ddr_service_cycles': ddr, 'per_core_pipe_work_cycles': pipe,
        'physical_path_cycles': physical_path['cycles'],
        'physical_only_lower_bound_cycles': max(ddr, pipe, physical_path['cycles']),
        'fifo_path_cycles': fifo_path['cycles'],
        'ideal_lower_bound_cycles': max(ddr, pipe, fifo_path['cycles']),
        'core_pipe_work': loads, 'physical_arc_count': arc_count,
        'fifo_arc_count': fifo_count,
        # Endpoint-pair difference, not a count of excluded original COPY paths:
        # a contracted path may share endpoints with a retained direct edge.
        'contracted_pairs_without_physical_arc': sum(
            (u, v) not in physical_pairs for u in index.order for v in index.succ[u]),
        'critical_path_ops': fifo_path['ops'], 'critical_path_edges': fifo_path['edges'],
        'base_copy_count': profile['base_copy_count'],
        'base_copy_bytes': profile['base_copy_bytes'],
        'max_core_compute_work_cycles': profile['max_core_compute_work_cycles'],
        'whole_components': profile['whole_components'],
        'cross_core_links': profile['cross_core_links'],
        'online_E0_calls': 0,
    }
