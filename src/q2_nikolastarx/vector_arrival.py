"""One guarded whole-lane / arrival-tree placement rule; zero online E0 calls.

The tree DP is a placement surrogate. Fixed V words are then constructed and
their mandatory-dependency bound recomputed; neither is an official schedule.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import heapq
import math

from .direct import Index, derive_multicore_plan
from .vector_lanes import recognize, _partition, _tree_order


def _place_tree(children, order, durations, leaves, core_free, transfer, next_work):
    """DP then root-conditioned backtracking; leaves are (physical core, end)."""
    k = len(core_free)
    tables = {t: [end if c == owner else math.inf for c in range(k)]
              for t, (owner, end) in leaves.items()}
    choices = {}
    for u in order:
        row, args = [], []
        for c in range(k):
            selected = [min(range(k), key=lambda a: (tables[t][a] + transfer * (a != c), a))
                        for t in children[u]]
            arrival = max(tables[t][a] + transfer * (a != c)
                          for t, a in zip(children[u], selected))
            row.append(max(core_free[c], arrival) + durations[u])
            args.append(selected)
        tables[u], choices[u] = row, args
    root = order[-1]

    def root_key(c):
        end = tables[root][c]
        horizon = max((end + transfer * (c != d) + w for d, w in enumerate(next_work) if w), default=end)
        return horizon, end, c

    root_core = min(range(k), key=root_key)
    owners, stack = {}, [(root, root_core)]
    while stack:
        u, c = stack.pop()
        if u in leaves:
            assert leaves[u][0] == c
            continue
        owners[u] = c
        stack.extend(zip(children[u], choices[u][c]))
    return owners, {'optimistic_root_end': tables[root][root_core],
                    'root_core': root_core, 'root_choice_horizon': root_key(root_core)[0],
                    'root_end_by_core': tables[root]}


def _list_tree(children, order, durations, leaves, owners, core_free, transfer):
    """Materialize one fixed-owner V word, accounting for sibling contention."""
    k = len(core_free)
    successors, pending = defaultdict(list), {}
    for u in order:
        pending[u] = sum(t not in leaves for t in children[u])
        for t in children[u]:
            successors[t].append(u)
    tail = {}
    for u in reversed(order):
        tail[u] = durations[u] + max((tail[v] for v in successors[u]), default=0)
    done = dict(leaves)
    future, ready = [[] for _ in range(k)], [[] for _ in range(k)]

    def publish(u):
        c = owners[u]
        release = max(done[t][1] + transfer * (done[t][0] != c) for t in children[u])
        heapq.heappush(future[c], (release, -tail[u], u))

    for u in order:
        if not pending[u]:
            publish(u)
    result, timing = [], {}
    while len(result) < len(order):
        heads = []
        for c in range(k):
            while future[c] and future[c][0][0] <= core_free[c]:
                release, neg_tail, u = heapq.heappop(future[c])
                heapq.heappush(ready[c], (neg_tail, u, release))
            if ready[c]:
                neg_tail, u, release = ready[c][0]
                heads.append((core_free[c], neg_tail, u, c, True))
            elif future[c]:
                release, neg_tail, u = future[c][0]
                heads.append((release, neg_tail, u, c, False))
        if not heads:
            raise AssertionError('scalar tree has no ready node')
        start, _, u, c, from_ready = min(heads)
        heapq.heappop(ready[c] if from_ready else future[c])
        end = start + durations[u]
        core_free[c] = end
        done[u], timing[u] = (c, end), (start, end)
        result.append(u)
        for v in successors[u]:
            pending[v] -= 1
            if not pending[v]:
                publish(v)
    return result, done, timing


def _fixed_bound(index, template, owner, sequences, transfer):
    """Final original compute graph + submitted V FIFO, with mandatory lags."""
    arcs = {u: {} for u in index.ops}
    for t in template['tensors']:
        for p in template['ep'][t]:
            for c in template['ec'][t]:
                if owner[p] != owner[c] and template['tensors'][t]['size'] != template['scalar_size']:
                    raise AssertionError('fixed whole-lane plan crosses a non-scalar tensor')
                lag = transfer if owner[p] != owner[c] else 0
                arcs[p][c] = max(arcs[p].get(c, 0), lag)
    for seq in sequences:
        for p, c in zip(seq, seq[1:]):
            arcs[p].setdefault(c, 0)
    degree = Counter(c for values in arcs.values() for c in values)
    ready = [u for u in arcs if not degree[u]]
    heapq.heapify(ready)
    start, parent, count = dict.fromkeys(arcs, 0), {}, 0
    while ready:
        p = heapq.heappop(ready)
        count += 1
        for c, lag in sorted(arcs[p].items()):
            value = start[p] + index.duration(p) + lag
            if value > start[c]:
                start[c], parent[c] = value, (p, lag)
            degree[c] -= 1
            if not degree[c]:
                heapq.heappush(ready, c)
    if count != len(arcs):
        raise AssertionError('original compute plus submitted FIFO cycle')
    end = {u: start[u] + index.duration(u) for u in arcs}
    sink = max(end, key=lambda u: (end[u], -u))
    path, lag_sum, u = [], 0, sink
    while True:
        path.append(u)
        if u not in parent:
            break
        u, lag = parent[u]
        lag_sum += lag
    return {'makespan_lower_bound_cycles': end[sink], 'path_compute_cycles': end[sink]-lag_sum,
            'path_transfer_lag_cycles': lag_sum, 'path_transfer_count': lag_sum//transfer if transfer else 0,
            'path_op_count': len(path),
            'stage_root_end': [end[next(iter(template['ep'][s['root']]))] for s in template['stages']],
            'scope': 'fixed singleton V FIFO plus retained tensor dependencies; not global optimum',
            'official_execution_validated': False}


def build(graph, cores, config):
    return build_from_index(Index(graph), cores, config)


def build_from_index(index, cores, config):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    capacity = config['capacity']
    bandwidth, delay = config['bandwidth'], config['cross_core_copy_delay_cycles']
    if (set(capacity) != {'L1', 'UB'} or any(type(v) is not int or v < 0 for v in capacity.values())
            or type(bandwidth) is not int or bandwidth <= 0 or type(delay) is not int or delay < 0):
        raise ValueError('invalid capacity, bandwidth or cross-core delay')
    template = recognize(index)
    stages, anchors = template['stages'], template['anchors']
    _, lane_order = _tree_order(template, stages[0])
    weights = {a: sum(index.duration(u) for s in stages for u in template['heads'][s['heads'][a]])
               for a in anchors}
    lane_owner, partition_bound = _partition(lane_order, weights, cores)
    transfer = delay + 2 * max(1, (template['scalar_size']+bandwidth-1)//bandwidth)
    stage_work = []
    for s in stages:
        row = [0]*cores
        for a in anchors:
            row[lane_owner[a]] += sum(index.duration(u) for u in template['heads'][s['heads'][a]])
        stage_work.append(row)
    owner, order, free, previous = {}, [], [0]*cores, None
    stage_detail = []
    for number, s in enumerate(stages):
        leaves, first_by_core = {}, {}
        for a in lane_order:
            chain, c = template['heads'][s['heads'][a]], lane_owner[a]
            release = 0 if previous is None else previous[1] + transfer * (previous[0] != c)
            start = max(free[c], release)
            first_by_core.setdefault(c, start)
            end = start + sum(index.duration(u) for u in chain)
            free[c] = end
            for u in chain:
                owner[u] = c
            order.extend(chain)
            leaves[chain[-1]] = (c, end)
        children = {u: tuple(next(iter(template['ep'][t])) for t in sorted(template['incoming'][u]))
                    for u in s['reducers']}
        durations = {u: index.duration(u) for u in s['reducers']}
        next_work = stage_work[number+1] if number+1 < len(stages) else []
        reducer_owners, placement = _place_tree(children, s['reducers'], durations, leaves,
                                               tuple(free), transfer, next_work)
        seq, done, timing = _list_tree(children, s['reducers'], durations, leaves,
                                     reducer_owners, free, transfer)
        root = next(iter(template['ep'][s['root']]))
        assert seq[-1] == root
        owner.update(reducer_owners)
        order.extend(seq)
        # This is the realized V-word proxy, never the optimistic placement DP.
        current = done[root]
        assert current[1] >= placement['optimistic_root_end']
        crossing_depth = {u: int(previous is not None and previous[0] != c) for u, (c, _) in leaves.items()}
        for u in s['reducers']:
            crossing_depth[u] = max(crossing_depth[t] + int(owner[t] != owner[u]) for t in children[u])
        stage_detail.append({'stage': number, 'root_op': root, **placement,
            'listed_root_end': current[1], 'listed_root_period': current[1] - (previous[1] if previous else 0),
            'previous_root_core': None if previous is None else previous[0],
            'first_lane_start_by_core': first_by_core,
            'scalar_owner': {u: owner[u] for u in s['reducers']},
            'scalar_timing': timing,
            'max_broadcast_plus_reduction_crossings_on_data_path': crossing_depth[root]})
        previous = current
    positions = {u: i for i, u in enumerate(order)}
    if len(order) != len(index.ops) or set(positions) != set(index.ops):
        raise AssertionError('eligible coverage failure')
    if any(positions[u] >= positions[v] for u in index.ops for v in index.succ[u]):
        raise AssertionError('global topological order failure')
    sequences = [[] for _ in range(cores)]
    for u in order:
        sequences[owner[u]].append(u)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
    derive_multicore_plan(index.graph, plan)
    fixed_bound = _fixed_bound(index, template, owner, sequences, transfer)
    assert fixed_bound['makespan_lower_bound_cycles'] <= previous[1]
    per_core = []
    for c, seq in enumerate(sequences):
        assigned = [a for a in anchors if lane_owner[a] == c]
        first, last = {}, {}
        for i, u in enumerate(seq):
            for t in template['incoming'][u] | template['outgoing'][u]:
                first.setdefault(t, i)
                last[t] = i
        changes = defaultdict(Counter)
        for t in first:
            x = template['tensors'][t]
            changes[first[t]][x['pos']] += x['size']
            changes[last[t]+1][x['pos']] -= x['size']
        live, peaks = Counter(), Counter()
        for i in range(len(seq)):
            live.update(changes[i])
            for pool in ('L1', 'UB'):
                peaks[pool] = max(peaks[pool], live[pool])
        bound = {'L1': sum(template['tensors'][a]['size'] for a in assigned),
                 'UB': 2*max((template['tensors'][a]['size'] for a in assigned), default=0)
                       + 2*len(anchors)*template['scalar_size']}
        assert all(peaks[p] <= bound[p] for p in bound)
        per_core.append({'core': c, 'lane_inputs': assigned,
            'compute_work_cycles': sum(index.duration(u) for u in seq),
            'raw_priority_peak_bytes': {p: peaks[p] for p in bound}, 'raw_envelope_bytes': bound,
            'raw_envelope_within_capacity': all(bound[p] <= capacity[p] for p in bound)})
    return plan, {'selected_strategy': 'vector_arrival', 'eligible_ops': len(index.ops),
        'stages': len(stages), 'lanes': len(anchors), 'cores': cores,
        'scalar_bytes': template['scalar_size'], 'scalar_transfer_minimum_cycles': transfer,
        'fixed_lane_ownership': True, 'local_lanes_before_scalar_reducers': True,
        'contiguous_lane_compute_partition_bound': partition_bound,
        'placement_model': 'tree DP with frozen post-lane core availability; root one-stage broadcast lookahead',
        'listed_proxy_makespan_cycles': previous[1], 'fixed_plan_bound': fixed_bound,
        'per_core': per_core, 'stage_detail': stage_detail,
        'zero_spill_claim': False, 'official_score_available': False,
        'limitations': ['DP omits sibling V contention; fixed-owner list corrects only compute contention',
                       'COPY FIFO, shared DDR, input loading and memory edges omitted from timing proxy',
                       'local lane/scalar overlap is sacrificed; whole-lane granularity retained',
                       'one-stage root lookahead is heuristic, not a global optimum certificate']}


def main():
    """Direct matrix contract; one construction and no evaluator calls."""
    import argparse
    from datetime import datetime, timezone
    import hashlib
    import json
    from pathlib import Path
    import time
    from .baseline import ROOT
    from evaluation_validation import read_evaluation_config, read_required_settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT/'data/raw/a/official/data/config.txt')
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--wall', type=float, default=30)
    parser.add_argument('--evaluation-timeout', type=float, default=60)
    args = parser.parse_args()
    started = time.perf_counter()
    args.evidence.mkdir(parents=True, exist_ok=False)
    ledger = {'status': 'running', 'calls': {'E0': 0, 'E1': 0, 'E2': 0}, 'attempts': [],
              'started_at': datetime.now(timezone.utc).isoformat(),
              'validation_scope': 'derive structural validation and fixed original compute/V FIFO bound only'}
    try:
        config = read_evaluation_config(str(args.config))
        config.update(read_required_settings(str(args.config), 'multicore_scene_b', ('cross_core_copy_delay_cycles',)))
        plan, detail = build(json.loads(args.graph.read_text()), args.cores, config)
        folder = args.evidence/'vector_arrival'
        folder.mkdir()
        data = (json.dumps(plan, ensure_ascii=False, indent=2)+'\n').encode()
        (folder/'plan.json').write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        ledger['attempts'].append({'name': 'vector_arrival', 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter()-started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(data)
        ledger.update(status='ok', selected='vector_arrival', plan_sha256=digest,
                      stop_reason='single_guarded_construction')
    except Exception as error:
        ledger.update(status='failed', error=repr(error))
    finally:
        ledger.update(finished_at=datetime.now(timezone.utc).isoformat(),
                      internal_wall_seconds=time.perf_counter()-started)
        (args.evidence/'solver.json').write_text(json.dumps(ledger, indent=2)+'\n')
    print(json.dumps({k: ledger[k] for k in ('status', 'calls', 'internal_wall_seconds')}))
    if ledger['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
