"""Compare frozen static bounds with a saved central-board projection.

No solver, compiler, evaluator, network, or plan selection is performed here.
The projection's central admission is not a new independent E0 execution.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import statistics


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def compare(current, prior, board, official_sha256):
    if current['input_identity'] != prior['input_identity']:
        raise ValueError('Input archive identity changed')
    for name in ('config_sha256', 'official_source_sha256'):
        if current['code_identity'][name] != prior['code_identity'][name]:
            raise ValueError(f'Frozen semantic identity changed: {name}')
    old = {(c['input_member'], b['cores']): (c['input_sha256'], b['lower_bound_cycles'])
           for c in prior['cases'] for b in c['bounds']}
    new = {(c['input_member'], b['cores']): (c['input_sha256'], b['lower_bound_cycles'])
           for c in current['cases'] for b in c['bounds']}
    if old.keys() != new.keys():
        raise ValueError('Bound coverage changed')
    changed = []
    for key, (graph_sha, bound) in new.items():
        if graph_sha != old[key][0] or bound < old[key][1]:
            raise ValueError(f'Changed input or weaker bound: {key}')
        if bound > old[key][1]:
            changed.append({'case_id': key[0], 'cores': key[1],
                            'old_bound': old[key][1], 'new_bound': bound})
    rows = []
    seen = set()
    for cell in board['cells']:
        best = cell['best']
        if cell['problem'] != 'P1' or best is None:
            continue
        key = (f"data/case_{cell['case_id']}.json", cell['cores'])
        if key in seen:
            raise ValueError('Duplicate board cell')
        seen.add(key)
        graph_sha, lower = new[key]
        if (not best['eligible'] or not best['baseline_verified']
                or best['evaluator']['route'] != 'E0'
                or best['identity']['official_sha256'] != official_sha256
                or best['identity']['graph_sha256'] != graph_sha
                or best['identity']['config_sha256'] != current['code_identity']['config_sha256']):
            raise ValueError(f'Board provenance mismatch: {key}')
        upper = best['metrics']['makespan_cycles']
        if lower > upper:
            raise ValueError(f'Lower bound exceeds accepted E0 value: {key}')
        rows.append({'case_id': cell['case_id'], 'cores': cell['cores'],
                     'lower_bound': lower, 'accepted_E0_cycles': upper,
                     'upper_to_lower_ratio': upper / lower,
                     'maximum_fractional_reduction': 1 - lower / upper,
                     'baseline_speedup': best['metrics']['baseline_speedup'],
                     'record_id': best['id'], 'algorithm_id': best['algorithm_id'],
                     'identity': best['identity']})
    if seen != new.keys():
        raise ValueError('Need the same complete board and bounds cell set')
    return {
        'kind': 'static_bound_feedback_NOT_new_performance',
        'calls': {'solver': 0, 'E0': 0, 'E1': 0, 'E2': 0},
        'board_as_of': board['as_of'], 'board_cursor': board['cursor'],
        'scope': 'Historical best combination; central-admitted E0 records, not independent reruns. Equality is under the stated frozen resource/causality semantics, not full numerical-program formal verification.',
        'improved_bound_cells': len(changed), 'changed': changed,
        'official_identity_counts': dict(Counter(r['identity']['official_sha256'] for r in rows)),
        'per_core': [
            {'cores': k, 'n': sum(r['cores'] == k for r in rows),
             'historical_best_mean_speedup': statistics.mean(r['baseline_speedup'] for r in rows if r['cores'] == k),
             'equal_bound_cases': [r['case_id'] for r in rows if r['cores'] == k and r['lower_bound'] == r['accepted_E0_cycles']]}
            for k in sorted(current['core_counts'])],
        'rows': rows,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bounds', type=Path, required=True)
    p.add_argument('--prior', type=Path, required=True)
    p.add_argument('--board', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--official-sha256', required=True)
    args = p.parse_args()
    report = compare(read(args.bounds), read(args.prior), read(args.board), args.official_sha256)
    report['input_hashes'] = {name: {'path': str(getattr(args, name)), 'sha256': hashlib.sha256(getattr(args, name).read_bytes()).hexdigest()}
                             for name in ('bounds', 'prior', 'board')}
    report['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({k: report[k] for k in ('improved_bound_cells', 'per_core', 'calls')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
