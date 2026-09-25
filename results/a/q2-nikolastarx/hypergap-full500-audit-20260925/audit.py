#!/usr/bin/env python3
"""Read-only paired audit; partial validation helpers never declare full scores."""
import argparse
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

SOLVER = 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'
RUNNER = 'ff47cbca4a953602dec7e4b959bbb10a016eca9a'
BASE = '60afc38b327680fbda0ff10182e3e05a01edd72d'
FEED = 'results/a/q2-nikolastarx/active-core-full500-20260925-s59/20260924T1910Z-s59ee/board-feed-500-with-runtime-notes.json'
FEED_SHA = '0b850686966d1d7c1ce1a8babb1655051756b42f9a59d5c6f6becd6a87f2f99c'
MANIFEST = 'results/a/q2-nikolastarx/hypergap-full500-20260925/manifest-workers1.json'
GRID = {(f'{i:03d}', k) for i in range(1, 101) for k in range(1, 6)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


@lru_cache(maxsize=1024)
def git_blob(repo, commit, path):
    return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=repo)


def pinned_records(repo):
    raw = git_blob(repo, BASE, FEED)
    require(sha(raw) == FEED_SHA, 'pinned previous feed differs')
    records = decode(raw)['records']
    table = {(r['case_id'], r['cores']): r for r in records}
    require(len(records) == 500 and set(table) == GRID, 'previous grid differs')
    return table


def necessary_bounds(repo, old):
    raw = (repo / 'results/a/q2-nikolastarx/goal-20260924/global-bounds.json').read_bytes()
    certificate = decode(raw)
    require(sha((repo / 'src/q2_nikolastarx/global_bounds.py').read_bytes()) ==
            certificate['certificate_source_sha256'], 'bound implementation identity differs')
    for name, expected in certificate['official_source_sha256'].items():
        require(sha((repo / 'data/raw/a/official/code' / name).read_bytes()) == expected,
                'bound official source differs: ' + name)
    table = {}
    for graph in certificate['records']:
        case = graph['graph_file'].removeprefix('case_').removesuffix('.json')
        require(graph['supported'] and graph['precedence_supported'] and
                graph['graph_sha256'] == old[(case, 1)]['identity']['graph_sha256'],
                'bound graph identity/domain differs')
        for bound in graph['by_core_count']:
            key = (case, bound['cores']); value = bound['makespan_lower_bound_cycles']
            require(key not in table and type(value) is int and value > 0, 'invalid bound')
            table[key] = value
    require(set(table) == GRID, 'bound grid differs')
    return table, sha(raw)


def artifact(repo, ref):
    path = (repo / ref['path']).resolve()
    require(path.is_relative_to(repo), 'artifact outside repo')
    raw = path.read_bytes()
    require(sha(raw) == ref['sha256'], 'artifact hash mismatch: ' + ref['path'])
    return raw, decode(raw)


def collect_feeds(repo, root, summary, *, require_full=True):
    manifest_raw = git_blob(repo, RUNNER, MANIFEST)
    manifest = decode(manifest_raw)
    require(summary['manifest_sha256'] == sha(manifest_raw), 'manifest hash differs')
    require(summary['limits'] == manifest['limits'], 'runtime limits differ')
    require(summary['solver_commit'] == SOLVER and summary['runner_commit'] == RUNNER,
            'runtime source differs')
    expected = {'global_budget': manifest['limits'], 'candidate_limit': 3,
                'selection': 'strict_lexicographic_makespan_added_copy_bytes', 'retry': False}
    table, run_ids = {}, set()
    for lo in range(1, 101, 10):
        group = root / f'cases-{lo:03d}-{lo+9:03d}'
        if not group.exists() and not require_full:
            continue
        feed = decode((group / 'board-feed.json').read_bytes())
        snapshot = decode((group / 'snapshot.json').read_bytes())
        require(snapshot['manifest_sha256'] == sha(manifest_raw), 'snapshot manifest differs')
        records = feed['records']
        require(len(records) == 50, 'case group must have 50 records')
        group_grid = {(f'{c:03d}', k) for c in range(lo, lo+10) for k in range(1, 6)}
        seen = set()
        for r in records:
            key = (r['case_id'], r['cores'])
            require(key in group_grid and key not in table, 'duplicate or unexpected coordinate')
            require(r['problem'] == 'P2' and r['status'] == 'ok' and r['solver_commit'] == SOLVER
                    and r['algorithm_id'] == 'q2-adaptive-hypergap-guarded'
                    and r['parameters'] == expected
                    and r['provenance']['runner']['source']['commit'] == RUNNER
                    and r['run_id'] == snapshot['run_id'], 'mixed algorithm/run/budget')
            run_ids.add(r['run_id']); seen.add(key); table[key] = r
        require(seen == group_grid, 'case group coverage differs')
    require(len(run_ids) == 1, 'must have one run ID')
    if require_full:
        require(set(table) == GRID, 'feeds do not cover 500 unique cells')
    return table, next(iter(run_ids))


def validate_cell(repo, row, record, previous, summary):
    key = (row['case'], row['cores'])
    require(row['status'] == 'accepted' and not row.get('request_in_flight'), 'unaccepted cell')
    plan_blob, plan = artifact(repo, record['artifacts']['plan'])
    result_blob, result = artifact(repo, record['artifacts']['result'])
    _, run = artifact(repo, record['artifacts']['run'])
    require(run['accepted_row'] == row, 'archive row differs from runtime summary')
    raw_plan = gzip.decompress(plan_blob) if plan_blob[:2] == b'\x1f\x8b' else plan_blob
    raw_result = gzip.decompress(result_blob) if result_blob[:2] == b'\x1f\x8b' else result_blob
    require(sha(raw_plan) == row['plan_sha256'] and sha(raw_result) == row['official']['result_sha256'],
            'original plan/result hash differs')
    evidence = {name: artifact(repo, ref)[1] for name, ref in run['archived_evidence'].items()}
    cell = evidence['cell_receipt']
    require({k: v for k, v in cell.items() if k not in
             ('solver_process_in_flight', 'independent_e0_in_flight')} == row, 'cell receipt differs')
    ledger = evidence['online_ledger']
    # Redaction changes receipt bytes. The archive hash and original identity are distinct.
    require(run['original_sha256']['online_ledger'] == row['solver_ledger_sha256'],
            'original ledger identity differs')
    require(ledger['status'] == 'ok' and ledger['solver_checkout_commit'] == RUNNER
            and not ledger['request_in_flight'] and not ledger['possible_E0_fallback_calls'],
            'ledger identity or uncertainty differs')
    calls = row['calls']
    require(ledger['calls']['E2_api_attempted'] == ledger['calls']['native_returns']
            == calls['E2_api_attempted'] == calls['native_returns'] == len(ledger['attempts'])
            and len(ledger['attempts']) <= 3 and not ledger['calls']['E0_fallback']
            and not calls['E0_fallback_confirmed'] and not calls['E0_fallback_possible']
            and calls['E0_independent_started'] == 1, 'call evidence differs')
    for name, compact in [('solver_process', row['solver_process']), ('e0_process', row['e0_process'])]:
        proc = evidence[name]
        require(proc['status'] == 'ok' and proc['exit_code'] == 0 and not proc['surviving_pids']
                and proc['wall_seconds'] == compact['wall_seconds'], 'process receipt differs')
    official = row['official']
    require(result['scene'] == 'B' and result['num_cores'] == key[1]
            and result['makespan'] == official['makespan'] == record['metrics']['makespan_cycles']
            and result['data_movement_bytes'] == official['movement']
            and result['cross_task_traffic'] == official['cross_task_traffic'], 'official metrics differ')
    ident = record['identity']
    require(record['baseline'] == previous['baseline']
            and ident['graph_sha256'] == row['graph_sha256'] == previous['identity']['graph_sha256']
            and ident['config_sha256'] == row['config_sha256'] == previous['identity']['config_sha256']
            and ident['official_sha256'] == previous['identity']['official_sha256']
            and ident['plan_sha256'] == sha(plan_blob), 'graph/config/official/plan identity differs')
    baseline = record['baseline']['result']
    baseline_blob = git_blob(repo, BASE, baseline['path'])
    require(sha(baseline_blob) == baseline['sha256'], 'official denominator artifact differs')
    old_ref = previous['artifacts']['plan']
    old_blob = git_blob(repo, BASE, old_ref['path'])
    require(sha(old_blob) == old_ref['sha256'], 'previous plan artifact differs')
    return {'case': key[0], 'cores': key[1], 'B': decode(baseline_blob)['makespan'],
            'new_M': result['makespan'], 'old_M': previous['metrics']['makespan_cycles'],
            'plan_changed': plan != decode(old_blob), 'E2': calls['E2_api_attempted'],
            'solver_wall': row['solver_process']['wall_seconds'],
            'external_E0_wall': row['e0_process']['wall_seconds']}


def stats(values):
    x = sorted(values)
    return {'n': len(x), 'mean': statistics.fmean(x),
            'p95_nearest_rank': x[math.ceil(.95*len(x))-1], 'max': x[-1]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--summary', type=Path, required=True)
    p.add_argument('--archive-root', type=Path, required=True)
    p.add_argument('--repo-root', type=Path, default=Path.cwd())
    a = p.parse_args(); repo = a.repo_root.resolve()
    sraw = a.summary.read_bytes(); summary = decode(sraw); rows = summary['rows']
    if (summary['status'] != 'completed' or summary['accepted_cells'] != 500
            or len(rows) != 500 or summary['in_flight'] or not summary['call_count_complete']
            or any(r['status'] != 'accepted' or r.get('request_in_flight') for r in rows)):
        print(json.dumps({'status': 'incomplete', 'accepted': summary['accepted_cells'],
                          'scores_computed': False})); return 2
    require({(r['case'], r['cores']) for r in rows} == GRID, 'summary grid differs')
    feeds, run_id = collect_feeds(repo, a.archive_root.resolve(), summary)
    old = pinned_records(repo)
    lower_bounds, bounds_sha = necessary_bounds(repo, old)
    values = [validate_cell(repo, row, feeds[(row['case'], row['cores'])],
                            old[(row['case'], row['cores'])], summary) for row in rows]
    for value in values:
        value['LB'] = lower_bounds[(value['case'], value['cores'])]
        require(value['new_M'] >= value['LB'], 'official result contradicts necessary bound')
    total_e2 = sum(v['E2'] for v in values); calls = summary['calls']
    require(calls['solver_started'] == calls['E0_independent_started'] == 500
            and calls['E2_api_attempted'] == calls['native_returns'] == total_e2
            and not calls['E0_fallback_confirmed'] and not calls['E0_fallback_possible'],
            'batch call accounting differs')
    comparison = {}
    for k in range(1, 6):
        v = [x for x in values if x['cores'] == k]
        comparison[str(k)] = {'n': len(v), 'new_mean_B_over_M': statistics.fmean(x['B']/x['new_M'] for x in v),
            'old_mean_B_over_M': statistics.fmean(x['B']/x['old_M'] for x in v),
            'relaxation_ceiling_mean_B_over_LB': statistics.fmean(x['B']/x['LB'] for x in v),
            'certified_within_5pct_of_optimum_count': sum(100*x['new_M'] <= 105*x['LB'] for x in v),
            'meets_lower_bound_exactly_count': sum(x['new_M'] == x['LB'] for x in v),
            'wins_ties_losses': [sum(x['new_M'] < x['old_M'] for x in v),
                                sum(x['new_M'] == x['old_M'] for x in v),
                                sum(x['new_M'] > x['old_M'] for x in v)]}
    print(json.dumps({'status': 'complete', 'cells': 500, 'run_id': run_id,
        'summary_sha256': sha(sraw), 'bounds_certificate_sha256': bounds_sha, 'solver_commit': SOLVER, 'runner_commit': RUNNER,
        'core_comparison': comparison,
        'cases_improved_makespan_any_core': len({x['case'] for x in values if x['new_M'] < x['old_M']}),
        'cases_with_plan_change_any_core': len({x['case'] for x in values if x['plan_changed']}),
        'solver_wall_seconds': stats([x['solver_wall'] for x in values]),
        'external_E0_wall_seconds': stats([x['external_E0_wall'] for x in values]),
        'calls': calls, 'peer_targets_reference_only': [2.26, 3.18, 3.96, 4.53],
        'limitations': 'No new evaluator calls. The necessary-bound ceiling may be unattainable; within-5pct counts rely on the stated source-checked bound proof. No global optimality or peer reproduction claim.'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
