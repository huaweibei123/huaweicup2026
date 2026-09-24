"""One guarded tree candidate: complete packets before remote skeleton joins.

Reuses the frozen tree_frontier pieces and ownership without changing its code.
Changes priority order once; no scores, search, parameter grid or fallback.
"""
from __future__ import annotations

from collections import defaultdict
import heapq

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from . import tree_frontier


def _fifo_bound(index, sequences):
    """Exact longest path of retained compute edges plus fixed compute FIFOs.

    Valid as a candidate lower bound only after tree_frontier's explicit tensor
    guard; omits COPY, shared DDR, spill and memory-reuse dependencies.
    """
    predecessors = {u: set(index.pred[u]) for u in index.ops}
    seen = set()
    for seq in sequences:
        previous = {}
        for u in seq:
            if u in seen or u not in index.ops:
                raise ValueError('compute coverage is not a partition')
            seen.add(u)
            pipe = index.ops[u]['pipe']
            if pipe in previous:
                predecessors[u].add(previous[pipe])
            previous[pipe] = u
    if seen != set(index.ops):
        raise ValueError('incomplete compute coverage')
    successors = defaultdict(list)
    degree = {u: len(ps) for u, ps in predecessors.items()}
    for u, ps in predecessors.items():
        for p in ps:
            successors[p].append(u)
    ready = [u for u in index.ops if not degree[u]]
    heapq.heapify(ready)
    finish = {u: index.duration(u) for u in index.ops}
    count = 0
    while ready:
        u = heapq.heappop(ready)
        count += 1
        for v in successors[u]:
            finish[v] = max(finish[v], finish[u] + index.duration(v))
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, v)
    if count != len(index.ops):
        raise ValueError('original dependencies plus compute FIFO contain a cycle')
    return max(finish.values(), default=0)


def _closed_packet_members(index, packets, owner):
    """Verify disjoint complete subtrees and retain original packet ownership."""
    membership = {}
    for packet in packets:
        members, stack = set(), [packet['root']]
        while stack:
            u = stack.pop()
            if u in members:
                continue
            members.add(u)
            stack.extend(index.pred[u])
        if len(members) != packet['ops']:
            raise UnsupportedStructure('packet metadata does not describe a complete subtree')
        if sum(index.duration(u) for u in members) != packet['work_cycles']:
            raise UnsupportedStructure('packet work metadata differs from original graph')
        for u in members:
            if u in membership:
                raise UnsupportedStructure('complete packet subtrees overlap')
            if owner[u] != packet['core']:
                raise UnsupportedStructure('packet crosses its declared owner')
            if not index.pred[u].issubset(members):
                raise UnsupportedStructure('packet has an external compute predecessor')
            membership[u] = packet['root']
    return membership


def build(graph, cores, config):
    return build_from_index(DAGIndex(graph), cores, config)


def build_from_index(index, cores, config):
    # Exactly one base construction, not an online alternative comparison.
    base_plan, base_detail = tree_frontier.build_from_index(index, cores, config)
    reverse = {sg: int(u) for u, sg in base_plan['node_to_subgraph'].items()}
    before = [[reverse[sg] for sg in seq] for seq in base_plan['core_schedules']]
    owner = {u: c for c, seq in enumerate(before) for u in seq}
    membership = _closed_packet_members(index, base_detail['packets'], owner)
    skeleton = set(index.ops) - set(membership)
    if len(skeleton) != base_detail['skeleton_ops']:
        raise UnsupportedStructure('packet/skeleton coverage does not match base construction')
    after = [[u for u in seq if u in membership] + [u for u in seq if u in skeleton]
             for seq in before]
    old_bound = _fifo_bound(index, before)
    new_bound = _fifo_bound(index, after)
    # Ownership and singleton IDs remain byte-for-byte identical; only the
    # per-core order changes. Original packet work and COPY byte counts survive.
    mapping = base_plan['node_to_subgraph']
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in after]}
    derive_multicore_plan(index.graph, plan)
    per_core = tree_frontier._priority_peaks(index, after)
    for c, row in enumerate(per_core):
        local_packets = [p for p in base_detail['packets'] if p['core'] == c]
        reserve = dict.fromkeys(tree_frontier.POOLS, 0)
        for p in local_packets:
            tensor = index.tensors[index.outputs[p['root']][0]]
            reserve[tree_frontier._pool(tensor)] += tensor['size']
        row.update(packet_root_reserve_bytes=reserve,
                   raw_peaks_fit_capacity=all(row['raw_priority_peak_bytes'][p] <= config['capacity'][p]
                                              for p in tree_frontier.POOLS))
    detail = {key: base_detail[key] for key in [
        'cores', 'eligible_ops', 'components', 'sink', 'sources', 'capacity_bytes',
        'packet_threshold_rational_cycles', 'packet_count', 'skeleton_ops', 'packets',
        'compute_load_by_core', 'active_cores', 'cut_edges', 'tensor_copy_bytes_without_spill']}
    detail.update(selected_strategy='tree_packets_first',
                  priority_rule='all closed packets first, then original topological skeleton subsequence',
                  index_constructions=1, base_construct_calls=1,
                  unchanged_ownership=True, per_core=per_core,
                  changed_core_orders=sum(a != b for a, b in zip(before, after)),
                  fixed_compute_fifo_bound_before=old_bound,
                  fixed_compute_fifo_bound_after=new_bound,
                  bound_scope='candidate-specific compute dependency plus pipe FIFO; not a predicted Makespan',
                  zero_spill_claim=False,
                  limitations=[
                      'whole packets and their original internal word/ownership are unchanged',
                      'deferring skeleton can retain more packet-root tensors',
                      'raw priority peaks omit COPY allocation timing and Step2/Step3 execution',
                      'a smaller compute FIFO lower bound does not prove faster official execution',
                      'no balance or optimality guarantee and no fallback for unsupported graphs'])
    return plan, detail


def main():
    """Direct matrix CLI; exactly one deterministic structural candidate."""
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
              'validation_scope': 'structure, guarded compute-FIFO lower bounds and raw priority intervals only'}
    try:
        graph = json.loads(args.graph.read_text())
        config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
        plan, detail = build(graph, args.cores, config)
        folder = args.evidence/'tree_packets_first'
        folder.mkdir()
        dump(folder/'plan.json', plan)
        raw = (folder/'plan.json').read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        ledger['attempts'].append({'name': 'tree_packets_first', 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter() - started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(raw)
        ledger.update(status='ok', selected='tree_packets_first', plan_sha256=digest,
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
