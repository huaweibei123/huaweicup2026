"""Guarded same-core sibling leaf-chain weaving; one deterministic candidate.

All ownership, packets and packet-before-skeleton policy remain frozen. Only a
contiguous pair of homogeneous alternating M/V unary leaves and its join changes.
The ideal two-pipe formula is not an official runtime/optimality guarantee.
"""
from __future__ import annotations

from collections import Counter

from .dag_direct import DAGIndex
from .direct import derive_multicore_plan
from . import tree_frontier, tree_packets_first


def _detect_pairs(index, sequences, packets):
    """Inspect structure only; never construct or evaluate an alternative plan."""
    tree_frontier._guard(index)
    owner = {u: c for c, seq in enumerate(sequences) for u in seq}
    membership = tree_packets_first._closed_packet_members(index, packets, owner)
    position = {u: p for seq in sequences for p, u in enumerate(seq)}
    pairs, rejected = [], Counter()
    for join in index.order:
        if len(index.pred[join]) != 2:
            continue
        chains = []
        for child in sorted(index.pred[join]):
            chain = []
            u = child
            while True:
                if len(index.pred[u]) > 1:
                    break
                chain.append(u)
                if not index.pred[u]:
                    chains.append(list(reversed(chain)))
                    break
                u = next(iter(index.pred[u]))
        if len(chains) != 2:
            rejected['not_two_source_unary_chains'] += 1
            continue
        signature = [tuple((index.ops[u]['pipe'], index.duration(u)) for u in chain) for chain in chains]
        sig = signature[0]
        if signature[0] != signature[1]:
            rejected['different_chain_signatures'] += 1
            continue
        if (len(sig) < 4 or len(sig) % 2
                or any(pipe != ('PIPE_M' if i % 2 == 0 else 'PIPE_V')
                       for i, (pipe, _) in enumerate(sig))
                or index.ops[join]['pipe'] != 'PIPE_V'):
            rejected['not_repeated_MV_with_V_join'] += 1
            continue
        a, b = sig[0][1], sig[1][1]
        if any(duration != (a if i % 2 == 0 else b) for i, (_, duration) in enumerate(sig)) or b > a:
            rejected['not_constant_durations_with_b_le_a'] += 1
            continue
        nodes = chains[0] + chains[1] + [join]
        if len({owner[u] for u in nodes}) != 1:
            rejected['not_same_core'] += 1
            continue
        if join not in membership or any(membership.get(u) != membership[join] for u in nodes):
            rejected['not_inside_one_complete_packet'] += 1
            continue
        chains.sort(key=lambda chain: position[chain[0]])
        left, right = chains
        start = position[left[0]]
        if sequences[owner[join]][start:start+len(nodes)] != left + right + [join]:
            rejected['not_contiguous_closed_pair'] += 1
            continue
        pairs.append({'join': join, 'core': owner[join], 'packet': membership[join],
                      'left': left, 'right': right, 'start': start, 'stop': start+len(nodes),
                      'M_visits_per_chain': len(sig)//2, 'M_cycles': a, 'V_cycles': b,
                      'join_cycles': index.duration(join)})
    pairs.sort(key=lambda p: (p['core'], p['start']))
    for earlier, later in zip(pairs, pairs[1:]):
        if earlier['core'] == later['core'] and earlier['stop'] > later['start']:
            raise ValueError('guarded leaf pairs overlap')
    return pairs, dict(sorted(rejected.items()))


def build(graph, cores, config):
    return build_from_index(DAGIndex(graph), cores, config)


def build_from_index(index, cores, config):
    base_plan, base_detail = tree_packets_first.build_from_index(index, cores, config)
    reverse = {sg: int(u) for u, sg in base_plan['node_to_subgraph'].items()}
    before = [[reverse[sg] for sg in seq] for seq in base_plan['core_schedules']]
    pairs, rejected = _detect_pairs(index, before, base_detail['packets'])
    at = {(p['core'], p['start']): p for p in pairs}
    after = []
    for core, seq in enumerate(before):
        result, cursor = [], 0
        while cursor < len(seq):
            pair = at.get((core, cursor))
            if pair is None:
                result.append(seq[cursor]); cursor += 1
                continue
            for a, b in zip(pair['left'], pair['right']):
                result.extend([a, b])
            result.append(pair['join'])
            cursor = pair['stop']
        after.append(result)
    bound = tree_packets_first._fifo_bound(index, after)
    mapping = base_plan['node_to_subgraph']
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in after]}
    derive_multicore_plan(index.graph, plan)
    per_core = tree_frontier._priority_peaks(index, after)
    for c, row in enumerate(per_core):
        row.update(packet_root_reserve_bytes=base_detail['per_core'][c]['packet_root_reserve_bytes'],
                   raw_peaks_fit_capacity=all(row['raw_priority_peak_bytes'][p] <= config['capacity'][p]
                                              for p in tree_frontier.POOLS))
    detail = {key: base_detail[key] for key in [
        'cores', 'eligible_ops', 'components', 'sink', 'sources', 'capacity_bytes',
        'packet_threshold_rational_cycles', 'packet_count', 'skeleton_ops', 'packets',
        'compute_load_by_core', 'active_cores', 'cut_edges', 'tensor_copy_bytes_without_spill']}
    detail.update(selected_strategy='tree_paired_leaves', priority_rule='MA_i,MB_i,VA_i,VB_i for each layer; then V join',
                  index_constructions=1, base_construct_calls=1, unchanged_ownership=True,
                  unchanged_packet_and_skeleton_policy=True, per_core=per_core,
                  paired_leaf_chains=2*len(pairs), pairs=pairs, rejected_binary_joins=rejected,
                  covered_compute_ops=sum(len(p['left'])+len(p['right']) for p in pairs),
                  covered_M_work=sum(2*p['M_visits_per_chain']*p['M_cycles'] for p in pairs),
                  fixed_compute_fifo_bound_before=base_detail['fixed_compute_fifo_bound_after'],
                  fixed_compute_fifo_bound_after=bound, zero_spill_claim=False,
                  ideal_pair_scope='two independent chains with all inputs ready, no COPY/capacity/shared DDR, dedicated M/V',
                  ideal_pair_finish_formula='2*r*a+b+join_cycles, for r>=2 and 0<b<=a',
                  limitations=[
                      'only contiguous same-core leaf pairs inside one existing complete packet are changed',
                      'unmatched chains and all skeleton nodes retain the prior order',
                      'ideal formula is local; global official time includes COPY and memory dependencies',
                      'raw priority peaks include graph inputs but not every transformed runtime lifetime',
                      'smaller FIFO lower bounds are not a proof of official performance improvement'])
    return plan, detail


def main():
    """Direct matrix CLI, one candidate and zero online evaluator calls."""
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
              'validation_scope': 'guarded structure, compute-FIFO lower bounds and raw intervals only'}
    try:
        graph = json.loads(args.graph.read_text())
        config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
        plan, detail = build(graph, args.cores, config)
        folder = args.evidence/'tree_paired_leaves'; folder.mkdir()
        dump(folder/'plan.json', plan)
        raw = (folder/'plan.json').read_bytes(); digest = hashlib.sha256(raw).hexdigest()
        ledger['attempts'].append({'name': 'tree_paired_leaves', 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter() - started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream: stream.write(raw)
        ledger.update(status='ok', selected='tree_paired_leaves', plan_sha256=digest,
                      stop_reason='single_structural_construction_completed')
    except Exception as error:
        ledger.update(status='failed', error=repr(error))
    finally:
        ledger.update(finished_at=datetime.now(timezone.utc).isoformat(),
                      internal_wall_seconds=time.perf_counter()-started)
        dump(args.evidence/'solver.json', ledger)
    print(json.dumps({'status': ledger['status'], 'calls': ledger['calls'],
                      'internal_wall_seconds': ledger['internal_wall_seconds']}))
    if ledger['status'] != 'ok': raise SystemExit(1)


if __name__ == '__main__': main()
