"""Zero-scoring verifier/exporter for the frozen six-cell adaptive smoke.

Reads original nested matrix/driver artifacts and local archived comparisons.
Never invokes Git, solver, evaluator or a network endpoint. Refuses to overwrite
existing exports. Producer precheck only reads evidence via a temporary ledger.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import csv
import gzip
import hashlib
import json
import statistics
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = next(p for p in OUT.parents if (p / 'docs/a/source-manifest.json').is_file())
SOURCE = '6e5099a35300133419990bf1f44f621f98850c21'
RUNNER = '08638ceb1ced999a1fe6024bbea61bc32657314f'
EXPECTED = ('008-k3', '014-k4', '025-k5', '016-k1', '016-k2', '062-k4')
PAIR = {'014-k4': 'envelope', '025-k5': 'envelope', '016-k2': 'direct', '062-k4': 'direct'}
SPECIALIST = {'016-k2': 'vector', '062-k4': 'tree'}
METRICS = ('makespan_cycles', 'ddr_bytes', 'extra_ddr_bytes', 'spill_bytes', 'solver_wall_seconds', 'evaluation_wall_seconds')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rel(path):
    return path.relative_to(ROOT).as_posix()


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def reference(entry):
    path = ROOT / entry['path']
    raw = path.read_bytes()
    assert sha(raw) == entry['sha256'], entry['path']
    return path


def comparison(batch_name, key, record, plan_raw):
    feed_path = ROOT / f'results/a/q2-nikolastarx/{batch_name}-pilot-20260924/run/board-feed-{key}.json'
    old = read(feed_path)['records'][0]
    assert old['status'] == 'ok' and old['problem'] == record['problem'] == 'P2'
    assert old['case_id'] == record['case_id'] and old['cores'] == record['cores']
    for field in ('graph_sha256', 'config_sha256', 'official_sha256'):
        assert old['identity'][field] == record['identity'][field]
    old_plan = reference(old['artifacts']['plan']).read_bytes()
    old_result = read(reference(old['artifacts']['result']))
    old_run = read(reference(old['artifacts']['run']))
    assert old_result['makespan'] == old['metrics']['makespan_cycles']
    for field, raw in (('ddr_bytes', 'scheduled_copy_bytes'), ('extra_ddr_bytes', 'added_copy_bytes'), ('spill_bytes', 'spill_added_copy_bytes')):
        assert old['metrics'][field] == old_result['data_movement_bytes'][raw]
    assert old_run['status'] == 'ok'
    assert old_run['solver']['wall_seconds'] == old['metrics']['solver_wall_seconds']
    detail = {'batch': batch_name, 'source_commit': old['solver_commit'], 'feed': rel(feed_path),
              'feed_sha256': sha(feed_path.read_bytes()), 'plan': old['artifacts']['plan'],
              'result': old['artifacts']['result'], 'run': old['artifacts']['run'],
              'plan_bytes_identical': old_plan == plan_raw,
              'old_metrics': old['metrics'], 'new_metrics': record['metrics'],
              'delta_metrics': {m: record['metrics'][m] - old['metrics'][m] for m in METRICS}}
    detail['new_over_old_makespan'] = record['metrics']['makespan_cycles'] / old['metrics']['makespan_cycles']
    detail['quality'] = 'win' if detail['new_over_old_makespan'] < 1 else 'loss' if detail['new_over_old_makespan'] > 1 else 'tie'
    return detail


def main():
    started = time.monotonic()
    assert not (OUT / 'board-feed.json').exists(), 'Exports already exist; preserve them.'
    original = {rel(p): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'postprocess.py'}
    batch = read(OUT / 'batch.json')
    frozen = read(OUT.parent / 'manifest.json')
    assert batch['source_commit'] == frozen['source_commit'] == SOURCE and batch['runner_commit'] == RUNNER
    assert batch['status'] == 'completed' and batch['finished_at'] and len(batch['cells']) == 6
    assert tuple(x['cell'] for x in batch['cells']) == EXPECTED
    assert tuple(f'{case}-k{k}' for case, k in frozen['cells']) == EXPECTED
    assert frozen['max_solver'] == frozen['max_E0'] == 6
    assert frozen['max_online_E0'] == frozen['max_E1'] == frozen['max_E2'] == frozen['retries'] == 0
    assert frozen['workers'] == 1 and batch['aggregate_wall_seconds'] <= frozen['aggregate_wall_seconds']
    source_manifest = read(ROOT / 'docs/a/source-manifest.json')
    official_files = {x['path']: x for x in source_manifest['files']}
    rows, records, indexes, hashes, comparisons, process_receipts = [], [], [], [], [], []
    calls = Counter()
    manifest_count = compression_count = 0
    for item in batch['cells']:
        key = item['cell']
        matrix, cell = OUT / key, OUT / key / key
        context, journal = read(matrix / 'context.json'), read(matrix / 'journal.json')
        run, ledger = read(cell / 'run.json'), read(cell / 'online/solver.json')
        protocol_path = context['argv'][context['argv'].index('--protocol') + 1]
        protocol_raw = (ROOT / protocol_path).read_bytes()
        protocol = json.loads(protocol_raw)
        assert protocol_path in frozen['protocols']
        assert context['source_commit'] == SOURCE and context['runner_commit'] == RUNNER
        assert journal['identity'] == {k: context[k] for k in ('source_commit', 'runner_commit', 'protocol_sha256')}
        assert sha(protocol_raw) == context['protocol_sha256']
        assert list(journal['cells']) == [key] and journal['stop_reason'] == 'all_fixed_cells_dispatched'
        assert journal['cells'][key]['state'] == 'ok' and journal['cells'][key]['charged_E0'] == 1
        assert protocol['max_E0'] == journal['budget_E0'] == 1
        assert protocol['max_internal_per_cell'] == protocol['retries'] == 0
        assert protocol['solver_mode'] == 'direct' and protocol['solver_module'] == 'src.q2_nikolastarx.adaptive_direct'
        assert protocol['cases'] == [run['case']] and protocol['cores'] == [run['cores']]
        for category in ('source', 'runner', 'official', 'inputs'):
            for path, digest in context['hashes'][category].items():
                actual = ROOT / path if category in ('source', 'runner') else ROOT / 'data/raw/a/official' / path
                assert sha(actual.read_bytes()) == digest, (category, path)
                if category in ('official', 'inputs'):
                    assert official_files[path]['sha256'] == digest
                hashes.append({'cell': key, 'category': category, 'path': path, 'sha256': digest})
        feed_path = matrix / f'board-feed-{key}.json'
        record = read(feed_path)['records'][0]
        result = read(cell / 'final/result.json.gz')
        assert run == item['attempt'] and item['accepted'] is True
        assert run['online'] == ledger
        assert record['status'] == run['status'] == ledger['status'] == 'ok'
        assert run['phase'] == 'complete' and run['solver_mode'] == 'direct' and run['full_online_result_equal'] is None
        assert ledger['calls'] == {'E0': 0, 'E1': 0, 'E2': 0} and len(ledger['attempts']) == 1
        assert run['calls'] == journal['cells'][key]['calls'] == record['provenance']['measurement']['calls'] == {'solver': 1, 'E0': 1, 'E1': 0, 'E2': 0}
        calls.update(run['calls'])
        assert record['problem'] == 'P2' and result['scene'] == 'B' and result.get('problem') != 3
        assert record['case_id'] == run['case'] and record['cores'] == result['num_cores'] == run['cores']
        assert record['solver_commit'] == record['provenance']['solver']['source']['commit'] == SOURCE
        assert record['provenance']['runner']['source']['commit'] == RUNNER
        assert record['parameters']['protocol'] == protocol
        assert record['identity']['graph_sha256'] == context['hashes']['inputs'][f'data/case_{run["case"]}.json']
        assert record['identity']['config_sha256'] == protocol['config_sha256'] == context['hashes']['inputs']['data/config.txt']
        assert record['identity']['official_sha256'] == protocol['official_sha256'] == source_manifest['official_code_hash']
        assert type(result['makespan']) is type(record['metrics']['makespan_cycles']) is int
        assert result['makespan'] == run['makespan_cycles'] == record['metrics']['makespan_cycles'] > 0
        plan_raw = (cell / 'plan.json').read_bytes()
        plan = json.loads(plan_raw)
        assert set(plan) == {'node_to_subgraph', 'core_schedules'}
        assert isinstance(plan['node_to_subgraph'], dict) and all(isinstance(x, list) for x in plan['core_schedules'])
        assert plan_raw == (cell / 'online/adaptive_direct/plan.json').read_bytes()
        assert sha(plan_raw) == ledger['plan_sha256'] == record['identity']['plan_sha256'] == ledger['attempts'][0]['plan_sha256']
        for field, raw in (('ddr_bytes', 'scheduled_copy_bytes'), ('extra_ddr_bytes', 'added_copy_bytes'), ('spill_bytes', 'spill_added_copy_bytes')):
            assert record['metrics'][field] == result['data_movement_bytes'][raw]
        for name, receipt, path in (('driver', item['driver'], OUT / f'{key}-driver/process.json'),
                                     ('solver', run['solver'], cell / 'solver-process/process.json'),
                                     ('final', run['final'], cell / 'final/process.json')):
            assert read(path) == receipt
            assert receipt['status'] == 'ok' and receipt['exit_code'] == 0 and receipt['finished_at']
            assert not receipt['surviving_pids'] and not receipt['cleanup_killed_pids']
            assert receipt['observer_inclusive_peak_rss_bytes'] <= frozen['rss_observation_stop_bytes']
            process_receipts.append({'cell': key, 'phase': name, 'pid': receipt['pid'], 'receipt': rel(path), 'sha256': sha(path.read_bytes())})
        assert record['metrics']['solver_wall_seconds'] == run['solver']['wall_seconds']
        assert record['metrics']['evaluation_wall_seconds'] == run['final']['wall_seconds']
        assert 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py' in run['final']['argv']
        for name, entry in read(cell / 'manifest.json').items():
            raw = (cell / name).read_bytes()
            assert len(raw) == entry['bytes'] and sha(raw) == entry['sha256'], (key, name)
            manifest_count += 1
        for entry in read(cell / 'archive.json')['compression'].values():
            packed = (cell / entry['stored']).read_bytes()
            raw = gzip.decompress(packed)
            assert sha(packed) == entry['stored_sha256'] and len(packed) == entry['stored_bytes']
            assert sha(raw) == entry['raw_sha256'] and len(raw) == entry['raw_bytes']
            compression_count += 1
        for entry in record['artifacts'].values():
            reference(entry)
        baseline = read(reference(record['baseline']['result']))
        for identity in ('graph_sha256', 'config_sha256', 'official_sha256'):
            assert record['baseline'][identity] == record['identity'][identity]
        precheck = read(matrix / f'precheck-{key}.json')
        eligibility = json.loads(precheck['stdout'])
        assert precheck['exit_code'] == 0 and eligibility['valid'] and eligibility['eligible'] == 1
        detail = ledger['attempts'][0]['detail']
        route = detail['adaptive_route']
        assert route == record['parameters']['selected_strategy'] == detail['selected_strategy']
        assert detail['index_constructions'] == 1
        row = {'case': run['case'], 'cores': run['cores'], 'status': run['status'], 'route': route,
               **{m: record['metrics'][m] for m in METRICS}, 'official_singlecore_makespan': baseline['makespan'],
               'official_baseline_speedup': baseline['makespan'] / result['makespan'],
               'paired_old_batch': None, 'paired_old_makespan': None, 'paired_plan_bytes_identical': None,
               'specialist_batch': None, 'specialist_makespan': None, 'new_over_specialist': None}
        comparisons_for_cell = {'cell': key, 'paired': None, 'specialist': None}
        if key in PAIR:
            old = comparison(PAIR[key], key, record, plan_raw)
            assert old['plan_bytes_identical'], ('Expected same plan', key)
            assert all(old['delta_metrics'][m] == 0 for m in METRICS[:4]), ('Same-plan quality differs', key)
            comparisons_for_cell['paired'] = old
            row.update(paired_old_batch=PAIR[key], paired_old_makespan=old['old_metrics']['makespan_cycles'], paired_plan_bytes_identical=True)
        if key in SPECIALIST:
            old = comparison(SPECIALIST[key], key, record, plan_raw)
            comparisons_for_cell['specialist'] = old
            row.update(specialist_batch=SPECIALIST[key], specialist_makespan=old['old_metrics']['makespan_cycles'], new_over_specialist=old['new_over_old_makespan'])
        comparisons.append(comparisons_for_cell)
        indexes.append({'cell': key, 'feed': rel(feed_path), 'sha256': sha(feed_path.read_bytes()), 'precheck': eligibility})
        records.append(record)
        rows.append(row)
    assert dict(calls) == {'solver': 6, 'E0': 6, 'E1': 0, 'E2': 0}
    live = {int(x) for x in subprocess.check_output(['ps', '-axo', 'pid='], text=True).splitlines()}
    survivors = sorted({r['pid'] for r in process_receipts} & live)
    assert not survivors, survivors
    save('board-feed.json', {'schema_version': 1, 'submission_version': 1, 'records': records})
    argv = [sys.executable, '-B', 'src/benchmark_board/protocol.py', rel(OUT / 'board-feed.json'), '--submission']
    checked = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, timeout=30)
    save('precheck.json', {'argv': ['.venv/bin/python', *argv[1:]], 'exit_code': checked.returncode, 'stdout': checked.stdout, 'stderr': checked.stderr})
    eligibility = json.loads(checked.stdout)
    assert checked.returncode == 0 and eligibility['valid'] and eligibility['eligible'] == 6
    feed_hash = sha((OUT / 'board-feed.json').read_bytes())
    indexes.append({'cell': 'aggregate-six', 'feed': rel(OUT / 'board-feed.json'), 'sha256': feed_hash, 'precheck': eligibility})
    save('feed-index.json', indexes)
    save('original-artifacts.json', original)
    save('comparisons.json', comparisons)
    with (OUT / 'metrics.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    assert b'\r' not in (OUT / 'metrics.csv').read_bytes()
    summary = {'source_commit': SOURCE, 'runner_commit': RUNNER, 'cells': rows,
               'route_counts': dict(Counter(r['route'] for r in rows)), 'calls': dict(calls), 'online_E0': 0,
               'batch_wall_seconds': batch['aggregate_wall_seconds'], 'eligible_records': eligibility['eligible'],
               'scope': 'One frozen unified router, six independently executed fixed cells, not the full 500-cell matrix.',
               'solver_wall_seconds': {'min': min(r['solver_wall_seconds'] for r in rows), 'max': max(r['solver_wall_seconds'] for r in rows), 'mean': statistics.mean(r['solver_wall_seconds'] for r in rows)},
               'original_plan_bytes_equal_to_old': [x['cell'] for x in comparisons if x['paired'] and x['paired']['plan_bytes_identical']],
               'specialist_regressions': [x['cell'] for x in comparisons if x['specialist'] and x['specialist']['quality'] == 'loss']}
    save('summary.json', summary)
    assert all(sha((ROOT / p).read_bytes()) == e['sha256'] and (ROOT / p).stat().st_size == e['bytes'] for p,e in original.items())
    verification = {'status': 'pass', 'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'source_commit': SOURCE, 'runner_commit': RUNNER,
                    'original_files_unchanged': len(original), 'cell_manifest_entries_verified': manifest_count,
                    'compressed_json_roundtrips': compression_count, 'process_receipts': process_receipts, 'surviving_pids': survivors,
                    'runtime_files_match_recorded_hashes': hashes, 'calls': dict(calls), 'online_E0': 0,
                    'new_scoring_calls_during_postprocess': 0, 'scoring_failures': 0, 'scoring_retries': 0,
                    'preflight_event': 'Parent reports a missing gitignored case path prevented preflight before scoring. Original bytes were verified and linked before the successful six-cell run. This is a zero-score preflight failure, not a scoring retry.',
                    'attribution_limit': 'Expected fixed source/runner IDs match context, journal, batch and feeds; current code bytes match recorded runtime hashes. No Git object reads were performed in this postprocess.',
                    'comparison_limit': 'Prior local archived feed/plan/result/run bytes rechecked by recorded hashes; no old solver or scoring call rerun. New six calls are real frozen-protocol executions.',
                    'process_limit': 'Terminal receipts and current PID absence; historical absence is not a continuous process monitor.',
                    'timing_limit': 'Solver wall includes process observation/cleanup; final E0 separate. Before/after machine timing differences are not causal speedup.',
                    'path_note': 'Original batch/driver receipts contain the actual absolute interpreter path; kept byte-for-byte unchanged. Root publisher should review personal path exposure without silently replacing evidence.',
                    'aggregate_feed_sha256': feed_hash, 'producer_precheck_eligible': eligibility['eligible'],
                    'precheck_code_sha256': sha((ROOT / 'src/benchmark_board/protocol.py').read_bytes()),
                    'verification_wall_seconds': time.monotonic() - started}
    save('verification.json', verification)
    lines = ['# Frozen adaptive-router smoke: six independent cells', '', f'Source `{SOURCE}`; runner `{RUNNER}`.', '',
             f'UTC {batch["started_at"]} to {batch["finished_at"]}; aggregate driver wall {batch["aggregate_wall_seconds"]:.9f} s.', '',
             'All six separately dispatched solver calls and six final official E0 calls succeeded. Online E0/E1/E2=0; scoring failures/retries=0. This postprocess added zero solver/evaluator calls. The initial missing-input preflight failed before scoring; original case bytes were linked and verified before the actual run (parent report).', '',
             '| Case | k | Actual route | Makespan cycles | DDR B | Extra DDR B | Spill B | Solver s | Final E0 s |',
             '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f'| {row["case"]} | {row["cores"]} | {row["route"]} | {row["makespan_cycles"]} | {row["ddr_bytes"]} | {row["extra_ddr_bytes"]} | {row["spill_bytes"]} | {row["solver_wall_seconds"]:.6f} | {row["evaluation_wall_seconds"]:.6f} |')
    lines += ['', 'The routes are resource_word (one), component_envelope (three), and dag_eft (two). This frozen unified router does not include the subsequently developed tree_frontier/vector_lanes constructors. It is six selected smoke cells, not a whole-100 or 500-cell result; no global mean is reported.', '',
              'Byte-for-byte plan equality and identical Makespan/DDR/extra/spill are confirmed against archived envelope 014-k4 / 025-k5 and direct 016-k2 / 062-k4. Old results are read only; the new six calls were explicitly required by the smoke protocol and really executed. Route-equivalence does not imply that the new timing difference is caused by shared-index reuse.', '',
              '| Cell | Later specialist | Specialist Makespan | Frozen router Makespan | Router / specialist |',
              '|---|---|---:|---:|---:|']
    for x in comparisons:
        if x['specialist']:
            c=x['specialist']
            lines.append(f'| {x["cell"]} | {c["batch"]} | {c["old_metrics"]["makespan_cycles"]} | {c["new_metrics"]["makespan_cycles"]} | {c["new_over_old_makespan"]:.6f} |')
    lines += ['', 'These two negative comparisons are retained. Their earlier tree/vector improvements are not attributed to this router. Capacity-priority metadata is not a runtime spill certificate, as the nonzero spill results show.', '',
              f'Checked {manifest_count} per-cell manifest entries, {compression_count} compressed JSON raw/stored hash-and-size roundtrips, {len(original)} immutable originals and 18 completed process receipts. No recorded child PID is present at verification. All six original prechecks and the aggregate precheck are eligible locally; this is not central admission or independent scientific acceptance.', '',
              'metrics.csv uses LF and includes matched official single-core denominators per cell. The P2 k=1 constructed result remains distinct from that denominator. Source/runtime/input/config/official hashes are checked against captured receipts and current original bytes; Git object verification and publication remain with the parent. No old scoring, Git command, message, network request, ledger write or mirror synchronization was performed by this script.', '',
              'Publication: explicitly include the six nested final/official.log files (normally Git-ignored). Original batch/driver receipts retain their actual absolute interpreter paths and are not silently rewritten. Parent should review these paths before publication. Shared-machine before/after wall differences are descriptive, not causal speedup.', '']
    with (OUT / 'SUMMARY.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines))
    with (OUT / '.gitattributes').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('# Preserve original evidence bytes and LF exports.\n* -text\n')
    manifest = {p.relative_to(OUT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                for p in sorted(OUT.rglob('*')) if p.is_file() and p != OUT / 'manifest.json'}
    save('manifest.json', manifest)
    print(json.dumps({'status': 'pass', 'cells': rows, 'feed_sha256': feed_hash, 'manifest_sha256': sha((OUT / 'manifest.json').read_bytes()),
                      'manifest_files': len(manifest), 'original_files': len(original), 'cell_manifest_entries': manifest_count,
                      'roundtrips': compression_count, 'process_receipts': len(process_receipts), 'calls': dict(calls),
                      'eligible': eligibility['eligible'], 'verification_wall_seconds': time.monotonic() - started}, indent=2))


if __name__ == '__main__':
    main()
