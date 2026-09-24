"""Guarded all-vector fork/chain/reduce stages with persistent lane ownership.

No case IDs or known scores are used. Certificates concern the original DAG
and raw tensor priority intervals, not official spill or runtime feasibility.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import heapq

from .direct import Index, UnsupportedStructure, derive_multicore_plan


def _need(condition, reason):
    if not condition:
        raise UnsupportedStructure('vector lanes: ' + reason)


def recognize(index):
    """Recognize a conservative tensor-only template; never guess a stage."""
    graph, ops = index.graph, index.ops
    _need(ops and all(o['pipe'] == 'PIPE_V' for o in ops.values()), 'all eligible ops must use PIPE_V')
    original = {o['id']: o for o in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    incoming, outgoing = defaultdict(set), defaultdict(set)
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph['edges']:
        a, b = edge['source'], edge['target']
        _need((a in original and b in tensors) or (a in tensors and b in original),
              'only op/tensor incidence edges are supported')
        if a in original:
            outgoing[a].add(b)
            producers[b].add(a)
        else:
            incoming[b].add(a)
            consumers[a].add(b)
    _need(all(len(ps) <= 1 for ps in producers.values()), 'multi-producer tensor')
    ep = {t: producers[t] & ops.keys() for t in tensors}
    ec = {t: consumers[t] & ops.keys() for t in tensors}
    anchors = sorted(t for t in tensors if ec[t] and not ep[t])
    _need(len(anchors) >= 2, 'at least two independent external lane inputs required')
    _need(all(tensors[t]['pos'] == 'L1' and tensors[t]['size'] > 0 for t in anchors),
          'lane inputs must be positive-size L1 tensors')
    anchor_set = set(anchors)
    heads, head_anchor, head_barrier = {}, {}, {}
    for t in anchors:
        for u in sorted(ec[t]):
            _need(u not in heads, 'a lane head consumes more than one external input')
            extra = incoming[u] - {t}
            _need(len(extra) <= 1 and not (extra & anchor_set), 'head requires only its input and optional barrier')
            head_anchor[u] = t
            head_barrier[u] = next(iter(extra)) if extra else None
            heads[u] = []
    chain_ops, chain_output = set(), {}
    widths = set()
    for head in sorted(heads):
        anchor = head_anchor[head]
        vector_size = tensors[anchor]['size']
        u, previous = head, None
        while True:
            _need(u not in chain_ops, 'overlapping or cyclic vector chains')
            _need(u == head or incoming[u] == {previous}, 'interior chain has extra inputs')
            _need(len(outgoing[u]) == 1, 'each compute op must have one output tensor')
            chain_ops.add(u)
            heads[head].append(u)
            t = next(iter(outgoing[u]))
            _need(tensors[t]['pos'] == 'UB', 'chain outputs must be UB')
            size = tensors[t]['size']
            if 0 < size < vector_size:
                widths.add(size)
                chain_output[head] = t
                break
            _need(size == vector_size, 'chain must keep input size until strict scalar shrink')
            _need(len(ec[t]) == 1 and consumers[t] == ec[t], 'vector output must have one eligible consumer')
            previous, u = t, next(iter(ec[t]))
            _need(u not in heads, 'vector chain reaches another lane head')
    _need(len(widths) == 1, 'all leaf scalar outputs must have the same positive size')
    scalar_size = next(iter(widths))
    reducers = set(ops) - chain_ops
    _need(reducers, 'a scalar reduction tree is required')
    for u in reducers:
        _need(len(incoming[u]) == 2 and len(outgoing[u]) == 1, 'scalar reduction must have two inputs and one output')
        _need(all(tensors[t]['size'] == scalar_size and tensors[t]['pos'] == 'UB'
                  and len(ep[t]) == 1 for t in incoming[u] | outgoing[u]),
              'reduction tensors must be single-producer equal-width UB scalars')
    by_barrier = defaultdict(dict)
    for head in sorted(heads):
        barrier, anchor = head_barrier[head], head_anchor[head]
        _need(anchor not in by_barrier[barrier], 'duplicate lane at a barrier')
        by_barrier[barrier][anchor] = head
    stages, seen_heads, seen_reducers = [], set(), set()
    barrier = None
    while True:
        stage_heads = by_barrier.get(barrier, {})
        _need(set(stage_heads) == anchor_set, 'every stage must contain every lane exactly once')
        _need(not (set(stage_heads.values()) & seen_heads), 'stage barrier cycle')
        seen_heads.update(stage_heads.values())
        leaves = {chain_output[h]: h for h in stage_heads.values()}
        available = set(leaves)
        pending, ready = Counter(), []
        reduction_order, roots = [], []

        def publish(t, is_leaf=False):
            targets = ec[t]
            rs = targets & reducers
            if rs:
                _need(len(targets) == 1 and consumers[t] == targets,
                      'scalar tree interior has extra consumers')
                v = next(iter(rs))
                pending[v] += 1
                if pending[v] == 2:
                    _need(incoming[v] <= available, 'reduction mixes stages or duplicate inputs')
                    heapq.heappush(ready, v)
            else:
                _need(not is_leaf, 'lane scalar must enter the reduction tree')
                roots.append(t)

        for t in sorted(leaves):
            publish(t, is_leaf=True)
        while ready:
            u = heapq.heappop(ready)
            _need(u not in seen_reducers, 'reduction reused across stages')
            seen_reducers.add(u)
            reduction_order.append(u)
            t = next(iter(outgoing[u]))
            available.add(t)
            publish(t)
        _need(len(roots) == 1 and len(reduction_order) == len(anchors) - 1,
              'each stage must reduce all lanes into one binary-tree root')
        root = roots[0]
        stages.append({'heads': stage_heads, 'leaves': leaves,
                       'reducers': reduction_order, 'root': root})
        if not ec[root]:
            break
        _need(ec[root] == set(by_barrier.get(root, {}).values()),
              'root may only broadcast to next-stage heads')
        _need(consumers[root] == ec[root], 'intermediate root cannot have external copies')
        barrier = root
    _need(seen_heads == set(heads) and seen_reducers == reducers,
          'template does not cover all eligible operations')
    final_root = stages[-1]['root']
    for u, op in original.items():
        if u in ops:
            continue
        _need(len(incoming[u]) == len(outgoing[u]) == 1, 'boundary COPY requires one input and output')
        a, b = next(iter(incoming[u])), next(iter(outgoing[u]))
        if op['op'] == 'COPY_IN':
            _need(b in anchor_set and not producers[a] and tensors[a]['pos'] == 'DDR'
                  and consumers[a] == {u} and tensors[a]['size'] == tensors[b]['size'],
                  'COPY_IN must be an external DDR-to-lane boundary')
        else:
            _need(op['op'] == 'COPY_OUT' and a == final_root and not consumers[b]
                  and tensors[b]['pos'] == 'DDR' and tensors[b]['size'] == scalar_size,
                  'COPY_OUT must be the final scalar boundary')
    # No external tap is permitted from a vector chain or an intermediate scalar.
    for u in chain_ops | reducers:
        t = next(iter(outgoing[u]))
        _need(not (consumers[t] - ec[t]) or t == final_root, 'non-final tensor has an external consumer')
    return dict(index=index, tensors=tensors, incoming=incoming, outgoing=outgoing,
                ep=ep, ec=ec, anchors=anchors, heads=heads, head_anchor=head_anchor,
                stages=stages, scalar_size=scalar_size)


def _tree_order(template, stage):
    """Return iterative postorder actions and deterministic tree leaf order."""
    incoming, ep = template['incoming'], template['ep']
    leaves = stage['leaves']
    actions, lanes = [], []
    stack = [(stage['root'], False)]
    while stack:
        t, visited = stack.pop()
        if t in leaves:
            h = leaves[t]
            actions.append(('chain', h))
            lanes.append(template['head_anchor'][h])
        elif visited:
            actions.append(('reduce', next(iter(ep[t]))))
        else:
            stack.append((t, True))
            u = next(iter(ep[t]))
            for child in sorted(incoming[u], reverse=True):
                stack.append((child, False))
    return actions, lanes


def _partition(lanes, weights, cores):
    """Optimal maximum total lane work among contiguous partitions.

    Binary search is on an integer feasibility bound, not evaluated plans.
    Among feasible cuts, prefer work nearest the remaining average.
    """
    groups = min(len(lanes), cores)
    work = [weights[t] for t in lanes]
    low, high = max(max(work), (sum(work) + groups - 1) // groups), sum(work)

    def count(limit, seq):
        n, load = 1, 0
        for w in seq:
            if load + w > limit:
                n, load = n + 1, 0
            load += w
        return n

    while low < high:
        middle = (low + high) // 2
        if count(middle, work) <= groups:
            high = middle
        else:
            low = middle + 1
    # Minimum groups needed by every suffix under the frozen optimal limit.
    suffix_groups = [0] * (len(work) + 1)
    end, total = len(work), 0
    for i in range(len(work) - 1, -1, -1):
        total += work[i]
        while total > low:
            end -= 1
            total -= work[end]
        suffix_groups[i] = 1 + suffix_groups[end]
    result, start, remaining = {}, 0, sum(work)
    for core in range(groups):
        g = groups - core
        if g == 1:
            cut = len(work)
        else:
            prefix, choices = 0, []
            for cut in range(start + 1, len(work) - g + 2):
                prefix += work[cut - 1]
                if prefix > low:
                    break
                if suffix_groups[cut] <= g - 1:
                    choices.append((abs(prefix * g - remaining), cut))
            cut = min(choices)[1]
        for t in lanes[start:cut]:
            result[t] = core
        remaining -= sum(work[start:cut])
        start = cut
    return result, low


def build(graph, cores, config):
    return build_from_index(Index(graph), cores, config)


def build_from_index(index, cores, config):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    capacity = config['capacity']
    if set(capacity) != {'L1', 'UB'} or any(type(v) is not int or v < 0 for v in capacity.values()):
        raise ValueError('capacity must give nonnegative integer L1 and UB bytes')
    template = recognize(index)
    stages, anchors = template['stages'], template['anchors']
    _, lane_order = _tree_order(template, stages[0])
    weights = {t: sum(index.duration(u) for stage in stages
                      for u in template['heads'][stage['heads'][t]]) for t in anchors}
    lane_owner, partition_bound = _partition(lane_order, weights, cores)
    owner, order = {}, []
    # Small reduction nodes inherit the core contributing most original lane
    # compute work to their subtree. This minimizes neither global COPY nor time.
    for stage in stages:
        support = {}
        actions, _ = _tree_order(template, stage)
        for kind, u in actions:
            if kind == 'chain':
                chain = template['heads'][u]
                core = lane_owner[template['head_anchor'][u]]
                for v in chain:
                    owner[v] = core
                order.extend(chain)
                t = next(iter(template['outgoing'][chain[-1]]))
                support[t] = Counter({core: sum(index.duration(v) for v in chain)})
            else:
                counts = Counter()
                for t in sorted(template['incoming'][u]):
                    counts.update(support[t])
                core = min(counts, key=lambda c: (-counts[c], c))
                owner[u] = core
                order.append(u)
                support[next(iter(template['outgoing'][u]))] = counts
    positions = {u: i for i, u in enumerate(order)}
    if set(positions) != set(index.ops) or len(order) != len(index.ops):
        raise AssertionError('internal eligible coverage failure')
    if any(positions[u] >= positions[v] for u in index.ops for v in index.succ[u]):
        raise AssertionError('internal global topological order failure')
    per_core = [[] for _ in range(cores)]
    for u in order:
        per_core[owner[u]].append(u)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in per_core]}
    derive_multicore_plan(index.graph, plan)
    scalar_size = template['scalar_size']
    core_detail = []
    for core, seq in enumerate(per_core):
        assigned = [t for t in anchors if lane_owner[t] == core]
        first, last = {}, {}
        for i, u in enumerate(seq):
            for t in template['incoming'][u] | template['outgoing'][u]:
                first.setdefault(t, i)
                last[t] = i
        changes = defaultdict(Counter)
        for t in first:
            tensor = template['tensors'][t]
            changes[first[t]][tensor['pos']] += tensor['size']
            changes[last[t] + 1][tensor['pos']] -= tensor['size']
        live, peaks = Counter(), Counter()
        for i in range(len(seq)):
            live.update(changes[i])
            for pool in ('L1', 'UB'):
                peaks[pool] = max(peaks[pool], live[pool])
        bound = {'L1': sum(template['tensors'][t]['size'] for t in assigned),
                 'UB': 2 * max((template['tensors'][t]['size'] for t in assigned), default=0)
                       + 2 * len(anchors) * scalar_size}
        if any(peaks[p] > bound[p] for p in bound):
            raise AssertionError('raw priority interval exceeds template envelope')
        core_detail.append({'core': core, 'lane_inputs': assigned,
                            'compute_work_cycles': sum(index.duration(u) for u in seq),
                            'raw_priority_peak_bytes': {p: peaks[p] for p in bound},
                            'raw_envelope_bytes': bound,
                            'raw_envelope_within_capacity': all(bound[p] <= capacity[p] for p in bound)})
    cross = Counter()
    for t in template['tensors']:
        if template['ep'][t]:
            source = owner[next(iter(template['ep'][t]))]
            targets = {owner[u] for u in template['ec'][t]} - {source}
            if targets:
                _need(template['tensors'][t]['size'] == scalar_size, 'internal vector crosses a core')
                cross['tensor_source_destination_pairs'] += len(targets)
                cross['copy_bytes_without_spill'] += 2 * len(targets) * scalar_size
    return plan, {'selected_strategy': 'vector_lanes', 'eligible_ops': len(index.ops),
                  'stages': len(stages), 'lanes': len(anchors), 'cores': cores,
                  'scalar_bytes': scalar_size, 'fixed_lane_ownership': True,
                  'maximum_open_vector_chains_per_core_in_priority': 1,
                  'input_consumer_cores_per_lane': 1,
                  'contiguous_lane_compute_partition_bound': partition_bound,
                  'cross_core_raw_tensor_transfers': dict(cross), 'per_core': core_detail,
                  'certificate_scope': 'original eligible DAG plus compute FIFO acyclic; raw tensor priority intervals only',
                  'zero_spill_claim': False, 'official_score_available': False,
                  'limitations': ['Step2/Step3 and inserted COPY FIFO still require final E0',
                                  'fixed lane granularity can imbalance cores',
                                  'compute closure may sacrifice DMA overlap; no optimality claim']}


def main():
    """Direct matrix contract, zero online evaluations."""
    import argparse
    from datetime import datetime, timezone
    import hashlib
    import json
    from pathlib import Path
    import time
    from .baseline import ROOT
    from evaluation_validation import read_evaluation_config

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
              'validation_scope': 'Official derive structural check plus original compute/FIFO acyclicity only'}
    try:
        graph = json.loads(args.graph.read_text())
        plan, detail = build(graph, args.cores, read_evaluation_config(str(args.config)))
        folder = args.evidence/'vector_lanes'
        folder.mkdir()
        data = (json.dumps(plan, ensure_ascii=False, indent=2) + '\n').encode()
        (folder/'plan.json').write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        ledger['attempts'].append({'name': 'vector_lanes', 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter() - started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(data)
        ledger.update(status='ok', selected='vector_lanes', plan_sha256=digest,
                      stop_reason='single_guarded_construction')
    except Exception as error:
        ledger.update(status='failed', error=repr(error))
    finally:
        ledger.update(finished_at=datetime.now(timezone.utc).isoformat(),
                      internal_wall_seconds=time.perf_counter()-started)
        (args.evidence/'solver.json').write_text(json.dumps(ledger, indent=2) + '\n')
    print(json.dumps({k: ledger[k] for k in ('status', 'calls', 'internal_wall_seconds')}))
    if ledger['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
