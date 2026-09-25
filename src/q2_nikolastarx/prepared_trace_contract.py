"""Capture prepared P2 constraints and audit one already-produced official trace.

This is a retrospective equality check, not an evaluator or counterfactual bound.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math

from . import direct as _official_path  # Installs this repository's frozen official code path.
from schedule_step3 import op_pipe


def _integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(label + ' must be a nonnegative integer')
    return value


def _ids(values, label):
    rows = list(values)
    if any(type(v) is not int for v in rows) or len(rows) != len(set(rows)):
        raise ValueError(label + ' has missing, duplicate, or noninteger IDs')
    return rows


def _graph_preds(graph, op_ids):
    tensors = _ids((t['id'] for t in graph['tensors']), 'tensor')
    tensor_by_id = {t['id']: t for t in graph['tensors']}
    if set(op_ids) & set(tensors):
        raise ValueError('op and tensor IDs overlap')
    known = set(op_ids) | set(tensors)
    producers, consumers = defaultdict(set), defaultdict(set)
    preds = {u: set() for u in op_ids}
    incoming = {u: [] for u in op_ids}
    outgoing = {u: [] for u in op_ids}
    for edge in graph['edges']:
        src, dst = edge['source'], edge['target']
        if src not in known or dst not in known:
            raise ValueError('execution graph edge has unknown endpoint')
        if src in preds and dst in preds and src != dst:
            preds[dst].add(src)
        elif src in preds and dst in tensors:
            producers[dst].add(src)
            outgoing[src].append(dst)
        elif src in tensors and dst in preds:
            consumers[src].add(dst)
            incoming[dst].append(src)
    for tid in tensors:
        for target in consumers[tid]:
            preds[target].update(u for u in producers[tid] if u != target)
    return preds, incoming, outgoing, tensor_by_id


def capture(tasks, cross_links):
    """Return a pure-JSON snapshot from complete official prepared task objects."""
    if not isinstance(tasks, dict) or not tasks:
        raise ValueError('complete nonempty task mapping required')
    if set(tasks) != set(range(len(tasks))):
        raise ValueError('prepared core IDs must be contiguous from zero')
    operations, links, prepared_by_core = [], [], []
    known = set()
    for core, task in sorted(tasks.items()):
        _integer(core, 'core')
        if task.get('core_id') != core:
            raise ValueError('task/core identity mismatch')
        graph = task['step3']['execution_graph']
        op_ids = _ids((op['id'] for op in graph['ops']), 'operation')
        op_by_id = {op['id']: op for op in graph['ops']}
        if set(task['op_by_id']) != set(op_ids) or any(task['op_by_id'][u] != op_by_id[u] for u in op_ids):
            raise ValueError('prepared op_by_id differs from execution graph')
        if set(_ids(task['seq'], 'seq')) != set(op_ids):
            raise ValueError('prepared seq omits operations')
        expected, incoming, outgoing, tensor_by_id = _graph_preds(graph, op_ids)
        if set(task['op_preds']) != set(op_ids):
            raise ValueError('prepared predecessor map incomplete')
        for u in op_ids:
            if set(task['op_preds'][u]) != expected[u]:
                raise ValueError('execution graph and prepared predecessors disagree')
        memory = task['step3']['memory_dependencies']
        for dep in memory:
            if set(dep) != {'source', 'target', 'kind', 'positions', 'reused_bytes',
                            'previous_tensor_ids'}:
                raise ValueError('incomplete Step3 memory dependency metadata')
            if dep['source'] not in expected.get(dep['target'], ()):
                raise ValueError('Step3 memory dependency missing from execution graph')
        tagged = {(e['source'], e['target']) for e in graph['edges']
                  if e.get('dependency') == 'MEMORY_REUSE'}
        if not tagged <= {(d['source'], d['target']) for d in memory}:
            raise ValueError('tagged execution memory edge missing from Step3 metadata')
        pipe_prev = {}
        covered = []
        for pipe, order in task['pipe_ops'].items():
            previous = None
            for u in _ids(order, 'pipe order'):
                if u not in op_by_id or op_pipe(op_by_id[u]) != pipe:
                    raise ValueError('Pipe order and op pipe disagree')
                pipe_prev[u] = previous
                previous = u
                covered.append(u)
        if len(covered) != len(op_ids) or set(covered) != set(op_ids):
            raise ValueError('Pipe orders must partition every prepared op exactly once')
        prepared_by_core.append({'core': core, 'memory_dependency_count': len(memory),
                                 'memory_dependencies': deepcopy(memory),
                                 'pipe_op_counts': {pipe: len(order) for pipe, order in task['pipe_ops'].items()}})
        for u in sorted(op_ids):
            op = op_by_id[u]
            if not isinstance(op.get('op'), str) or not isinstance(op_pipe(op), str):
                raise ValueError('operation kind and Pipe are required')
            cycles = _integer(op.get('cycles', 1), 'op cycles')
            adjacent = incoming[u] + outgoing[u]
            if any(type(tensor_by_id[t]['size']) is not int or tensor_by_id[t]['size'] < 0
                   for t in adjacent):
                raise ValueError('adjacent tensor size must be a nonnegative integer')
            copy_tids = (outgoing[u] if op['op'] == 'COPY_IN' else incoming[u]
                         if op['op'] == 'COPY_OUT' else [])
            copy_bytes = sum(tensor_by_id[t]['size'] for t in copy_tids)
            uses_ddr = (op['op'] in ('COPY_IN', 'COPY_OUT') and
                        any(tensor_by_id[t].get('pos') == 'DDR' for t in adjacent))
            operations.append({'core': core, 'id': u, 'kind': op['op'], 'pipe': op_pipe(op),
                               'is_compute': op['op'] not in ('COPY_IN', 'COPY_OUT'),
                               'cycles': cycles, 'copy_bytes': copy_bytes,
                               'has_copy_tensor': bool(copy_tids), 'uses_ddr': uses_ddr,
                               'local_preds': sorted(expected[u]), 'fifo_prev': pipe_prev[u]})
            known.add((core, u))
    for number, link in enumerate(cross_links):
        source = (_integer(link['source_core'], 'source core'),
                  _integer(link['source_copy_out_id'], 'source copy'))
        target = (_integer(link['target_core'], 'target core'),
                  _integer(link['target_copy_in_id'], 'target copy'))
        if source not in known or target not in known or source == target:
            raise ValueError('cross link has missing or self endpoint')
        op_lookup = {(o['core'], o['id']): o for o in operations}
        if op_lookup[source]['kind'] != 'COPY_OUT' or op_lookup[target]['kind'] != 'COPY_IN':
            raise ValueError('cross link must join COPY_OUT to COPY_IN')
        links.append({'index': number, 'source': list(source), 'target': list(target),
                      'tensor_id': link.get('tensor_id'), 'size': link.get('size')})
    return {'schema': 'prepared-trace-contract-v1', 'operations': operations,
            'prepared_by_core': prepared_by_core,
            'cross_links': links, 'scope': 'Complete prepared execution/FIFO/memory/cross DAG; retrospective only'}


def audit(contract, official_result):
    """Check every start gate; report tight ancestors only when all checks pass."""
    try:
        return _audit(contract, official_result)
    except (KeyError, TypeError, ValueError) as error:
        return {'consistent': False, 'residuals': [], 'critical_cross_links': [],
                'errors': [str(error)], 'scope': 'No critical-path claim from inconsistent evidence'}


def _audit(contract, result):
    if contract['schema'] != 'prepared-trace-contract-v1' or result['scene'] != 'B':
        raise ValueError('contract or scene mismatch')
    ops = {(o['core'], o['id']): o for o in contract['operations']}
    if len(ops) != len(contract['operations']):
        raise ValueError('duplicate prepared (core,id)')
    delay = _integer(result['cross_core_copy_delay_cycles'], 'cross delay')
    bandwidth = result['bandwidth_bytes_per_cycle']
    if type(bandwidth) not in (int, float) or not math.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError('official bandwidth must be finite and positive')
    prepared_cores = {row['core'] for row in contract['prepared_by_core']}
    if len(prepared_cores) != len(contract['prepared_by_core']):
        raise ValueError('duplicate prepared core')
    if result['num_cores'] != len(prepared_cores) or not {c for c, _ in ops} <= prepared_cores:
        raise ValueError('core count mismatch')
    official_prepared = result['step3_by_core']
    if len(official_prepared) != len(contract['prepared_by_core']):
        raise ValueError('official Step3 core coverage mismatch')
    for row in contract['prepared_by_core']:
        actual = official_prepared.get(row['core'], official_prepared.get(str(row['core'])))
        if (not isinstance(actual, dict)
                or actual.get('memory_dependency_count') != row['memory_dependency_count']
                or actual.get('pipe_op_counts') != row['pipe_op_counts']):
            raise ValueError('official Step3 memory/Pipe counts differ from snapshot')
    expected_links = [dict(source_core=l['source'][0], source_copy_out_id=l['source'][1],
                           target_core=l['target'][0], target_copy_in_id=l['target'][1],
                           tensor_id=l['tensor_id'], size=l['size']) for l in contract['cross_links']]
    if result['task_dependencies'] != expected_links:
        raise ValueError('official cross-link list differs from prepared snapshot')
    trace = {}
    seen_cores = set()
    for row in result['per_core_timeline']:
        core = row['core_id']
        if core in seen_cores:
            raise ValueError('duplicate core timeline')
        seen_cores.add(core)
        for item in row['ops']:
            key = (core, item['op_id'])
            if key in trace or key not in ops or item['task_id'] != core:
                raise ValueError('duplicate or unknown trace operation')
            op = ops[key]
            if item['op'] != op['kind'] or item['pipe'] != op['pipe']:
                raise ValueError('trace operation kind or Pipe mismatch')
            start, end, duration = (_integer(item[k], k) for k in ('start', 'end', 'duration'))
            if duration <= 0 or end - start != duration:
                raise ValueError('trace duration mismatch')
            base_duration = (max(1, math.ceil(op['copy_bytes'] / bandwidth))
                             if op['kind'] in ('COPY_IN', 'COPY_OUT') and op['has_copy_tensor']
                             else max(1, op['cycles']))
            if (duration < base_duration if op['uses_ddr'] else duration != base_duration):
                raise ValueError('trace duration differs from prepared operation work')
            trace[key] = (start, end)
    if set(trace) != set(ops):
        raise ValueError('trace omits prepared operations')
    if seen_cores != prepared_cores:
        raise ValueError('trace core coverage differs from prepared tasks')
    if result['makespan'] != max((end for _, end in trace.values()), default=0):
        raise ValueError('trace makespan mismatch')
    incoming = defaultdict(list)
    for link in contract['cross_links']:
        incoming[tuple(link['target'])].append(link)
    gates, residuals = {}, []
    for key, op in ops.items():
        core, _ = key
        local = [(core, u) for u in op['local_preds']]
        fifo = [(core, op['fifo_prev'])] if op['fifo_prev'] is not None else []
        cross = [(tuple(l['source']), delay, l['index']) for l in incoming[key]]
        candidates = [(p, 0, None) for p in local + fifo] + cross
        start = trace[key][0]
        maximum = max((trace[p][1] + lag for p, lag, _ in candidates), default=0)
        gates[key] = candidates
        if start != maximum:
            residuals.append({'core': core, 'id': key[1], 'start': start,
                              'expected': maximum, 'residual': start - maximum})
    if residuals:
        return {'consistent': False, 'residuals': residuals, 'critical_cross_links': [],
                'errors': ['start-gate residuals'], 'scope': 'No critical-path claim from inconsistent evidence'}
    makespan = result['makespan']
    queue = [key for key, (_, end) in trace.items() if end == makespan]
    visited, critical = set(), {}
    while queue:
        key = queue.pop()
        if key in visited:
            continue
        visited.add(key)
        start = trace[key][0]
        for predecessor, lag, link_index in gates[key]:
            if trace[predecessor][1] + lag != start:
                continue
            queue.append(predecessor)
            if link_index is not None:
                other = max((trace[p][1] + d for p, d, i in gates[key]
                             if i != link_index), default=0)
                exposed = min(delay, max(0, start - other))
                link = contract['cross_links'][link_index]
                critical[link_index] = {'index': link_index, 'source': list(predecessor),
                                        'target': list(key), 'exposed_delay_cycles': exposed,
                                        'delay_range': [0, delay],
                                        'tensor_id': link['tensor_id'], 'size': link['size'],
                                        'source_core': link['source'][0],
                                        'source_copy_out_id': link['source'][1],
                                        'target_core': link['target'][0],
                                        'target_copy_in_id': link['target'][1]}
    return {'consistent': True, 'residuals': [],
            'critical_cross_links': [critical[i] for i in sorted(critical)],
            'critical_operations': [list(k) for k in sorted(visited)],
            'errors': [], 'scope': 'Retrospective tight paths; exposed delay fixes all other observed gates and durations'}
