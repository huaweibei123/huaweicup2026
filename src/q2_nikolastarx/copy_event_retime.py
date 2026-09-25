"""Optional fixed-owner priority retiming with static MTE copy events.

The pre-Step2 boundary/cross rules follow frozen P2 task construction
(`multicore_cut_evaluate_problem_2.py`, _build_scene_b_tasks, lines 61-238).
Only the frozen _original_tensor_views is imported: the P2 builder itself also
runs Step2/Step3 and therefore cannot serve as a lightweight event extractor.
This approximation has per-core MTE2/MTE3 calendars and COPY_OUT-end + delay
release, but no shared DDR queue, Step2 spill, memory, or official scheduling.
Its times and result have NO official Makespan guarantee.
"""
from __future__ import annotations

from collections import defaultdict
import heapq
import math

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .gap_calendar import empty, earliest, reserve

# Import direct first, so it installs the frozen official code path.
from multicore_cut_evaluate_problem_1 import _original_tensor_views


def retime(graph: dict, plan: dict, config: dict) -> tuple[dict, dict]:
    """Build one static event witness, returning only same-owner singleton ops."""
    bandwidth = config['bandwidth']
    delay = config['cross_core_copy_delay_cycles']
    if (type(bandwidth) not in (int, float) or not math.isfinite(bandwidth)
            or bandwidth <= 0 or type(delay) is not int or delay < 0):
        raise ValueError('finite positive bandwidth and nonnegative integer delay required')
    index = DAGIndex(graph)
    view = derive_multicore_plan(graph, plan)
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise UnsupportedStructure('copy-event retime requires singleton subgraphs')
    if any('logical_tid' in tensor for tensor in graph['tensors']):
        raise UnsupportedStructure('logical_tid aliases are outside copy-event guard')
    mapping = view['mapping']
    owner = {u: view['core_by_subgraph'][sg] for u, sg in mapping.items()}
    if set(owner) != set(index.ops):
        raise UnsupportedStructure('eligible operation coverage differs from plan')
    producers, consumers, direct_edges = _original_tensor_views(graph)
    tensors = {t['id']: t for t in graph['tensors']}
    originals = {o['id']: o for o in graph['ops']}
    eligible = set(index.ops)
    for tid, tensor in tensors.items():
        if type(tensor['size']) is not int or tensor['size'] < 0:
            raise UnsupportedStructure('tensor size must be nonnegative integer')
        if len(producers[tid] & eligible) > 1:
            raise UnsupportedStructure('multiple eligible producers of a physical tensor')

    def copy_duration(size: int) -> int:
        if type(size) is not int or size < 0:
            raise UnsupportedStructure('COPY size must be nonnegative integer')
        return max(1, math.ceil(size / bandwidth))

    pipes = {o['pipe'] for o in index.ops.values()} | {'PIPE_MTE2', 'PIPE_MTE3'}
    events = {u: (owner[u], index.ops[u]['pipe'], index.duration(u), 'eligible')
              for u in index.ops}
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    modeled_pairs = set()
    next_id = max(set(originals) | set(tensors) | {0}) + 1
    counts = defaultdict(int)
    cross_links = []

    def event(core: int, kind: str, size: int) -> int:
        nonlocal next_id
        eid = next_id
        next_id += 1
        events[eid] = (core, 'PIPE_MTE2' if kind == 'in' else 'PIPE_MTE3',
                       copy_duration(size), kind)
        counts[kind] += 1
        return eid

    def edge(u: int, v: int, lag: int = 0) -> None:
        if u == v:
            raise UnsupportedStructure('self dependency in copy-event graph')
        outgoing[u].append((v, lag))
        incoming[v].append((u, lag))

    for tid in sorted(tensors):
        tensor = tensors[tid]
        size = tensor['size']
        source_ops = sorted(producers[tid] & eligible)
        target_ops = sorted(consumers[tid] & eligible)
        if not source_ops and not target_ops:
            continue
        source_cores = sorted({owner[u] for u in source_ops})
        target_cores = sorted({owner[u] for u in target_ops})
        if not source_ops:
            # Frozen P2: one boundary COPY_IN per consuming core.
            for core in target_cores:
                ci = event(core, 'in', size)
                counts['boundary_in'] += 1
                for v in target_ops:
                    if owner[v] == core:
                        edge(ci, v)
        if source_ops and (not target_ops or any(
                originals[u]['op'] == 'COPY_OUT' for u in consumers[tid])):
            # Frozen P2: one boundary COPY_OUT per producing core.
            for core in source_cores:
                co = event(core, 'out', size)
                counts['boundary_out'] += 1
                for u in source_ops:
                    if owner[u] == core:
                        edge(u, co)
        for u in source_ops:
            for v in target_ops:
                if u != v:
                    modeled_pairs.add((u, v))
                    if owner[u] == owner[v]:
                        edge(u, v)
        for source_core in source_cores:
            for target_core in target_cores:
                if source_core == target_core:
                    continue
                # Frozen P2: one pair per physical tensor and core pair,
                # shared by every consumer on that target core.
                co = event(source_core, 'out', size)
                ci = event(target_core, 'in', size)
                counts['cross_tensor_pairs'] += 1
                cross_links.append((co, ci, tuple(v for v in target_ops
                                                  if owner[v] == target_core)))
                for u in source_ops:
                    if owner[u] == source_core:
                        edge(u, co)
                edge(co, ci, delay)
                for v in target_ops:
                    if owner[v] == target_core:
                        edge(ci, v)

    for record in direct_edges:
        u, v = record['source'], record['target']
        if u not in index.ops or v not in index.ops:
            continue
        modeled_pairs.add((u, v))
        if owner[u] == owner[v]:
            edge(u, v)
        else:
            size = record.get('data_size', 0)
            co = event(owner[u], 'out', size)
            ci = event(owner[v], 'in', size)
            counts['cross_direct_pairs'] += 1
            cross_links.append((co, ci, (v,)))
            edge(u, co)
            edge(co, ci, delay)
            edge(ci, v)

    contracted = {(u, v) for u in index.ops for v in index.succ[u]}
    if modeled_pairs != contracted:
        raise UnsupportedStructure('excluded COPY paths or other contracted edges are not represented')

    degree = {u: len(incoming[u]) for u in events}
    ready = [u for u in events if degree[u] == 0]
    heapq.heapify(ready)
    topo = []
    while ready:
        u = heapq.heappop(ready)
        topo.append(u)
        for v, _ in outgoing[u]:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    if len(topo) != len(events):
        raise UnsupportedStructure('copy-event graph has a cycle')
    tail = {}
    for u in reversed(topo):
        tail[u] = events[u][2] + max((lag + tail[v] for v, lag in outgoing[u]), default=0)

    degree = {u: len(incoming[u]) for u in events}
    ready = [(-tail[u], u) for u in events if degree[u] == 0]
    heapq.heapify(ready)
    calendars = [{p: empty() for p in pipes} for _ in plan['core_schedules']]
    starts, ends = {}, {}
    while ready:
        _, u = heapq.heappop(ready)
        core, pipe, duration, _ = events[u]
        release = max((ends[v] + lag for v, lag in incoming[u]), default=0)
        begin = earliest(calendars[core][pipe], release, duration)
        calendars[core][pipe] = reserve(calendars[core][pipe], begin, duration)
        starts[u], ends[u] = begin, begin + duration
        for v, _ in outgoing[u]:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, (-tail[v], v))
    if len(ends) != len(events):
        raise AssertionError('event scheduling did not cover every event')

    result_rows = [[] for _ in plan['core_schedules']]
    for u in index.ops:
        result_rows[owner[u]].append(u)
    result = {'node_to_subgraph': dict(plan['node_to_subgraph']),
              'core_schedules': [
                  [mapping[u] for u in sorted(row, key=lambda u: (starts[u], mapping[u]))]
                  for row in result_rows]}
    try:
        checked = derive_multicore_plan(graph, result)
    except Exception as exc:
        raise UnsupportedStructure('copy-event priority failed final structural validation') from exc
    if {u: checked['core_by_subgraph'][sg] for u, sg in checked['mapping'].items()} != owner:
        raise AssertionError('fixed eligible owner changed')
    return result, {
        'selected_strategy': 'copy_event_retime',
        'static_event_finish_cycles': max(ends.values(), default=0),
        'eligible_operations': len(index.ops), 'events': len(events),
        'copy_counts': dict(counts), 'cross_link_count': len(cross_links),
        'cross_link_release_checks': all(starts[ci] >= ends[co] + delay
                                         for co, ci, _ in cross_links),
        'static_event_starts': {str(u): starts[u] for u in events},
        'static_event_ends': {str(u): ends[u] for u in events},
        'static_event_resources': {str(u): {'core': events[u][0], 'pipe': events[u][1],
                                            'kind': events[u][3]} for u in events},
        'cross_links': [[co, ci, list(targets)] for co, ci, targets in cross_links],
        'scope': 'Static per-core Pipe events only; no shared DDR, Step2 spill, memory, or official Makespan guarantee.',
    }


build = retime
