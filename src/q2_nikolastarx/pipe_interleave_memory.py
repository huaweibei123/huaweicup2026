"""Greedy cross-Pipe priority interleaving with fixed owners and Pipe FIFO.

With V ops, E dependencies, I tensor incidences and R ready Pipe heads,
work is O(V*R + E + I) plus two certificates, space O(V+E+I);
R <= cores*distinct_Pipes. Each tensor's remaining pins are scanned at most
once when opened. The closed-touch peak is pre-Step2 only.
"""
from __future__ import annotations

from collections import defaultdict

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .zero_spill_intervals import certify, _original_tensor_views


def retime(graph: dict, plan: dict, config: dict) -> tuple[dict, dict]:
    initial = certify(graph, plan, config)
    if not initial['supported']:
        raise UnsupportedStructure('closed-touch domain rejected input: ' + initial['reason'])
    index = DAGIndex(graph)
    view = derive_multicore_plan(graph, plan)
    mapping = view['mapping']
    inverse = {sg: u for u, sg in mapping.items()}
    rows = [[inverse[sg] for sg in row] for row in plan['core_schedules']]
    owner = {u: c for c, row in enumerate(rows) for u in row}
    rank = {u: i for i, u in enumerate(index.order)}
    succ = {u: set(index.succ[u]) for u in index.ops}
    for row in rows:
        pipe_last = {}
        for u in row:
            pipe = index.ops[u]['pipe']
            if pipe in pipe_last:
                succ[pipe_last[pipe]].add(u)
            pipe_last[pipe] = u
    degree = dict.fromkeys(index.ops, 0)
    for next_ops in succ.values():
        for v in next_ops:
            degree[v] += 1

    _, _, directs = _original_tensor_views(graph)
    tensor = {t['id']: t for t in graph['tensors']}
    touches = {u: set(index.inputs[u]) | set(index.outputs[u]) for u in index.ops}
    remaining = [defaultdict(set) for _ in rows]
    opening = {u: {'L1': 0, 'UB': 0} for u in index.ops}
    freeing = {u: {'L1': 0, 'UB': 0} for u in index.ops}

    def pool(tid):
        return 'UB' if tensor[tid]['pos'] == 'DDR' else tensor[tid]['pos']

    for u, ids in touches.items():
        for tid in ids:
            remaining[owner[u]][tid].add(u)
            opening[u][pool(tid)] += tensor[tid]['size']
    for core_tensors in remaining:
        for tid, pins in core_tensors.items():
            if len(pins) == 1:
                freeing[next(iter(pins))][pool(tid)] += tensor[tid]['size']
    direct_bytes = defaultdict(int)
    for edge in directs:
        u, v = edge['source'], edge['target']
        if u in owner and v in owner and owner[u] != owner[v]:
            direct_bytes[u] += edge.get('data_size', 0)
            direct_bytes[v] += edge.get('data_size', 0)

    capacity = config['capacity']
    resident = [set() for _ in rows]
    used = [{p: 0 for p in ('L1', 'UB')} for _ in rows]
    peak = [{p: 0 for p in ('L1', 'UB')} for _ in rows]
    ready = {u for u, d in degree.items() if d == 0}
    global_order = []
    output = [[] for _ in rows]

    def evaluate(u):
        c = owner[u]
        at = {p: used[c][p] + opening[u][p] +
              (direct_bytes[u] if p == 'UB' else 0) for p in ('L1', 'UB')}
        excess = sum(max(0, at[p] - capacity[p]) for p in ('L1', 'UB'))
        net_release = sum(freeing[u].values()) - sum(opening[u].values())
        return (excess, -net_release, rank[u], u), at

    while ready:
        # Evaluate each currently ready op; ready set is bounded by the number
        # of Pipe heads after adding fixed Pipe FIFO arcs.
        scored = [(score, u, at) for u in ready for score, at in [evaluate(u)]]
        _, u, at = min(scored)
        ready.remove(u)
        c = owner[u]
        for p in ('L1', 'UB'):
            peak[c][p] = max(peak[c][p], at[p])
        for tid in touches[u]:
            p, size = pool(tid), tensor[tid]['size']
            pins = remaining[c][tid]
            if tid not in resident[c]:
                for later in pins:
                    if later != u:
                        opening[later][p] -= size
                resident[c].add(tid)
                used[c][p] += size
            pins.remove(u)
            if len(pins) == 1:
                freeing[next(iter(pins))][p] += size
            if not pins:
                resident[c].remove(tid)
                used[c][p] -= size
        global_order.append(u)
        output[c].append(mapping[u])
        for v in succ[u]:
            degree[v] -= 1
            if degree[v] == 0:
                ready.add(v)
    if len(global_order) != len(index.ops):
        raise UnsupportedStructure('compute dependencies plus fixed Pipe FIFO contain a cycle')
    result = {'node_to_subgraph': dict(plan['node_to_subgraph']),
              'core_schedules': output}
    derive_multicore_plan(graph, result)
    checked = certify(graph, result, config)
    if not checked['supported'] or checked['peaks'] != peak:
        raise AssertionError('incremental closed-touch peak disagrees with certificate')
    return result, {'selected_strategy': 'pipe_interleave_memory',
                    'original_peaks': initial['peaks'], 'new_peaks': peak,
                    'zero_spill_diagnostic': checked,
                    'global_topological_order': global_order,
                    'official_score_available': False,
                    'limitations': ['fixed owners and Pipe FIFO only',
                                    'no Step3/DDR/Makespan guarantee']}
