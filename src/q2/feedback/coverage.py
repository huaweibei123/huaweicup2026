"""Audit completed P2 batches and report full-100 means without selecting winners.

Never pass a live batch: Windows readers can prevent the runner's atomic rename.
This is post-processing only; no graph construction or evaluator is called.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def reference(path):
    return {'path': path.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def summarize(batches, solver_commit, variant='tensor_packet'):
    rows, incomplete, receipts = [], [], []
    keys, calls = set(), dict.fromkeys(('solver', 'E0', 'E1', 'E2'), 0)
    graph_identities = {}
    source_hashes = None
    fixed_args = None
    for batch in batches:
        ledger_path = batch / 'ledger.json'
        ledger, spec = read(ledger_path), read(batch / 'spec.json')
        if ledger['state'] == 'running':
            raise ValueError('refusing a live batch: ' + str(batch))
        if spec['solver_commit'] != solver_commit or len(spec['methods']) != 1:
            raise ValueError('single fixed algorithm source required')
        method = spec['methods'][0]
        if method['variant'] != variant:
            raise ValueError('batch variant differs from requested variant')
        if fixed_args is None:
            fixed_args = list(method['args'])
        elif fixed_args != method['args']:
            raise ValueError('method args differ across batches')
        hashes = {p: ledger['source_hashes'][p] for p in spec['source_paths']}
        if source_hashes is None:
            source_hashes = hashes
        elif source_hashes != hashes:
            raise ValueError('source bytes differ across batches')
        receipts.append({'ledger': reference(ledger_path), 'state': ledger['state'],
                         'started_at': ledger['started_at'], 'finished_at': ledger['finished_at'],
                         'batch_wall_seconds': ledger['batch_wall_seconds'],
                         'preparation_wall_seconds': ledger['preparation']['wall_seconds'],
                         'calls': ledger['charged_calls'], 'coordination': spec.get('coordination')})
        for name in calls:
            calls[name] += ledger['charged_calls'][name]
        for name in ledger['attempts']:
            path = ROOT / name
            run = read(path)
            if run['status'] != 'ok':
                incomplete.append({'run': reference(path), 'case_id': run['case_id'],
                                   'cores': run['cores'], 'stored_status': run['status'],
                                   'batch_state': ledger['state'], 'failure': run.get('failure'),
                                   'note': 'A running receipt in a stopped batch is incomplete, not an active process.'})
                continue
            key = (run['case_id'], run['cores'])
            if key in keys:
                raise ValueError('duplicate successful cell; refusing winner selection: ' + str(key))
            keys.add(key)
            if run['solver_commit'] != solver_commit or run['calls']['E0'] != 1:
                raise ValueError('unexpected source or external E0 count')
            if run['method']['variant'] != variant or run['method']['args'] != fixed_args:
                raise ValueError('run method differs from fixed batch method')
            if {p: run['source_hashes'][p] for p in spec['source_paths']} != hashes:
                raise ValueError('run source bytes differ from batch')
            if run['stages']['E0']['status'] != 'ok' or run['stages']['E0']['returncode'] != 0:
                raise ValueError('successful receipt lacks completed E0')
            identity = {k: run['identity'][k] for k in ('graph_sha256', 'config_sha256', 'official_sha256')}
            previous = graph_identities.setdefault(run['case_id'], identity)
            if previous != identity:
                raise ValueError('case identity changed across cores')
            base_path = ROOT / 'results/benchmark-board/official-singlecore-20260924' / run['case_id'] / 'run.json'
            baseline = read(base_path)
            for k, source in [('graph_sha256', 'graph_sha256'), ('config_sha256', 'config_sha256'),
                              ('official_sha256', 'official_code_hash')]:
                if identity[k] != baseline[source]:
                    raise ValueError('baseline identity mismatch')
            artifact = run['artifacts']['result']
            result_path = ROOT / artifact['path']
            if reference(result_path) != artifact:
                raise ValueError('stored official result hash mismatch')
            result = read(result_path)
            makespan = result['makespan']
            if result['scene'] != 'B' or result['num_cores'] != run['cores']:
                raise ValueError('wrong scene or core count')
            if makespan != run['metrics']['makespan_cycles'] or not math.isfinite(makespan) or makespan <= 0:
                raise ValueError('official result and receipt disagree')
            rows.append({'case_id': run['case_id'], 'cores': run['cores'],
                         'makespan_cycles': makespan, 'baseline_cycles': baseline['makespan_cycles'],
                         'speedup': baseline['makespan_cycles'] / makespan,
                         'extra_ddr_bytes': result['data_movement_bytes']['added_copy_bytes'],
                         'spill_bytes': result['data_movement_bytes']['spill_added_copy_bytes'],
                         'solver_wall_seconds': run['stages']['solver']['wall_seconds'],
                         'E0_wall_seconds': run['stages']['E0']['wall_seconds'],
                         'run_path': name, 'result_sha256': artifact['sha256'],
                         'baseline_receipt_sha256': reference(base_path)['sha256']})
    all_cases = {f'{n:03}' for n in range(1, 101)}
    cores = {}
    for k in range(1, 6):
        selected = [r for r in rows if r['cores'] == k]
        present = {r['case_id'] for r in selected}
        if present - all_cases:
            raise ValueError('unexpected official case')
        scores = [r['speedup'] for r in selected]
        complete = present == all_cases
        cores[str(k)] = {'successful_cases': len(present), 'complete': complete,
                         'missing_cases': sorted(all_cases - present),
                         'full100_arithmetic_mean': statistics.fmean(scores) if complete else None,
                         'observed_subset_mean': statistics.fmean(scores) if scores else None,
                         'faster_than_official_A_baseline': sum(r['speedup'] > 1 for r in selected),
                         'equal_to_official_A_baseline': sum(r['speedup'] == 1 for r in selected),
                         'slower_than_official_A_baseline': sum(r['speedup'] < 1 for r in selected),
                         'solver_wall_total_seconds': sum(r['solver_wall_seconds'] for r in selected),
                         'external_E0_wall_total_seconds': sum(r['E0_wall_seconds'] for r in selected)}
    return {'created_at': datetime.now(timezone.utc).isoformat(), 'solver_commit': solver_commit,
            'source_hashes': source_hashes, 'problem': 'P2', 'algorithm': variant,
            'args': fixed_args,
            'scope': 'Exactly one fixed algorithm, no best-of selection; arithmetic mean of per-case fixed official A baseline / P2 makespan. '
                     'Only a complete 100-case core gets a full mean. Shared-resource wall times are observations, not exclusive-machine comparisons.',
            'new_postprocessing_solver_calls': 0, 'new_postprocessing_E0_calls': 0,
            'measured_calls_in_included_batches': calls, 'batches': receipts, 'cores': cores,
            'incomplete_attempts': incomplete, 'rows': sorted(rows, key=lambda r: (r['cores'], r['case_id']))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, action='append', required=True)
    parser.add_argument('--solver-commit', required=True)
    parser.add_argument('--variant', default='tensor_packet')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = summarize([p.resolve() for p in args.batch], args.solver_commit, args.variant)
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / 'coverage.json').open('x', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    if report['rows']:
        with (args.output / 'per-cell.csv').open('x', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(report['rows'][0]))
            writer.writeheader()
            writer.writerows(report['rows'])
    print(json.dumps({'cores': report['cores'], 'calls': report['measured_calls_in_included_batches']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
