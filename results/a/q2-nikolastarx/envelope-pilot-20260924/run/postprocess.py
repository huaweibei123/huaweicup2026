"""Read-only scoring evidence verification and report export; executes no solver/E0.

Run from the repository root with Python. Writes only batch-level derived reports.
"""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'results/a/q2-nikolastarx/direct-pilot-20260924/run'
OLD_COMMIT = '81219bf923524fb60616e39b5ad2dced67aec3e2'
SOURCE = '919c82370a42eca9fcff444bef4c1e1e3ea78282'
RUNNER = 'aa714b3811fa3722e5e126be12268917af0da93f'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def rel(path):
    return path.relative_to(ROOT).as_posix()


def frozen_old(path):
    raw = subprocess.check_output(['git', 'show', OLD_COMMIT + ':' + rel(path)], cwd=ROOT)
    assert raw == path.read_bytes(), rel(path)
    return raw


def main():
    journal = read(OUT / 'journal.json')
    context = read(OUT / 'context.json')
    assert journal['identity']['source_commit'] == SOURCE
    assert journal['identity']['runner_commit'] == RUNNER
    assert context['source_commit'] == SOURCE and context['runner_commit'] == RUNNER
    fixed_hashes_checked = 0
    for category, commit in (('source', SOURCE), ('runner', RUNNER)):
        for path, recorded_hash in context['hashes'][category].items():
            raw = subprocess.check_output(['git', 'show', commit + ':' + path], cwd=ROOT)
            assert sha(raw) == recorded_hash, (category, path)
            fixed_hashes_checked += 1
    # Source files may have moved on after the finished run. Verify captured hashes
    # against immutable Git objects, not against the subsequent working tree.
    source_manifest = json.loads(subprocess.check_output(['git', 'show', RUNNER + ':docs/a/source-manifest.json'], cwd=ROOT))
    official_entries = {x['path']: x for x in source_manifest['files']}
    for category in ('official', 'inputs'):
        for path, recorded_hash in context['hashes'][category].items():
            assert official_entries[path]['sha256'] == recorded_hash
            fixed_hashes_checked += 1
    assert journal['stop_reason'] == 'all_fixed_cells_dispatched'
    expected = [f'{c}-k{k}' for c in ('014', '025') for k in (2, 4, 5)]
    assert list(journal['cells']) == expected
    assert all(c['state'] == 'ok' for c in journal['cells'].values())
    calls = {kind: sum(c['calls'][kind] for c in journal['cells'].values()) for kind in ('solver', 'E0', 'E1', 'E2')}
    assert calls == {'solver': 6, 'E0': 6, 'E1': 0, 'E2': 0}
    records, rows, index, pids, manifests, compressed, peaks, old_sources = [], [], [], [], 0, 0, [], []
    for key in expected:
        folder = OUT / key
        run, ledger = read(folder / 'run.json'), read(folder / 'online/solver.json')
        feed = OUT / f'board-feed-{key}.json'
        record = read(feed)['records'][0]
        result = read(folder / 'final/result.json.gz')
        check = read(OUT / f'precheck-{key}.json')
        eligibility = json.loads(check['stdout'])
        assert check['exit_code'] == 0 and eligibility['valid'] and eligibility['eligible'] == 1
        assert run['status'] == ledger['status'] == record['status'] == 'ok'
        assert ledger['calls'] == {'E0': 0, 'E1': 0, 'E2': 0}
        assert run['full_online_result_equal'] is None
        assert result['scene'] == 'B' and result['num_cores'] == run['cores']
        assert type(result['makespan']) is type(record['metrics']['makespan_cycles']) is int
        assert result['makespan'] == run['makespan_cycles'] == record['metrics']['makespan_cycles']
        plan = (folder / 'plan.json').read_bytes()
        assert plan == (folder / 'online/component_envelope/plan.json').read_bytes()
        assert set(json.loads(plan)) == {'node_to_subgraph', 'core_schedules'}
        assert sha(plan) == ledger['plan_sha256'] == record['identity']['plan_sha256']
        for metric, official in (('ddr_bytes', 'scheduled_copy_bytes'), ('extra_ddr_bytes', 'added_copy_bytes'), ('spill_bytes', 'spill_added_copy_bytes')):
            assert record['metrics'][metric] == result['data_movement_bytes'][official]
        for stage in ('solver', 'final'):
            receipt = run[stage]
            assert receipt['status'] == 'ok' and receipt['exit_code'] == 0 and not receipt['surviving_pids']
            peaks.append(receipt['observer_inclusive_peak_rss_bytes'])
            assert peaks[-1] <= 4 * 1024**3
            pids.append(receipt['pid'])
        for name, entry in read(folder / 'manifest.json').items():
            raw = (folder / name).read_bytes()
            assert len(raw) == entry['bytes'] and sha(raw) == entry['sha256']
            manifests += 1
        for entry in read(folder / 'archive.json')['compression'].values():
            packed = (folder / entry['stored']).read_bytes()
            raw = gzip.decompress(packed)
            assert sha(packed) == entry['stored_sha256'] and len(packed) == entry['stored_bytes']
            assert sha(raw) == entry['raw_sha256'] and len(raw) == entry['raw_bytes']
            compressed += 1
        for entry in record['artifacts'].values():
            assert sha((ROOT / entry['path']).read_bytes()) == entry['sha256']
        baseline = record['baseline']['result']
        assert sha((ROOT / baseline['path']).read_bytes()) == baseline['sha256']
        old_feed = OLD / feed.name
        old = json.loads(frozen_old(old_feed))['records'][0]
        old_result_path = ROOT / old['artifacts']['result']['path']
        old_raw = frozen_old(old_result_path)
        assert sha(old_raw) == old['artifacts']['result']['sha256']
        old_result = json.loads(gzip.decompress(old_raw))
        for identity in ('graph_sha256', 'config_sha256', 'official_sha256'):
            assert record['identity'][identity] == old['identity'][identity]
        assert old['solver_commit'] == 'dd9d89918f7a4e3d2cfab48d4d0246db3408310b'
        assert old_result['makespan'] == old['metrics']['makespan_cycles']
        row = {'case': run['case'], 'cores': run['cores'], 'status': run['status']}
        for metric in ('makespan_cycles', 'ddr_bytes', 'extra_ddr_bytes', 'spill_bytes', 'solver_wall_seconds', 'evaluation_wall_seconds'):
            row['old_' + metric] = old['metrics'][metric]
            row['new_' + metric] = record['metrics'][metric]
            row['delta_' + metric] = row['new_' + metric] - row['old_' + metric]
        row['makespan_reduction_percent'] = 100 * (1 - row['new_makespan_cycles'] / row['old_makespan_cycles'])
        detail = ledger['attempts'][0]['detail']
        row['all_raw_envelopes_fit'] = all(core['all_raw_envelopes_fit'] for core in detail['per_core'])
        row['uncertified_cohorts'] = sum(not cohort['within_capacity'] for core in detail['per_core'] for cohort in core['cohorts'])
        rows.append(row)
        records.append(record)
        index.append({'cell': key, 'path': rel(feed), 'sha256': sha(feed.read_bytes()), 'precheck': eligibility})
        old_sources.append({'feed': rel(old_feed), 'feed_sha256': sha(old_feed.read_bytes()), 'result': rel(old_result_path), 'result_sha256': sha(old_raw)})
    live = {int(line) for line in subprocess.check_output(['ps', '-axo', 'pid='], text=True).splitlines()}
    survivors = sorted(set(pids) & live)
    assert not survivors, survivors
    aggregate = OUT / 'board-feed.json'
    save(aggregate, {'schema_version': 1, 'submission_version': 1, 'records': records})
    argv = ['.venv/bin/python', '-B', 'src/benchmark_board/protocol.py', rel(aggregate), '--submission']
    checked = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True)
    save(OUT / 'precheck.json', {'argv': argv, 'exit_code': checked.returncode, 'stdout': checked.stdout, 'stderr': checked.stderr})
    eligibility = json.loads(checked.stdout)
    assert checked.returncode == 0 and eligibility['valid'] and eligibility['eligible'] == 6
    index.append({'cell': 'aggregate-6', 'path': rel(aggregate), 'sha256': sha(aggregate.read_bytes()), 'precheck': eligibility})
    save(OUT / 'feed-index.json', index)
    with (OUT / 'metrics.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification = {'status': 'pass', 'cells': 6, 'calls': calls, 'online_E0': 0, 'external_E0': 6,
        'failures': 0, 'retries': 0, 'eligible_records': 6, 'cell_manifest_files_checked': manifests,
        'compressed_json_roundtrips': compressed, 'owned_child_pids_checked': len(pids),
        'owned_child_pids_still_present': survivors, 'maximum_observer_inclusive_rss_bytes': max(peaks),
        'source_commit': SOURCE, 'runner_commit': RUNNER, 'comparison_data_commit': OLD_COMMIT,
        'runtime_hashes_verified_against_fixed_git_and_official_manifest': fixed_hashes_checked,
        'comparison_verified_git_originals': old_sources,
        'aggregate_feed_sha256': sha(aggregate.read_bytes()),
        'limits': 'Six development cells, no causal or full-suite claim; shared-machine wall time and sampled RSS.',
        'solver_wall_summary': {label: fn([r['new_solver_wall_seconds'] for r in rows]) for label, fn in (('min', min), ('max', max), ('mean', statistics.mean), ('median', statistics.median))}}
    save(OUT / 'verification.json', verification)
    lines = ['# Component-envelope P2 pilot: six fixed cells', '',
        f'Source `{SOURCE}`; runner `{RUNNER}`.', '',
        f"UTC {journal['started_at']} to {journal['finished_at']}; execution batch wall {journal['execution_wall_seconds']:.9f} s.", '',
        'All six solver and final E0 calls succeeded. Zero online E0; six external E0; E1/E2=0; zero retries, failures or replacement. All 12 owned child PIDs had exited when checked.', '',
        '| Case | k | Old Makespan | New Makespan | Reduction | Old spill B | New spill B | Old extra DDR B | New extra DDR B | Solver s |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['case']} | {r['cores']} | {r['old_makespan_cycles']} | {r['new_makespan_cycles']} | {r['makespan_reduction_percent']:.2f}% | {r['old_spill_bytes']} | {r['new_spill_bytes']} | {r['old_extra_ddr_bytes']} | {r['new_extra_ddr_bytes']} | {r['new_solver_wall_seconds']:.6f} |")
    lines += ['', 'All six new Makespans, spill totals and extra-DDR totals decreased relative to the same-case/core frozen dd9d8991 direct pilot. The old feed/result bytes were compared to Git data commit `' + OLD_COMMIT + '`. Old records were not re-executed. All paired graph/config/official identities match.', '',
        '025 has zero official spill in these three runs; 014 retains positive spill. The envelope metadata is a priority-order certificate only, not a zero-spill proof or a runtime feasibility theorem. Multiple algorithm choices changed together, so the measured reductions do not identify a single causal mechanism.', '',
        'This is a selected development sample, not the full 100-case result. End-to-end solver wall includes process launch, input, construction, output and observation/cleanup; the independent final E0 wall is separate in metrics.csv. Shared P1 load may be present, and wall timing is nonexclusive. RSS polling can miss short peaks.', '',
        f'Verified {manifests} per-cell manifest entries and {compressed} lossless compressed JSON round-trips; six independent feeds and the aggregate feed pass producer precheck. All original per-cell evidence remains unchanged. No central import, Git commit/push, mirror sync or broader acceptance was performed.', '',
        'Official `final/official.log` files are Git-ignored and must be explicitly included by the parent publisher. Raw stdout backup path was emitted by the runner and sent to the parent; shared redactions, if present, are recorded in archive.json.', '']
    (OUT / 'SUMMARY.md').write_text('\n'.join(lines))
    # This script and all derived reports join the final manifest. Per-cell manifests stay unchanged.
    manifest = {p.relative_to(OUT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                for p in sorted(OUT.rglob('*')) if p.is_file() and p != OUT / 'manifest.json'}
    save(OUT / 'manifest.json', manifest)
    print(json.dumps(verification, indent=2))
    print(json.dumps({'manifest_files': len(manifest), 'bytes': sum(x['bytes'] for x in manifest.values()), 'manifest_sha256': sha((OUT / 'manifest.json').read_bytes())}))


if __name__ == '__main__':
    main()
