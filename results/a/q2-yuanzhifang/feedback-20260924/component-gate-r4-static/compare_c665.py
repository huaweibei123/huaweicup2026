"""Read-only paired diagnostic; no plans constructed, scored or combined."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
COMMIT = '1c00079aadbd071de62db17686d5ba3fed1da0f2'
SUMMARY = 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = subprocess.check_output(['git', 'show', f'{COMMIT}:{SUMMARY}'], cwd=ROOT)
    captain = json.loads(raw)
    assert captain['status'] == 'completed' and captain['accepted_cells'] == 500
    cap = {(r['case'], r['cores']): r for r in captain['rows']}
    assert len(cap) == 500
    reports = {}
    base = ROOT / 'results/a/q2-yuanzhifang/feedback-20260924/full-coverage'
    for name in ('all500', 'gap-full500', 'frontier-k5-100'):
        coverage_path = base / name / 'coverage.json'
        coverage = json.loads(coverage_path.read_bytes())
        paired, counts = [], {'better': 0, 'equal': 0, 'worse': 0}
        for row in coverage['rows']:
            key = (row['case_id'], row['cores'])
            c = cap[key]
            run = json.loads((ROOT / row['run_path']).read_bytes())
            assert c['status'] == 'accepted' and run['status'] == 'ok'
            assert run['identity']['graph_sha256'] == c['graph_sha256']
            assert run['identity']['config_sha256'] == c['config_sha256']
            delta = row['makespan_cycles'] - c['official']['makespan']
            counts['better' if delta < 0 else 'equal' if delta == 0 else 'worse'] += 1
            paired.append({'case': key[0], 'cores': key[1],
                           'own_makespan': row['makespan_cycles'],
                           'captain_makespan': c['official']['makespan'], 'delta': delta,
                           'own_result_sha256': row['result_sha256'],
                           'captain_result_sha256_from_summary': c['official']['result_sha256']})
        reports[name] = {'own_solver_commit': coverage['solver_commit'],
                         'coverage_sha256': hashlib.sha256(coverage_path.read_bytes()).hexdigest(),
                         'cells': len(paired), 'counts': counts, 'pairs': paired}
    result = {'captain_summary_commit': COMMIT, 'captain_summary_path': SUMMARY,
              'captain_summary_sha256': hashlib.sha256(raw).hexdigest(),
              'captain_solver_commit': captain['solver_commit'],
              'scope': 'Saved-report comparison with matching graph/config hashes. Captain raw E0 artifacts not independently re-audited here; no cross-platform time claim, no new algorithm mean, no winner mixing.',
              'new_solver_calls': 0, 'new_E0_calls': 0, 'comparisons': reports}
    with args.output.open('x', encoding='utf-8', newline='\n') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({k: v['counts'] for k, v in reports.items()}))


if __name__ == '__main__':
    main()
