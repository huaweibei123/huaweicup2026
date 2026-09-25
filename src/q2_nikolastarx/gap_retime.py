"""Retime a fixed singleton placement with a deterministic Pipe gap calendar.

This preserves every eligible operation's core. Static isolated COPY lag is
modeled, but contention, capacity, spill, and official Makespan are not.
"""
from __future__ import annotations

import heapq

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .gap_calendar import empty, earliest, reserve
from .gap_candidate import _chain_dag


def retime(graph, plan, config):
    """Return a new singleton schedule and static start-time witness."""
    index = DAGIndex(graph)
    chains, pred, succ, delay, order = _chain_dag(
        index, config['bandwidth'], config['cross_core_copy_delay_cycles'])
    try:
        view = derive_multicore_plan(graph, plan)
    except Exception as error:
        raise UnsupportedStructure('input plan failed structural validation') from error
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise UnsupportedStructure('requires singleton subgraphs')
    owner = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
    chain_core = {}
    for j, chain in enumerate(chains):
        cores = {owner[u] for u in chain}
        if len(cores) != 1:
            raise UnsupportedStructure('each maximal chain must remain on one core')
        chain_core[j] = next(iter(cores))
    rank = {}
    for j in reversed(order):
        rank[j] = sum(index.duration(u) for u in chains[j]) + max(
            (rank[v] for v in succ[j]), default=0)
    degree = [len(row) for row in pred]
    ready = [(-rank[j], min(chains[j]), j) for j in order if degree[j] == 0]
    heapq.heapify(ready)
    pipes = sorted({op['pipe'] for op in index.ops.values()})
    calendars = [{p: empty() for p in pipes} for _ in plan['core_schedules']]
    starts, finish, dispatched = {}, {}, []
    while ready:
        _, _, j = heapq.heappop(ready)
        core = chain_core[j]
        at = max((finish[p] + (delay[p, j] if chain_core[p] != core else 0)
                  for p in pred[j]), default=0)
        for u in chains[j]:
            pipe, duration = index.ops[u]['pipe'], index.duration(u)
            start = earliest(calendars[core][pipe], at, duration)
            calendars[core][pipe] = reserve(calendars[core][pipe], start, duration)
            starts[u] = start
            at = start + duration
        finish[j] = at
        dispatched.append(j)
        for v in sorted(succ[j]):
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, (-rank[v], min(chains[v]), v))
    if len(dispatched) != len(chains):
        raise UnsupportedStructure('incomplete chain retiming')
    key_by_op = {int(key): key for key in plan['node_to_subgraph']}
    mapping = plan['node_to_subgraph']
    rows = [[] for _ in plan['core_schedules']]
    for u in index.ops:
        rows[owner[u]].append(u)
    output = {'node_to_subgraph': dict(mapping), 'core_schedules': [
        [mapping[key_by_op[u]] for u in sorted(row, key=lambda u: (starts[u], mapping[key_by_op[u]]))]
        for row in rows]}
    derive_multicore_plan(graph, output)
    return output, {'static_finish_cycles': max(finish.values(), default=0),
                    'op_starts': {str(u): starts[u] for u in sorted(starts)},
                    'chain_count': len(chains), 'dispatch_order': dispatched,
                    'scope': 'Fixed-core static Pipe calendar only; no official Makespan or spill guarantee'}


def build(graph, plan, config):
    """Alias for callers using constructor-style names."""
    return retime(graph, plan, config)
