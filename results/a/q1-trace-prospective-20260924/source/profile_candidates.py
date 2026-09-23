"""Small Q1 split/cover neighborhoods guided by actual Task compilation.

Scores prioritize proposals only. They are not makespan bounds or spill
certificates. A changed partition always receives fresh official compilation.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path
import time

from search import OFFICIAL, dump, plan_key
from prototype import read_evaluation_config
from structure import topological
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order
from schedule_step2 import _find_copy_in_backings
import multicore_cut_evaluate_problem_1 as official


def split_plan(plan, task, suffix):
    result = copy.deepcopy(plan)
    new_task = max(result['node_to_subgraph'].values()) + 1
    for node in result['node_to_subgraph']:
        if int(node) in suffix:
            result['node_to_subgraph'][node] = new_task
    for order in result['core_schedules']:
        if task in order:
            order.insert(order.index(task) + 1, new_task)
            break
    return result


def merge_plan(plan, a, b):
    result = copy.deepcopy(plan)
    for node, task in result['node_to_subgraph'].items():
        if task == b:
            result['node_to_subgraph'][node] = a
    for order in result['core_schedules']:
        if b in order:
            order.remove(b)
    return result


def is_cover(successors, a, b):
    pending, seen = list(successors[a] - {b}), set()
    while pending:
        node = pending.pop()
        if node == b:
            return False
        if node not in seen:
            seen.add(node)
            pending.extend(successors[node] - seen)
    return True


def candidates(graph, plan, seen, limit=4, max_merge_ops=256):
    start = time.monotonic()
    settings = read_evaluation_config(str(OFFICIAL / 'data/config.txt'))
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    owner = view['core_by_subgraph']
    mapping = view['mapping']
    compute_ids = set(mapping)
    producers, consumers, _ = official._original_tensor_views(graph)
    ops = {op['id']: op for op in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    profiles = []
    original = official.step2_spill_insertion

    def capture(local, sequence, capacity):
        result = original(local, sequence, capacity)
        local_ops = {op['id']: op for op in local['ops']}
        compute_order = [op for op in sequence if op in compute_ids]
        positions = {op: i for i, op in enumerate(sequence)}
        touches = collections.defaultdict(set)
        for edge in local['edges']:
            a, b = edge['source'], edge['target']
            if a in positions and b not in local_ops:
                touches[b].add(positions[a])
            elif b in positions and a not in local_ops:
                touches[a].add(positions[b])
        delta = {kind: [0] * (len(sequence) + 1) for kind in capacity}
        for tensor in local['tensors']:
            uses, kind = touches[tensor['id']], tensor['pos']
            if uses and kind in delta:
                delta[kind][min(uses)] += tensor['size']
                delta[kind][max(uses) + 1] -= tensor['size']
        residency = dict.fromkeys(capacity, 0)
        pressure, peak_step = 0.0, 0
        for i in range(len(sequence)):
            for kind in capacity:
                residency[kind] += delta[kind][i]
            ratio = max(residency[kind] / capacity[kind] for kind in capacity)
            if ratio > pressure:
                pressure, peak_step = ratio, i
        cut_points = collections.defaultdict(set)

        def add_step(step, reason):
            # The cut only selects compute members; new Tasks get fresh COPY
            # nodes and Step1 order. Never submit slices of an old local order.
            cut = sum(positions[op] < step for op in compute_order)
            for value in [cut, cut + 1]:
                if 0 < value < len(compute_order):
                    cut_points[value].add(reason)

        add_step(peak_step, 'actual_step1_peak')
        if result['overflow_log']:
            add_step(result['overflow_log'][0]['step'], 'first_overflow')
        if len(compute_order) > 1:
            cut_points[len(compute_order) // 2].add('midpoint_fallback')
        spill_bytes = sum(r['size'] * (1 + int(r['spill_out_copies_data'])) for r in result['spill_records'])
        profiles.append({'compute_order': compute_order, 'positions': positions,
                         'cuts': {str(k): sorted(v) for k, v in cut_points.items()},
                         'peak_ratio': pressure, 'peak_step': peak_step, 'spill_bytes': spill_bytes,
                         'copy_bytes': official._copy_traffic_bytes(local),
                         'initial_backings': _find_copy_in_backings(local),
                         'local_graph_sha256': hashlib.sha256(json.dumps(local, separators=(',', ':')).encode()).hexdigest(),
                         'step1': sequence, 'spill_records': result['spill_records']})
        return result

    official.step2_spill_insertion = capture
    try:
        official._build_scene_a_tasks(graph, plan, settings['bandwidth'], settings['capacity'])
    finally:
        official.step2_spill_insertion = original
    assert len(profiles) == len(view['subgraph_ids'])
    by_task = dict(zip(view['subgraph_ids'], profiles))
    for task, profile in by_task.items():
        profile['task_id'] = task

    # Boundary entry/export cuts use actual Step1 compute positions, but their
    # priority is deliberately heuristic: remote Task completion still gates.
    for tid, tensor in tensors.items():
        prod = producers.get(tid, set()) & compute_ids
        cons = consumers.get(tid, set()) & compute_ids
        for producer in prod:
            task = mapping[producer]
            if any(owner[mapping[c]] != owner[task] for c in cons):
                p = by_task[task]
                cut = p['compute_order'].index(producer) + 1
                if cut < len(p['compute_order']):
                    p['cuts'].setdefault(str(cut), []).append('remote_export')
        for consumer in cons:
            task = mapping[consumer]
            if any(owner[mapping[p]] != owner[task] for p in prod):
                p = by_task[task]
                cut = p['compute_order'].index(consumer)
                if cut > 0:
                    p['cuts'].setdefault(str(cut), []).append('remote_entry')

    splits = []
    for task, p in by_task.items():
        for cut, reasons in p['cuts'].items():
            cut = int(cut)
            priority = (p['spill_bytes'], int('first_overflow' in reasons),
                        int('remote_export' in reasons or 'remote_entry' in reasons),
                        p['peak_ratio'], -abs(2 * cut - len(p['compute_order'])))
            splits.append({'kind': 'split', 'task': task, 'cut': cut,
                           'reasons': sorted(set(reasons)), 'priority': priority})
    splits.sort(key=lambda x: (tuple(-n for n in x['priority']), x['task'], x['cut']))

    successors = {task: set() for task in view['subgraph_ids']}
    edges = set(view['dependency_pairs'])
    edges.update((a, b) for order in plan['core_schedules'] for a, b in zip(order, order[1:]))
    for a, b in edges:
        successors[a].add(b)
    topological(successors, successors)

    def boundary_bytes(members):
        total = 0
        for tid, tensor in tensors.items():
            prod, cons = producers.get(tid, set()), consumers.get(tid, set())
            local_prod, local_cons = prod & members, cons & members
            eligible_cons = cons & compute_ids
            has_copy_out = any(ops[c]['op'] == 'COPY_OUT' for c in cons)
            total += tensor['size'] * (int(bool(local_cons) and not local_prod)
                + int(bool(local_prod) and (has_copy_out or not eligible_cons or bool(eligible_cons - members))))
        return total

    merges, cover_rejections = [], 0
    for order in plan['core_schedules']:
        for a, b in zip(order, order[1:]):
            members = set(view['nodes_by_subgraph'][a]) | set(view['nodes_by_subgraph'][b])
            if len(members) > max_merge_ops:
                continue
            if not is_cover(successors, a, b):
                cover_rejections += 1
                continue
            saving = by_task[a]['copy_bytes'] + by_task[b]['copy_bytes'] - boundary_bytes(members)
            merges.append({'kind': 'merge', 'tasks': [a, b], 'boundary_saving_bytes': saving,
                           'rank_scope': 'Pre-spill boundary bytes only; no guarantee on total bytes or makespan'})
    merges.sort(key=lambda x: (-x['boundary_saving_bytes'], x['tasks']))

    selected, rejected, duplicates = [], [], 0
    queues = [collections.deque(splits), collections.deque(merges)]
    while any(queues) and len(selected) < limit:
        for queue in queues:
            while queue and len(selected) < limit:
                choice = queue.popleft()
                if choice['kind'] == 'split':
                    suffix = set(by_task[choice['task']]['compute_order'][choice['cut']:])
                    candidate = split_plan(plan, choice['task'], suffix)
                else:
                    candidate = merge_plan(plan, *choice['tasks'])
                key = plan_key(candidate)
                if key in seen:
                    duplicates += 1
                    continue
                try:
                    validate_task_order(derive_multicore_plan(graph, candidate))
                except ValueError as error:
                    rejected.append({'choice': choice, 'error': str(error)})
                    continue
                seen.add(key)
                selected.append({'choice': choice, 'plan': candidate, 'key': key})
                break
    for p in profiles:
        p.pop('positions')
    return {'profiles': profiles, 'candidates': selected, 'rejected': rejected,
            'duplicates': duplicates, 'cover_rejections': cover_rejections,
            'proposal_seconds': time.monotonic() - start,
            'scope': 'Deterministic heuristic priorities; no memory or makespan hard pruning'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph', type=Path); p.add_argument('parent', type=Path)
    p.add_argument('seen', type=Path); p.add_argument('output', type=Path)
    args = p.parse_args()
    result = candidates(json.loads(args.graph.read_text()), json.loads(args.parent.read_text()),
                        set(json.loads(args.seen.read_text())))
    dump(args.output, result)


if __name__ == '__main__':
    main()
