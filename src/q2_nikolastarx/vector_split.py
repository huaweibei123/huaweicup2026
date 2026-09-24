"""Guarded half-lane transfers to reduce indivisible all-V load imbalance.

One deterministic construction, with explicit DDR cost. The timing model is a
fixed-candidate lower bound; shared DDR/COPY FIFO and memory reuse still need E0.
This experimental candidate is not part of the frozen adaptive_semantic solver.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import heapq
import math

from .direct import Index, UnsupportedStructure, derive_multicore_plan
from .vector_lanes import recognize, _tree_order
from .vector_arrival import _list_tree


def _need(condition, reason):
    if not condition:
        raise UnsupportedStructure('vector split: ' + reason)


def _transfer(size, bandwidth, delay):
    isolated = max(1, (size + bandwidth - 1) // bandwidth)
    # Frozen COPY duration uses float division before ceil. An exact integer
    # ceil can exceed it for large inputs, invalidating a claimed lower bound.
    try:
        official = max(1, math.ceil(size / bandwidth))
    except (OverflowError, ValueError):
        raise UnsupportedStructure('vector split: COPY duration exceeds numeric domain') from None
    _need(isolated == official, 'COPY integer/official duration rounding differs')
    return delay + 2 * isolated


def _fixed_bound(index, model, owners, sequences, bandwidth, delay):
    """Single-producer UB crossings require COPY_OUT, delay, COPY_IN.

    These guarded tensor dependencies survive reconstruction. Adjacent original
    V operations retain their singleton FIFO order. Ignoring bandwidth sharing,
    boundary loads and new memory dependencies can only lower this bound.
    """
    arcs = {u: {} for u in index.ops}
    for t, tensor in model['tensors'].items():
        for a in model['ep'][t]:
            for b in model['ec'][t]:
                crossing = owners[a] != owners[b]
                if crossing:
                    _need(tensor['pos'] == 'UB', 'bound requires internal UB crossings')
                lag = _transfer(tensor['size'], bandwidth, delay) if crossing else 0
                arcs[a][b] = max(arcs[a].get(b, 0), lag)
    for seq in sequences:
        for a, b in zip(seq, seq[1:]):
            arcs[a].setdefault(b, 0)
    degrees = Counter(b for values in arcs.values() for b in values)
    ready = [u for u in arcs if not degrees[u]]
    heapq.heapify(ready)
    starts, count = dict.fromkeys(arcs, 0), 0
    while ready:
        a = heapq.heappop(ready)
        count += 1
        for b, lag in sorted(arcs[a].items()):
            starts[b] = max(starts[b], starts[a] + index.duration(a) + lag)
            degrees[b] -= 1
            if not degrees[b]:
                heapq.heappush(ready, b)
    if count != len(arcs):
        raise AssertionError('original compute plus submitted V FIFO cycle')
    end = {u: starts[u] + index.duration(u) for u in arcs}
    return {'makespan_lower_bound_cycles': max(end.values()),
            'stage_root_end': [end[next(iter(model['ep'][s['root']]))] for s in model['stages']],
            'scope': 'fixed singleton V FIFO plus retained tensor dependencies and minimum COPY lags',
            'global_optimum_bound': False, 'official_execution_validated': False}


def build(graph, cores, config):
    return build_from_index(Index(graph), cores, config)


def build_from_index(index, cores, config):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    bandwidth, delay, capacity = (config['bandwidth'], config['cross_core_copy_delay_cycles'],
                                  config['capacity'])
    if (type(bandwidth) is not int or bandwidth <= 0 or type(delay) is not int or delay < 0
            or set(capacity) != {'L1', 'UB'}
            or any(type(v) is not int or v < 0 for v in capacity.values())):
        raise ValueError('invalid capacity, bandwidth or delay')
    model = recognize(index)
    stages, anchors = model['stages'], model['anchors']
    q, r = divmod(len(anchors), cores)
    _need(q >= 1 and 0 < 2*r < cores, 'requires positive remainder with disjoint pairs and a spare core')
    lengths = {len(chain) for chain in model['heads'].values()}
    _need(len(lengths) == 1, 'all chains must have equal length')
    length = next(iter(lengths))
    _need(length >= 2 and length % 2 == 0, 'chain length must be positive and even')
    chain_work = {index.duration(u) for chain in model['heads'].values() for u in chain}
    _need(len(chain_work) == 1, 'all chain operations must have equal durations')
    p, half = next(iter(chain_work)), length // 2
    sizes = {model['tensors'][a]['size'] for a in anchors}
    _need(len(sizes) == 1, 'all lane inputs must have equal size')
    size = next(iter(sizes))
    _, lane_order = _tree_order(model, stages[0])
    whole = [lane_order[c*q:(c+1)*q] for c in range(cores)]
    split = [{'anchor': a, 'sender': i, 'receiver': r+i}
             for i, a in enumerate(lane_order[q*cores:])]
    root_core = 2*r
    scalar_lag = _transfer(model['scalar_size'], bandwidth, delay)
    vector_lag = _transfer(size, bandwidth, delay)
    owners, order, free, previous_root = {}, [], [0]*cores, None
    stage_detail = []
    for number, stage in enumerate(stages):
        leaves, prefixes = {}, {}

        def put(chunk, c, release):
            start = max(free[c], release)
            end = start + sum(index.duration(u) for u in chunk)
            free[c] = end
            order.extend(chunk)
            for u in chunk:
                owners[u] = c
            return end

        def release(c):
            return 0 if previous_root is None else previous_root + scalar_lag * (c != root_core)

        for spec in split:
            chain = model['heads'][stage['heads'][spec['anchor']]]
            prefixes[spec['anchor']] = put(chain[:half], spec['sender'], release(spec['sender']))
        for c, lanes in enumerate(whole):
            for a in lanes:
                chain = model['heads'][stage['heads'][a]]
                leaves[chain[-1]] = (c, put(chain, c, release(c)))
        for spec in split:
            chain = model['heads'][stage['heads'][spec['anchor']]]
            c = spec['receiver']
            leaves[chain[-1]] = (c, put(chain[half:], c, prefixes[spec['anchor']]+vector_lag))
        chain_finish = tuple(free)
        children = {u: tuple(next(iter(model['ep'][t])) for t in sorted(model['incoming'][u]))
                    for u in stage['reducers']}
        durations = {u: index.duration(u) for u in stage['reducers']}
        assigned = {u: root_core for u in stage['reducers']}
        seq, done, _ = _list_tree(children, stage['reducers'], durations, leaves, assigned, free, scalar_lag)
        root = next(iter(model['ep'][stage['root']]))
        assert seq[-1] == root
        order.extend(seq)
        owners.update(assigned)
        end = done[root][1]
        stage_detail.append({'stage': number, 'root_op': root, 'root_core': root_core,
                             'independent_lag_chain_end_by_core': chain_finish,
                             'listed_root_end': end,
                             'listed_root_period': end - (previous_root or 0)})
        previous_root = end
    position = {u: i for i, u in enumerate(order)}
    if set(position) != set(index.ops) or len(order) != len(index.ops):
        raise AssertionError('eligible coverage failure')
    if any(position[a] >= position[b] for a in index.ops for b in index.succ[a]):
        raise AssertionError('global topological order failure')
    sequences = [[] for _ in range(cores)]
    for u in order:
        sequences[owners[u]].append(u)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
    derive_multicore_plan(index.graph, plan)
    bound = _fixed_bound(index, model, owners, sequences, bandwidth, delay)
    assert bound['makespan_lower_bound_cycles'] <= previous_root
    per_core = []
    for c, seq in enumerate(sequences):
        first, last, changes = {}, {}, defaultdict(Counter)
        for i, u in enumerate(seq):
            for t in model['incoming'][u] | model['outgoing'][u]:
                first.setdefault(t, i)
                last[t] = i
        for t in first:
            tensor = model['tensors'][t]
            changes[first[t]][tensor['pos']] += tensor['size']
            changes[last[t]+1][tensor['pos']] -= tensor['size']
        live, peak = Counter(), Counter()
        for i in range(len(seq)):
            live.update(changes[i])
            for pool in ('L1', 'UB'):
                peak[pool] = max(peak[pool], live[pool])
        per_core.append({'core': c, 'compute_work_cycles': sum(index.duration(u) for u in seq),
                         'original_compute_touch_peak_bytes': {p: peak[p] for p in capacity},
                         'original_peak_within_capacity': all(peak[p] <= capacity[p] for p in capacity)})
    return plan, {'selected_strategy': 'vector_split', 'eligible_ops': len(index.ops),
        'cores': cores, 'lanes': len(anchors), 'stages': len(stages),
        'whole_lanes_per_core': q, 'split_pairs': split, 'whole_lanes': whole,
        'chain_length': length, 'chain_op_cycles': p, 'vector_bytes': size,
        'fixed_root_core': root_core,
        'chain_only_work_lower_bound_cycles': ((len(anchors)*length+cores-1)//cores)*p,
        'assigned_chain_work_maximum_cycles': (q*length+half)*p,
        'whole_lane_restricted_chain_work_lower_bound_cycles': (q+1)*length*p,
        'vector_copy_minimum_lag_cycles': vector_lag,
        'ideal_equal_release_communication_window_cycles': (q*length-half)*p,
        'isolated_all_pairs_service_allowance_cycles': delay+2*r*((size+bandwidth-1)//bandwidth),
        'planned_large_crossing_pairs': r*len(stages),
        'planned_large_vector_added_copy_bytes_without_spill': 2*r*size*len(stages),
        'listed_independent_lag_proxy_cycles': previous_root, 'fixed_plan_bound': bound,
        'stage_detail': stage_detail, 'per_core': per_core,
        'zero_spill_claim': False, 'official_score_available': False,
        'limitations': ['timing ignores shared DDR, boundary COPY, COPY FIFO and Step3 memory edges',
                       'original-compute touch peaks omit inserted COPY/spill; not a memory certificate',
                       'isolated service allowance is not an official upper bound',
                       'centralized scalar reduction and equal-half placement are heuristics',
                       'substantial extra DDR is explicit; not a Pareto improvement claim']}


def main():
    """Frozen direct-runner CLI: one construction and zero online scoring."""
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
              'validation_scope': 'derive structure, original compute/V FIFO acyclicity and fixed lower bound'}
    try:
        config = read_evaluation_config(str(args.config))
        config.update(read_required_settings(str(args.config), 'multicore_scene_b', ('cross_core_copy_delay_cycles',)))
        plan, detail = build(json.loads(args.graph.read_text()), args.cores, config)
        folder = args.evidence/'vector_split'
        folder.mkdir()
        data = (json.dumps(plan, ensure_ascii=False, indent=2)+'\n').encode()
        (folder/'plan.json').write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        ledger['attempts'].append({'name': 'vector_split', 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter()-started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(data)
        ledger.update(status='ok', selected='vector_split', plan_sha256=digest,
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
