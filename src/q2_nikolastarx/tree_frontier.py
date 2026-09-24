"""Guarded reduction-tree construction; private weighted postorder, zero scores.

The scalar P-R interchange proof applies only to noninterleaving private
subtrees. Real P2 has two pools, graph inputs, COPY and Step2/3 dependencies:
all reported interval peaks are raw submitted-priority diagnostics, not E0.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan

POOLS = ('L1', 'UB')


def _pool(tensor):
    return 'UB' if tensor['pos'] == 'DDR' else tensor['pos']


def _guard(index):
    """Accept only an explicit tensor reduction tree, not arbitrary DAGs."""
    if not index.ops or len(index.components) != 1:
        raise UnsupportedStructure('requires one nonempty eligible weak component')
    if any(len(index.succ[u]) > 1 for u in index.ops):
        raise UnsupportedStructure('requires at most one eligible successor per op')
    if any(index.direct_inputs.values()):
        raise UnsupportedStructure('direct op-op edges are outside the tensor-tree guard')
    if any(len(index.outputs[u]) != 1 for u in index.ops):
        raise UnsupportedStructure('requires exactly one output tensor per eligible op')
    if any(len(ps) != 1 for ps in index.producers.values() if ps):
        raise UnsupportedStructure('requires single eligible tensor producers')
    for tid, producers in index.producers.items():
        if not producers:
            continue
        if len(index.consumers[tid]) > 1:
            raise UnsupportedStructure('internal tensor fanout is outside the guard')
        if index.consumers[tid] and tid in index.copy_out_inputs:
            raise UnsupportedStructure('intermediate graph outputs are outside the guard')
    for u in index.ops:
        tensor_predecessors = set().union(*(index.producers[t] for t in index.inputs[u]))
        if tensor_predecessors != index.pred[u]:
            raise UnsupportedStructure('contracted COPY dependencies must equal tensor-tree edges')
    roots = [u for u in index.order if not index.succ[u]]
    if len(roots) != 1:
        raise UnsupportedStructure('requires exactly one sink')
    return roots[0]


def _postorder(index, root, capacity):
    """Private subtree profile in integer capacity-normalized scalar units.

    Graph inputs are excluded here, then counted once per core by first-last
    touch in _priority_peaks. For the selected order, per-pool peaks are also
    exact in the private inclusive-touch model, but are not jointly optimized.
    """
    scale = math.lcm(*(capacity[p] for p in POOLS))
    weight = {p: scale // capacity[p] for p in POOLS}
    peak, retained, work, size, children, pool_peak = {}, {}, {}, {}, {}, {}
    for u in index.order:
        tid = index.outputs[u][0]
        tensor = index.tensors[tid]
        out = Counter({_pool(tensor): tensor['size']})
        retained[u] = sum(out[p] * weight[p] for p in POOLS)
        order = sorted(index.pred[u], key=lambda v: (-(peak[v] - retained[v]), v))
        children[u] = order
        held, best = 0, 0
        live, by_pool = Counter(), Counter()
        for v in order:
            best = max(best, held + peak[v])
            for p in POOLS:
                by_pool[p] = max(by_pool[p], live[p] + pool_peak[v][p])
            child_t = index.tensors[index.outputs[v][0]]
            live[_pool(child_t)] += child_t['size']
            held += retained[v]
        peak[u] = max(best, held + retained[u])
        pool_peak[u] = {p: max(by_pool[p], live[p] + out[p]) for p in POOLS}
        work[u] = index.duration(u) + sum(work[v] for v in order)
        size[u] = 1 + sum(size[v] for v in order)
    # Iterative traversal also handles long unary chains without recursion depth.
    sequence, stack = [], [(root, False)]
    while stack:
        u, closing = stack.pop()
        if closing:
            sequence.append(u)
        else:
            stack.append((u, True))
            stack.extend((v, False) for v in reversed(children[u]))
    return sequence, children, work, size, {
        'private_scalar_peak_units': peak[root], 'scalar_units_per_capacity': scale,
        'private_pool_peak_bytes': pool_peak[root],
        'sibling_rule': 'descending private P-R, then op id',
        'optimality_scope': 'private scalar noninterleaving subtree order only',
    }


def _priority_peaks(index, sequences):
    """Count each touched original tensor once per core, including shared input.

    COPY allocation occurs before/after compute touches; these intervals do not
    model that expansion, allocator fragmentation, spills or runtime overlaps.
    """
    records = []
    for core, seq in enumerate(sequences):
        first, last = {}, {}
        for position, u in enumerate(seq):
            for tid in set(index.inputs[u]) | set(index.outputs[u]):
                first.setdefault(tid, position)
                last[tid] = position
        changes = defaultdict(Counter)
        for tid in first:
            tensor = index.tensors[tid]
            pool = _pool(tensor)
            changes[first[tid]][pool] += tensor['size']
            changes[last[tid] + 1][pool] -= tensor['size']
        live, peak = Counter(), Counter()
        for position in range(len(seq)):
            live.update(changes[position])
            for p in POOLS:
                peak[p] = max(peak[p], live[p])
        external = [t for t in first if not index.producers[t]]
        records.append({'core': core, 'ops': len(seq),
                        'raw_priority_peak_bytes': {p: peak[p] for p in POOLS},
                        'graph_input_tensors': len(external),
                        'shared_graph_input_tensors': sum(len(index.consumers[t]) > 1 for t in external)})
    return records


def build(graph, cores, config):
    return build_from_index(DAGIndex(graph), cores, config)


def build_from_index(index, cores, config):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    capacity = config['capacity']
    if set(capacity) != set(POOLS) or any(type(capacity[p]) is not int or capacity[p] <= 0 for p in POOLS):
        raise ValueError('capacity must contain positive integer L1 and UB bytes')
    root = _guard(index)
    sequence, children, work, size, profile = _postorder(index, root, capacity)
    # One fixed granularity, no trial schedules. At most W/(2k) work per
    # ordinary packet. This nominal granularity does NOT imply any minimum
    # packet count, a total 2k packet count or a balance guarantee.
    denominator = 2 * cores
    packets, skeleton = [], set()
    stack = [root]
    while stack:
        u = stack.pop()
        if denominator * work[u] <= work[root]:
            packets.append(u)
        else:
            skeleton.add(u)
            stack.extend(reversed(children[u]))
    end = {u: i + 1 for i, u in enumerate(sequence)}
    owner, load = {}, [0] * cores
    packet_records = []
    for u in sorted(packets, key=lambda v: (-work[v], v)):
        core = min(range(cores), key=lambda c: (load[c], c))
        for v in sequence[end[u] - size[u]:end[u]]:
            owner[v] = core
        load[core] += work[u]
        packet_records.append({'root': u, 'ops': size[u], 'work_cycles': work[u], 'core': core})
    for u in sequence:
        if u not in skeleton:
            continue
        keep = Counter()
        for v in children[u]:
            keep[owner[v]] += index.tensors[index.outputs[v][0]]['size']
        # Heavy sources may themselves exceed the packet threshold. Assign
        # them directly, then attach a parent to an existing child core.
        eligible = sorted(keep) if keep else range(cores)
        core = min(eligible, key=lambda c: (-keep[c], load[c], c))
        owner[u] = core
        load[core] += index.duration(u)
    sequences = [[] for _ in range(cores)]
    for u in sequence:
        sequences[owner[u]].append(u)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
    derive_multicore_plan(index.graph, plan)
    cuts = []
    for u in sequence:
        for v in children[u]:
            if owner[u] != owner[v]:
                tid = index.outputs[v][0]
                cuts.append({'source_op': v, 'target_op': u, 'tensor': tid,
                             'bytes': index.tensors[tid]['size'],
                             'source_core': owner[v], 'target_core': owner[u]})
    external = [t for t, cs in index.consumers.items() if cs and not index.producers[t]]
    unique_input = sum(index.tensors[t]['size'] for t in external)
    input_copies = sum(index.tensors[t]['size'] * len({owner[u] for u in index.consumers[t]})
                       for t in external)
    output_bytes = index.tensors[index.outputs[root][0]]['size']
    cross_bytes = 2 * sum(c['bytes'] for c in cuts)
    return plan, {
        'selected_strategy': 'tree_frontier', 'cores': cores, 'eligible_ops': len(index.ops),
        'components': 1, 'sink': root, 'sources': sum(not index.pred[u] for u in sequence),
        'capacity_bytes': dict(capacity), 'private_profile': profile,
        'packet_threshold_rational_cycles': [work[root], denominator],
        'packet_count': len(packets), 'skeleton_ops': len(skeleton), 'packets': packet_records,
        'compute_load_by_core': load, 'active_cores': sum(bool(s) for s in sequences),
        'per_core': _priority_peaks(index, sequences), 'cut_edges': cuts,
        'tensor_copy_bytes_without_spill': {
            'external_input_bytes': input_copies, 'cross_core_bytes': cross_bytes,
            'output_bytes': output_bytes, 'extra_vs_unique_input_output': input_copies - unique_input + cross_bytes},
        'zero_spill_claim': False,
        'limitations': [
            'LPT uses total compute work, not exact multi-pipe execution time',
            'capacity-normalized scalar ordering does not optimize each pool jointly',
            'shared graph inputs excluded from private profile and counted in per-core intervals',
            'raw intervals exclude inserted COPY timing, Step2 spill and Step3 reorder',
            'global postorder projection proves original-order acyclicity, not complete E0 feasibility',
            'skeleton locality rule and packet threshold do not guarantee balanced core loads'],
    }


def main():
    """Matrix direct-solver CLI: exactly one construction, no evaluator calls."""
    import argparse
    from datetime import datetime, timezone
    import hashlib
    import json
    from pathlib import Path
    import time
    from .baseline import ROOT
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config

    def dump(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT/'data/raw/a/official/data/config.txt')
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--wall', type=float, default=240)
    args = parser.parse_args()
    started = time.perf_counter()
    args.evidence.mkdir(parents=True, exist_ok=False)
    ledger = {'status': 'running', 'calls': {'E0': 0, 'E1': 0, 'E2': 0}, 'attempts': [],
              'started_at': datetime.now(timezone.utc).isoformat(),
              'validation_scope': 'official derive structure only; raw priority intervals, not E0'}
    try:
        graph = json.loads(args.graph.read_text())
        config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
        plan, detail = build(graph, args.cores, config)
        folder = args.evidence/'tree_frontier'
        folder.mkdir()
        dump(folder/'plan.json', plan)
        raw = (folder/'plan.json').read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        ledger['attempts'].append({'name': 'tree_frontier', 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter() - started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(raw)
        ledger.update(status='ok', selected='tree_frontier', plan_sha256=digest,
                      stop_reason='single_structural_construction_completed')
    except Exception as error:
        ledger.update(status='failed', error=repr(error))
    finally:
        ledger.update(finished_at=datetime.now(timezone.utc).isoformat(),
                      internal_wall_seconds=time.perf_counter()-started)
        dump(args.evidence/'solver.json', ledger)
    print(json.dumps({'status': ledger['status'], 'calls': ledger['calls'],
                      'internal_wall_seconds': ledger['internal_wall_seconds']}))
    if ledger['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
