"""Verify a completed direct matrix and export reports; never runs scoring.

Run with the expected immutable source/runner IDs and comparison data commit.
All writes are batch-level derived files beside this script; original cells/feed
are immutable. Refuses to replace an existing aggregate or report.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = next(p for p in OUT.parents if (p / 'docs/a/source-manifest.json').is_file())
METRICS = ('makespan_cycles', 'ddr_bytes', 'extra_ddr_bytes', 'spill_bytes',
           'solver_wall_seconds', 'evaluation_wall_seconds')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rel(path):
    return path.relative_to(ROOT).as_posix()


def decode(raw, name=''):
    return json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)


def read(path):
    return decode(path.read_bytes(), path.name)


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def git_bytes(commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)


def verify_reference(entry):
    raw = (ROOT / entry['path']).read_bytes()
    assert sha(raw) == entry['sha256'], entry['path']
    return decode(raw, entry['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--runner', required=True)
    parser.add_argument('--comparison-data', required=True)
    parser.add_argument('--comparison-run', required=True, type=Path)
    parser.add_argument('--preflight-note', default='No preflight issue reported.')
    args = parser.parse_args()
    started = time.monotonic()
    original = {p: sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and p.name not in ('postprocess.py', '.gitattributes')}
    assert not (OUT / 'board-feed.json').exists(), 'Derived output already exists; preserve prior export.'
    context, journal = read(OUT / 'context.json'), read(OUT / 'journal.json')
    assert context['source_commit'] == args.source and context['runner_commit'] == args.runner
    assert journal['identity'] == {k: context[k] for k in ('source_commit', 'runner_commit', 'protocol_sha256')}
    protocol_path = context['argv'][context['argv'].index('--protocol') + 1]
    protocol_raw = git_bytes(args.runner, protocol_path)
    assert sha(protocol_raw) == context['protocol_sha256']
    assert protocol_raw == (ROOT / protocol_path).read_bytes()
    protocol = decode(protocol_raw)
    assert protocol['solver_mode'] == 'direct' and protocol['max_internal_per_cell'] == 0
    assert protocol['retries'] == 0 and protocol['workers'] == 1
    expected = [f'{c}-k{k}' for c in protocol['cases'] for k in protocol['cores']]
    assert list(journal['cells']) == expected
    assert journal['stop_reason'] == 'all_fixed_cells_dispatched' and journal['finished_at']
    assert all(c['state'] == 'ok' and c['charged_E0'] == 1 for c in journal['cells'].values())
    calls = {k: sum(c['calls'][k] for c in journal['cells'].values()) for k in ('solver', 'E0', 'E1', 'E2')}
    assert calls == {'solver': len(expected), 'E0': len(expected), 'E1': 0, 'E2': 0}
    assert journal['budget_E0'] == protocol['max_E0'] == len(expected)
    fixed_checks = []
    for category, commit in (('source', args.source), ('runner', args.runner)):
        for path, digest in context['hashes'][category].items():
            assert sha(git_bytes(commit, path)) == digest, (category, path)
            fixed_checks.append({'category': category, 'path': path, 'commit': commit, 'sha256': digest})
    source_manifest = decode(git_bytes(args.runner, 'docs/a/source-manifest.json'))
    entries = {x['path']: x for x in source_manifest['files']}
    assert source_manifest['official_code_hash'] == protocol['official_sha256']
    for category in ('official', 'inputs'):
        for path, digest in context['hashes'][category].items():
            assert entries[path]['sha256'] == digest
            assert sha((ROOT / 'data/raw/a/official' / path).read_bytes()) == digest
            fixed_checks.append({'category': category, 'path': path, 'sha256': digest})
    records, rows, index, old_refs, peaks, pids = [], [], [], [], [], []
    manifest_count = compression_count = 0
    audit_path = ROOT / 'results/a/q2-nikolastarx/target-audit-20260924/per-cell.csv'
    audit = {(r['case_id'], int(r['cores'])): r for r in csv.DictReader(audit_path.open())}
    for key in expected:
        folder = OUT / key
        run, ledger = read(folder / 'run.json'), read(folder / 'online/solver.json')
        record = read(OUT / f'board-feed-{key}.json')['records'][0]
        result = read(folder / 'final/result.json.gz')
        assert run['status'] == ledger['status'] == record['status'] == 'ok'
        assert run['phase'] == 'complete' and run['solver_mode'] == 'direct'
        assert run['calls'] == journal['cells'][key]['calls'] == record['provenance']['measurement']['calls']
        assert run['online'] == ledger and ledger['calls'] == {'E0': 0, 'E1': 0, 'E2': 0}
        assert run['full_online_result_equal'] is None and len(ledger['attempts']) == 1
        assert record['problem'] == 'P2' and result['scene'] == 'B'
        assert record['case_id'] == run['case'] and record['cores'] == result['num_cores'] == run['cores']
        assert record['solver_commit'] == record['provenance']['solver']['source']['commit'] == args.source
        assert record['provenance']['runner']['source']['commit'] == args.runner
        assert record['parameters']['protocol'] == protocol
        assert record['identity']['graph_sha256'] == context['hashes']['inputs'][f'data/case_{run["case"]}.json']
        assert record['identity']['config_sha256'] == protocol['config_sha256'] == context['hashes']['inputs']['data/config.txt']
        assert record['identity']['official_sha256'] == protocol['official_sha256']
        assert type(result['makespan']) is type(record['metrics']['makespan_cycles']) is int
        assert result['makespan'] == run['makespan_cycles'] == record['metrics']['makespan_cycles'] > 0
        plan_raw = (folder / 'plan.json').read_bytes()
        plan = decode(plan_raw)
        assert set(plan) == {'node_to_subgraph', 'core_schedules'}
        assert isinstance(plan['node_to_subgraph'], dict) and isinstance(plan['core_schedules'], list)
        assert all(isinstance(x, list) for x in plan['core_schedules'])
        assert sha(plan_raw) == ledger['plan_sha256'] == ledger['attempts'][0]['plan_sha256'] == record['identity']['plan_sha256']
        for metric, official in (('ddr_bytes', 'scheduled_copy_bytes'), ('extra_ddr_bytes', 'added_copy_bytes'), ('spill_bytes', 'spill_added_copy_bytes')):
            assert record['metrics'][metric] == result['data_movement_bytes'][official]
        for stage, receipt_path in (('solver', 'solver-process/process.json'), ('final', 'final/process.json')):
            receipt = run[stage]
            assert receipt == read(folder / receipt_path)
            assert receipt['status'] == 'ok' and receipt['exit_code'] == 0 and receipt['finished_at']
            assert not receipt['surviving_pids'] and not receipt['cleanup_killed_pids']
            metric = 'solver_wall_seconds' if stage == 'solver' else 'evaluation_wall_seconds'
            assert record['metrics'][metric] == receipt['wall_seconds']
            peaks.append(receipt['observer_inclusive_peak_rss_bytes'])
            assert peaks[-1] <= protocol['rss_observation_stop_bytes']
            pids.append(receipt['pid'])
        assert 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py' in run['final']['argv']
        for name, entry in read(folder / 'manifest.json').items():
            raw = (folder / name).read_bytes()
            assert len(raw) == entry['bytes'] and sha(raw) == entry['sha256'], (key, name)
            manifest_count += 1
        for entry in read(folder / 'archive.json')['compression'].values():
            packed = (folder / entry['stored']).read_bytes()
            raw = gzip.decompress(packed)
            assert sha(packed) == entry['stored_sha256'] and len(packed) == entry['stored_bytes']
            assert sha(raw) == entry['raw_sha256'] and len(raw) == entry['raw_bytes']
            compression_count += 1
        for entry in record['artifacts'].values():
            verify_reference(entry)
        verify_reference(record['baseline']['result'])
        for identity in ('graph_sha256', 'config_sha256', 'official_sha256'):
            assert record['baseline'][identity] == record['identity'][identity]
        check = read(OUT / f'precheck-{key}.json')
        eligibility = json.loads(check['stdout'])
        assert check['exit_code'] == 0 and eligibility['valid'] and eligibility['eligible'] == 1
        feed_path = OUT / f'board-feed-{key}.json'
        index.append({'cell': key, 'path': rel(feed_path), 'sha256': sha(feed_path.read_bytes()), 'precheck': eligibility})
        old_feed_path = args.comparison_run / feed_path.name
        old_raw = git_bytes(args.comparison_data, old_feed_path.as_posix())
        old = decode(old_raw)['records'][0]
        old_result_raw = git_bytes(args.comparison_data, old['artifacts']['result']['path'])
        old_result = decode(old_result_raw, old['artifacts']['result']['path'])
        assert sha(old_result_raw) == old['artifacts']['result']['sha256']
        old_run_raw = git_bytes(args.comparison_data, old['artifacts']['run']['path'])
        old_run = decode(old_run_raw)
        assert sha(old_run_raw) == old['artifacts']['run']['sha256']
        assert old['status'] == old_run['status'] == 'ok'
        assert old['case_id'] == record['case_id'] and old['cores'] == record['cores']
        for identity in ('graph_sha256', 'config_sha256', 'official_sha256'):
            assert record['identity'][identity] == old['identity'][identity]
        assert old_result['makespan'] == old['metrics']['makespan_cycles']
        for metric, official in (('ddr_bytes', 'scheduled_copy_bytes'), ('extra_ddr_bytes', 'added_copy_bytes'), ('spill_bytes', 'spill_added_copy_bytes')):
            assert old['metrics'][metric] == old_result['data_movement_bytes'][official]
        assert old['metrics']['solver_wall_seconds'] == old_run['solver']['wall_seconds']
        assert old['metrics']['evaluation_wall_seconds'] == old_run['final']['wall_seconds']
        row = {'case': run['case'], 'cores': run['cores'], 'status': run['status']}
        for metric in METRICS:
            row['old_' + metric] = old['metrics'][metric]
            row['new_' + metric] = record['metrics'][metric]
            row['delta_' + metric] = row['new_' + metric] - row['old_' + metric]
        row['makespan_new_over_old'] = row['new_makespan_cycles'] / row['old_makespan_cycles']
        row['makespan_reduction_percent'] = 100 * (1 - row['makespan_new_over_old'])
        row['quality_vs_direct'] = 'win' if row['makespan_new_over_old'] < 1 else 'loss' if row['makespan_new_over_old'] > 1 else 'tie'
        frozen = audit[(run['case'], run['cores'])]
        for label in ('fang', 'history'):
            row[label + '_makespan_cycles'] = int(frozen[label + '_makespan_cycles'])
            row['new_over_' + label] = row['new_makespan_cycles'] / row[label + '_makespan_cycles']
        row['frozen_history_record_id'] = frozen['history_record_id']
        rows.append(row)
        records.append(record)
        old_refs.append({'cell': key, 'solver_commit': old['solver_commit'], 'feed': old_feed_path.as_posix(), 'feed_sha256': sha(old_raw),
                         'result': old['artifacts']['result'], 'run': old['artifacts']['run']})
    live = {int(x) for x in subprocess.check_output(['ps', '-axo', 'pid='], text=True).splitlines()}
    survivors = sorted(set(pids) & live)
    assert not survivors, survivors
    aggregate = OUT / 'board-feed.json'
    save(aggregate, {'schema_version': 1, 'submission_version': 1, 'records': records})
    argv = [sys.executable, '-B', 'src/benchmark_board/protocol.py', rel(aggregate), '--submission']
    checked = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, timeout=30)
    # Record portable interpreter path when it is the repository environment.
    recorded_argv = [rel(Path(sys.executable)) if Path(sys.executable).is_relative_to(ROOT) else sys.executable] + argv[1:]
    save(OUT / 'precheck.json', {'argv': recorded_argv, 'exit_code': checked.returncode, 'stdout': checked.stdout, 'stderr': checked.stderr})
    eligible = json.loads(checked.stdout)
    assert checked.returncode == 0 and eligible['valid'] and eligible['eligible'] == len(expected)
    index.append({'cell': 'aggregate', 'path': rel(aggregate), 'sha256': sha(aggregate.read_bytes()), 'precheck': eligible})
    save(OUT / 'feed-index.json', index)
    with (OUT / 'metrics.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    assert b'\r' not in (OUT / 'metrics.csv').read_bytes()
    summary = {'rows': rows, 'quality_vs_direct': {x: sum(r['quality_vs_direct'] == x for r in rows) for x in ('win', 'tie', 'loss')},
               'scope': 'Selected development cells; not a whole-100 aggregate or one globally validated solver.',
               'frozen_history': {'path': rel(audit_path), 'sha256': sha(audit_path.read_bytes()), 'snapshot_utc': '2026-09-24T14:45:49.529895Z'},
               'solver_wall_summary': {label: fn([r['new_solver_wall_seconds'] for r in rows]) for label, fn in (('min', min), ('max', max), ('mean', statistics.mean), ('median', statistics.median))}}
    save(OUT / 'summary.json', summary)
    assert all(sha(p.read_bytes()) == digest for p, digest in original.items()), 'An original changed during export.'
    verification = {'status': 'pass', 'verified_at': datetime.now(timezone.utc).isoformat(), 'cells': len(expected), 'calls': calls,
                    'new_scoring_calls_during_verification': 0, 'online_E0': 0, 'external_E0': len(expected), 'failures': 0, 'scoring_retries': 0,
                    'preflight_note': args.preflight_note, 'preflight_note_evidence': 'Parent execution report; not inferred from successful scoring receipts.',
                    'eligible_records': eligible['eligible'], 'source_commit': args.source, 'runner_commit': args.runner,
                    'comparison_data_commit': args.comparison_data, 'comparison_verified_git_originals': old_refs,
                    'runtime_hashes_verified': fixed_checks, 'cell_manifest_entries_verified': manifest_count,
                    'compressed_json_roundtrips': compression_count, 'original_files_unchanged': len(original),
                    'owned_child_pids_checked': pids, 'owned_child_pids_still_present': survivors,
                    'maximum_observer_inclusive_rss_bytes': max(peaks), 'aggregate_feed_sha256': sha(aggregate.read_bytes()),
                    'precheck_code_sha256': sha((ROOT / 'src/benchmark_board/protocol.py').read_bytes()),
                    'verification_wall_seconds': time.monotonic() - started,
                    'limits': 'Process receipts plus present-PID absence; sampled RSS may miss peaks. Producer precheck is not central admission. Nonexclusive wall time is not causal speedup.'}
    save(OUT / 'verification.json', verification)
    lines = ['# P2 direct structural pilot: fixed development cells', '', f'Solver `{args.source}`; runner `{args.runner}`.', '',
             f'Execution UTC {journal["started_at"]} to {journal["finished_at"]}; matrix wall {journal["execution_wall_seconds"]:.9f} s.', '',
             f'{len(expected)} solver calls and {len(expected)} separate final official E0 calls succeeded. Online E0/E1/E2=0; scoring failures/retries=0. Verification adds zero solver or evaluator calls.', '',
             args.preflight_note + ' This note comes from the parent execution report, separate from per-cell scoring receipts.', '',
             '| Case | k | Old Makespan | New Makespan | Change (cycles) | Reduction | DDR B | Extra DDR B | Spill B | Solver s | Final E0 s |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f'| {row["case"]} | {row["cores"]} | {row["old_makespan_cycles"]} | {row["new_makespan_cycles"]} | {row["delta_makespan_cycles"]:+} | {row["makespan_reduction_percent"]:.4f}% | {row["new_ddr_bytes"]} | {row["new_extra_ddr_bytes"]} | {row["new_spill_bytes"]} | {row["new_solver_wall_seconds"]:.6f} | {row["new_evaluation_wall_seconds"]:.6f} |')
    lines += ['', f'Paired quality versus frozen direct pilot: {summary["quality_vs_direct"]}. All cells, including regressions, are retained. Old feed/result/run are read from Git data `{args.comparison_data}`; same case/core/graph/config/official identities were checked. No old solver was rerun.', '',
              'Observed zero spill describes these final official results only; it does not prove the priority-interval certificates sufficient in general. DDR/extra/spill byte reductions do not imply a Makespan improvement. Algorithm detail fields are preserved in original solver.json and not generalized by this exporter.', '',
              'These are selected development cells, not held-out or full-100 performance. The frozen Fang/history reference is timestamped in summary.json; history is a mix of winners, not one solver. All old/new byte and wall differences are available in metrics.csv. Shared-machine wall times include launch, input, construction, output and observation/cleanup; final E0 time is separate. Timing differences do not establish causal speedup.', '',
              f'All {manifest_count} per-cell manifest entries and {compression_count} lossless compressed JSON round-trips verified; all original files unchanged. Process receipts have exit0/no survivors, and all {len(pids)} owned PIDs are absent at verification. Each feed and aggregate pass local producer precheck; central admission and scientific acceptance remain separate.', '',
              'The original final/official.log files are Git-ignored and require explicit inclusion by the parent publisher. Raw stdout is unchanged except any runner-recorded redaction in archive.json. No Git mutation, central import or mirror synchronization was done by this exporter.', '']
    with (OUT / 'SUMMARY.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines))
    with (OUT / '.gitattributes').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('# Preserve archived evidence and hashes byte for byte.\n* -text\n')
    manifest = {p.relative_to(OUT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                for p in sorted(OUT.rglob('*')) if p.is_file() and p != OUT / 'manifest.json'}
    save(OUT / 'manifest.json', manifest)
    print(json.dumps({'run': rel(OUT), 'rows': rows, 'feed_sha256': verification['aggregate_feed_sha256'],
                      'manifest_sha256': sha((OUT / 'manifest.json').read_bytes()), 'manifest_files': len(manifest),
                      'eligible': eligible['eligible'], 'calls': calls, 'roundtrips': compression_count,
                      'verification_wall_seconds': time.monotonic() - started}, indent=2))


if __name__ == '__main__':
    main()
