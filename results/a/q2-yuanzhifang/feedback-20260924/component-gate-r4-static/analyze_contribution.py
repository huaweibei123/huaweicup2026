"""Group saved paired results by recorded construction route; no new scoring."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / 'results/a/q2-yuanzhifang/feedback-20260924'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pair_path = BASE / 'component-gate-r4-static/vs-c665.json'
    coverage_path = BASE / 'full-coverage/all500/coverage.json'
    pair_raw, coverage_raw = pair_path.read_bytes(), coverage_path.read_bytes()
    report, coverage = json.loads(pair_raw), json.loads(coverage_raw)
    paired = report['comparisons']['all500']
    assert paired['coverage_sha256'] == digest(coverage_raw)
    assert paired['own_solver_commit'] == coverage['solver_commit']
    rows = {(r['case_id'], r['cores']): r for r in coverage['rows']}
    pairs = {(r['case'], r['cores']): r for r in paired['pairs']}
    assert len(rows) == len(pairs) == 500 and rows.keys() == pairs.keys()
    by_route, by_core = defaultdict(Counter), defaultdict(Counter)
    wins, stdout_manifest = [], []
    for key in sorted(pairs):
        pair, row = pairs[key], rows[key]
        assert pair['own_result_sha256'] == row['result_sha256']
        assert pair['own_makespan'] == row['makespan_cycles']
        assert pair['delta'] == pair['own_makespan'] - pair['captain_makespan']
        stdout_path = ROOT / Path(row['run_path']).parent / 'solver.stdout.txt'
        stdout_raw = stdout_path.read_bytes()
        metadata = json.loads(stdout_raw.decode('utf-8-sig'))
        route = metadata.get('selected', 'missing')
        outcome = 'better' if pair['delta'] < 0 else 'equal' if pair['delta'] == 0 else 'worse'
        by_route[route][outcome] += 1
        by_core[key[1]][outcome] += 1
        stdout_manifest.append([key[0], key[1], stdout_path.relative_to(ROOT).as_posix(), digest(stdout_raw)])
        if outcome == 'better':
            wins.append({**pair, 'selected': route,
                         'split_components': metadata.get('split_components'),
                         'spill_bytes': row['spill_bytes'],
                         'makespan_reduction_fraction': -pair['delta'] / pair['captain_makespan']})
    counts = Counter()
    for values in by_route.values():
        counts.update(values)
    assert dict(counts) == paired['counts']
    result = {
        'scope': 'Post-hoc descriptive grouping of saved scores and solver stdout. No causal claim, new solver score, case-ID selection rule, or independent captain raw audit.',
        'new_solver_calls': 0, 'new_E0_calls': 0,
        'captain_solver_commit': report['captain_solver_commit'],
        'own_solver_commit': coverage['solver_commit'],
        'inputs': {pair_path.relative_to(ROOT).as_posix(): digest(pair_raw),
                   coverage_path.relative_to(ROOT).as_posix(): digest(coverage_raw)},
        'script_sha256': digest(Path(__file__).read_bytes()),
        'stdout_manifest_sha256': digest(json.dumps(stdout_manifest, ensure_ascii=False, separators=(',', ':')).encode()),
        'cells': len(rows), 'counts': counts,
        'counts_by_route': dict(by_route), 'counts_by_core': dict(by_core),
        'winning_unique_graphs': len({r['case'] for r in wins}),
        'wins_with_recorded_no_split': sum(r['split_components'] == 0 for r in wins),
        'wins_with_unknown_split_count': sum(r['split_components'] is None for r in wins),
        'wins_with_zero_spill': sum(r['spill_bytes'] == 0 for r in wins),
        'win_reduction_median': statistics.median(r['makespan_reduction_fraction'] for r in wins),
        'win_reduction_max': max(r['makespan_reduction_fraction'] for r in wins),
        'wins': wins,
    }
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('wins', 'inputs')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
