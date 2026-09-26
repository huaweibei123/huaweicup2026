"""Recompute paper tables from frozen saved results; never construct or score plans."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OWN_COMMIT = '178a3673bd238b20772211427b8134b6db35f5af'
CAPTAIN_COMMIT = '1c00079aadbd071de62db17686d5ba3fed1da0f2'
SOLVER_COMMIT = 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'
BASE = 'results/a/q2-yuanzhifang/feedback-20260924/full-coverage'
CAPTAIN = 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925'
OUTPUT = Path(__file__).with_name('evidence.json')
CONFIG_SHA = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    inputs = []

    def frozen(commit, path):
        raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
        inputs.append({'commit': commit, 'path': path, 'sha256': digest(raw)})
        return raw

    saved = {}
    for name in ('all500', 'gap-full500', 'frontier-k5-100'):
        raw = frozen(OWN_COMMIT, f'{BASE}/{name}/per-cell.csv')
        rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        expected = {(f'{n:03}', k) for n in range(1, 101)
                    for k in ([5] if name == 'frontier-k5-100' else range(1, 6))}
        keys = {(r['case_id'], int(r['cores'])) for r in rows}
        assert keys == expected and len(keys) == len(rows), name
        saved[name] = {(r['case_id'], int(r['cores'])): r for r in rows}

    denominators = {}
    for (case, _), row in saved['all500'].items():
        b = int(row['baseline_cycles'])
        assert b > 0 and denominators.get(case, b) == b
        denominators[case] = b
    for rows in saved.values():
        for (case, _), row in rows.items():
            assert int(row['baseline_cycles']) == denominators[case]
            assert abs(float(row['speedup']) - denominators[case] / int(row['makespan_cycles'])) < 1e-12

    report = json.loads(frozen(CAPTAIN_COMMIT, f'{CAPTAIN}/report.json'))
    terminal = json.loads(frozen(CAPTAIN_COMMIT, f'{CAPTAIN}/completed-summary.json'))
    assert terminal['status'] == 'completed' and terminal['accepted_cells'] == 500
    assert terminal['solver_commit'] == SOLVER_COMMIT
    assert not terminal['in_flight'] and terminal['call_count_complete']
    cap = {(r['case'], r['cores']): r for r in terminal['rows']}
    assert set(cap) == set(saved['all500']) and len(terminal['rows']) == 500
    assert digest((ROOT / 'data/raw/a/official/data/config.txt').read_bytes()) == CONFIG_SHA
    graph_hashes = {case: digest((ROOT / f'data/raw/a/official/data/case_{case}.json').read_bytes())
                    for case in denominators}
    for (case, _), row in cap.items():
        assert row['status'] == 'accepted' and not row['request_in_flight']
        assert row['graph_sha256'] == graph_hashes[case]
        assert row['config_sha256'] == CONFIG_SHA
        assert row['solver_process']['status'] == row['e0_process']['status'] == 'ok'

    def compare(left, right):
        return [sum(a < b for a, b in zip(left, right)),
                sum(a == b for a, b in zip(left, right)),
                sum(a > b for a, b in zip(left, right))]

    table = []
    for k in range(1, 6):
        keys = [(f'{n:03}', k) for n in range(1, 101)]
        row = {'cores': k, 'n': 100}
        for label, source in saved.items():
            if all(key in source for key in keys):
                row[label] = {
                    'mean_speedup': statistics.fmean(denominators[c] / int(source[c, k]['makespan_cycles']) for c, k in keys),
                    'total_added_copy_bytes': sum(int(source[key]['extra_ddr_bytes']) for key in keys),
                    'total_spill_bytes': sum(int(source[key]['spill_bytes']) for key in keys),
                }
            else:
                row[label] = None  # No missing measurement is filled with 0 or 1.
        means = statistics.fmean(denominators[c] / cap[c, k]['official']['makespan'] for c, k in keys)
        assert abs(means - report['core_comparison'][str(k)]['new_mean_B_over_M']) < 1e-12
        new = [cap[key]['official']['makespan'] for key in keys]
        previous = [cap[key]['baseline']['makespan'] for key in keys]
        wtl = compare(new, previous)
        assert wtl == report['core_comparison'][str(k)]['wins_ties_losses']
        row['hypergap'] = {
            'mean_speedup': means,
            'total_added_copy_bytes': sum(cap[key]['official']['movement']['added_copy_bytes'] for key in keys),
            'total_spill_bytes': sum(cap[key]['official']['movement']['spill_added_copy_bytes'] for key in keys),
            'vs_previous_wins_ties_losses': wtl,
            'previous_mean_speedup': report['core_comparison'][str(k)]['old_mean_B_over_M'],
            'within_5pct_count_from_published_bound_audit': report['core_comparison'][str(k)]['certified_within_5pct_of_optimum_count'],
        }
        row['gap_vs_tensor_wins_ties_losses'] = compare(
            [int(saved['gap-full500'][key]['makespan_cycles']) for key in keys],
            [int(saved['all500'][key]['makespan_cycles']) for key in keys])
        table.append(row)
    cost = {}
    for label, key in [('solver', 'solver_process'), ('external_E0', 'e0_process')]:
        values = sorted(row[key]['wall_seconds'] for row in cap.values())
        cost[label] = {'n': len(values), 'mean_seconds': statistics.fmean(values),
                       'p95_nearest_rank_seconds': values[474], 'max_seconds': values[-1]}
    total_wtl = [sum(row['hypergap']['vs_previous_wins_ties_losses'][i] for row in table) for i in range(3)]
    output = {
        'purpose': 'Read-only chapter table reconstruction from saved official-result summaries; not a new benchmark.',
        'sources': inputs, 'config_sha256': CONFIG_SHA,
        'graph_sha256': graph_hashes, 'denominator_definition': 'fixed official A single-core baseline per graph',
        'coverage': {'tensor_packet': 500, 'gap_packet': 500, 'hypergap': 500, 'F1_k5': 100},
        'core_table': table, 'hypergap_vs_previous_wins_ties_losses': total_wtl,
        'hypergap_cost': cost, 'published_hypergap_calls': terminal['calls'],
        'published_hypergap_batch_wall_seconds': terminal['total_wall_seconds'],
        'validation_scope': 'Recomputed means, comparisons and timing quantiles from frozen saved summaries/CSVs; checked 500 unique coordinates, local graph/config identity, denominator consistency and accepted states. Captain raw 500 plan/result/receipt byte audits were published by their owner and are not independently repeated here.',
        'new_calls': {'solver': 0, 'Step2': 0, 'Step3': 0, 'E0': 0, 'E1': 0, 'E2': 0},
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': OUTPUT.relative_to(ROOT).as_posix(), 'sha256': digest(OUTPUT.read_bytes()),
                      'coverage': output['coverage'], 'paired_counts': total_wtl,
                      'means': {r['cores']: r['hypergap']['mean_speedup'] for r in table},
                      'new_calls': output['new_calls']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
