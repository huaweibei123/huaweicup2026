"""Archive verified compact hypergap cells as board-submission-v1 case groups.

This module reads accepted cells by coordinate and never imports a solver or evaluator.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.chain_pilot import pinned
REPO = 'huaweibei123/huaweicup2026'
SOLVER = 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'
RUNNER = 'ff47cbca4a953602dec7e4b959bbb10a016eca9a'
BASE = '60afc38b327680fbda0ff10182e3e05a01edd72d'
E2 = '603b0741e21c449d3db652ebd67c94f2dc014cc9'
OFFICIAL = '2794ceba93acc1f7fc119154f61082511843d4b3'
FANG = '71616ac7c4c7fca56e37e2d3245dd13725316d82'
P3_CALENDAR = 'a37eb931a22fb7df7e0d00d193538ce5289ae045'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def jbytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def read(path):
    return json.loads(path.read_bytes())


def sanitized(value):
    if isinstance(value, str):
        return value.replace(str(Path.home()), '<local-home>')
    if isinstance(value, list):
        return [sanitized(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitized(item) for key, item in value.items()}
    return value


def sanitized_receipt(raw, dest):
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError('Raw receipt exceeds 64 MiB')
    return archive_bytes(jbytes(sanitized(json.loads(raw))), dest)


def source(commit, path, entrypoint):
    return {'repo': REPO, 'commit': commit, 'path': path, 'entrypoint': entrypoint}


def matching_metrics(a, b):
    return (a['makespan'] == b['makespan']
            and a['cross_task_traffic'] == b['cross_task_traffic']
            and a['data_movement_bytes'] == b['data_movement_bytes'])


def frozen_feed(manifest):
    ref = manifest['baseline_feed']
    if ref['commit'] != BASE:
        raise ValueError('Unexpected baseline commit')
    raw = subprocess.check_output(['git', 'show', ref['commit'] + ':' + ref['path']], cwd=ROOT)
    if sha(raw) != ref['sha256']:
        raise ValueError('Baseline feed drift')
    records = json.loads(raw)['records']
    table = {(r['case_id'], r['cores']): r for r in records}
    if len(records) != 500 or len(table) != 500:
        raise ValueError('Baseline feed not unique full500')
    return table


def accepted_by_coordinate(summary, old):
    expected = {(r['case'], r['cores']) for r in old['rows']}
    if len(expected) != 500:
        raise ValueError('Expected 500 unique manifest coordinates')
    found = {}
    for row in summary['rows']:
        key = (row['case'], row['cores'])
        if key not in expected or key in found:
            raise ValueError('Unknown or duplicate summary coordinate')
        found[key] = row
    accepted = {k: v for k, v in found.items() if v['status'] == 'accepted'}
    if summary['accepted_cells'] != len(accepted):
        raise ValueError('Accepted count differs')
    if summary['status'] == 'completed' and (len(accepted) != 500 or len(found) != 500
                                           or summary['in_flight']):
        raise ValueError('False full500 completion')
    return accepted


def archive_file(src, dest, *, pack=False):
    raw = src.read_bytes()
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError('Raw artifact exceeds 64 MiB: ' + str(src))
    data = gzip.compress(raw, mtime=0) if pack else raw
    if len(data) > 64 * 1024 * 1024:
        raise ValueError('Artifact exceeds 64 MiB: ' + str(src))
    if dest.exists():
        if dest.read_bytes() != data:
            raise ValueError('Immutable artifact differs: ' + str(dest))
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(data)
    return {'path': dest.relative_to(ROOT).as_posix(), 'sha256': sha(data)}


def archive_bytes(data, dest):
    if dest.exists():
        if dest.read_bytes() != data:
            raise ValueError('Immutable receipt differs: ' + str(dest))
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(data)
    return {'path': dest.relative_to(ROOT).as_posix(), 'sha256': sha(data)}


def export(summary_path, manifest_path, output_root, run_id, case_start, case_end,
           producer_session, task_url, runtime_id, source_reference):
    from src.benchmark_board.protocol import validate_feed
    summary_raw = summary_path.read_bytes()
    summary = json.loads(summary_raw)
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    manifest_rel = manifest_path.relative_to(ROOT).as_posix()
    if manifest_raw != subprocess.check_output(['git', 'show', RUNNER+':'+manifest_rel], cwd=ROOT):
        raise ValueError('Runner manifest bytes differ from frozen commit')
    if (manifest.get('schema') != 'hypergap_full500_v1' or manifest['solver_commit'] != SOLVER
            or summary['solver_commit'] != SOLVER or summary['runner_commit'] != RUNNER
            or manifest['solver_module'] != 'src.q2_nikolastarx.adaptive_hypergap_guarded'
            or summary['manifest_sha256'] != sha(manifest_raw)
            or summary['limits'] != manifest['limits']):
        raise ValueError('Frozen source or manifest mismatch')
    ref = manifest['baseline_manifest']
    old_raw = (ROOT / ref['path']).read_bytes()
    if sha(old_raw) != ref['sha256']:
        raise ValueError('Baseline manifest drift')
    old = json.loads(old_raw)
    if old['baseline_commit'] != BASE or old['e2_commit'] != E2:
        raise ValueError('Baseline/E2 identity mismatch')
    if sha((ROOT/'docs/a/source-manifest.json').read_bytes()) != old['source_manifest_sha256']:
        raise ValueError('Official source manifest drift')
    for name, expected in manifest['solver_sources'].items():
        if sha(subprocess.check_output(['git', 'show', SOLVER+':'+name], cwd=ROOT)) != expected:
            raise ValueError('Frozen solver source hash mismatch: '+name)
    if (summary['source']['baseline_manifest_sha256'] != sha(old_raw)
            or summary['source']['e2']['commit'] != E2
            or summary['source']['official_manifest_sha256'] != old['source_manifest_sha256']
            or len(manifest['solver_sources']) != 47):
        raise ValueError('Runtime source identity mismatch')
    if not run_id or len(run_id) > 150 or not run_id.isascii() or not all(c.isalnum() or c in '-_' for c in run_id):
        raise ValueError('Invalid run ID')
    if not source_reference or source_reference.startswith('/') or '..' in Path(source_reference).parts:
        raise ValueError('Portable source reference required')
    if not 1 <= case_start <= case_end <= 100 or case_end-case_start+1 > 10:
        raise ValueError('Case range must be at most ten cases')
    accepted = accepted_by_coordinate(summary, old)
    coordinates = [(f'{case:03d}', core) for case in range(case_start, case_end+1)
                   for core in range(1, 6)]
    if any(key not in accepted for key in coordinates):
        raise ValueError('Selected case range contains a missing/nonaccepted cell')
    if not output_root.is_relative_to(ROOT / 'results/a/q2-nikolastarx'):
        raise ValueError('Output must be in P2 results area')
    if output_root.is_symlink():
        raise ValueError('Output root symlink forbidden')
    for other in output_root.glob('cases-???-???'):
        lo, hi = (int(x) for x in other.name.split('-')[1:])
        if (lo, hi) != (case_start, case_end) and lo <= case_end and case_start <= hi:
            raise ValueError('Overlapping immutable case group')
    baselines = frozen_feed(old)
    specs = {(r['case'], r['cores']): r for r in old['rows']}
    folder = output_root / f'cases-{case_start:03d}-{case_end:03d}'
    if folder.is_symlink():
        raise ValueError('Shard symlink forbidden')
    snapshot_path = folder / 'snapshot.json'
    if snapshot_path.exists():
        prior = read(snapshot_path)
        if (prior['cases'] != [case_start, case_end] or prior['run_id'] != run_id
                or prior['manifest_sha256'] != sha(manifest_raw)
                or prior['source_summary_reference'] != source_reference):
            raise ValueError('Prior immutable snapshot differs')
    records = []
    official = read(ROOT / 'docs/a/source-manifest.json')['official_code_hash']
    for key in coordinates:
        row = accepted[key]
        spec = specs[key]
        case, cores = row['case'], row['cores']
        cell = summary_path.parent / f'{case}-k{cores}'
        archive = folder / f'{case}-k{cores}'
        expected_paths = {'folder': cell.name, 'plan': f'{cell.name}/plan.json',
                          'solver_ledger': f'{cell.name}/online/solver.json',
                          'result': f'{cell.name}/result.json',
                          'trace': f'{cell.name}/trace.json',
                          'log': f'{cell.name}/official.log'}
        if row['paths'] != expected_paths:
            raise ValueError('Cell path mapping differs')
        cell_receipt = read(cell / 'cell.json')
        if {k: v for k, v in cell_receipt.items()
            if k not in ('solver_process_in_flight', 'independent_e0_in_flight')} != row:
            raise ValueError('Compact/cell receipt mismatch')
        plan_raw = (cell / 'plan.json').read_bytes()
        result_raw = (cell / 'result.json').read_bytes()
        if sha(plan_raw) != row['plan_sha256'] or sha(result_raw) != row['official']['result_sha256']:
            raise ValueError('Raw plan/result hash mismatch')
        result = json.loads(result_raw)
        process = read(cell / 'solver-process/process.json')
        e0_process = read(cell / 'e0-process/process.json')
        ledger_raw = (cell / 'online/solver.json').read_bytes()
        ledger = json.loads(ledger_raw)
        if sha(ledger_raw) != row['solver_ledger_sha256']:
            raise ValueError('Online ledger hash mismatch')
        if (process['status'] != 'ok' or e0_process['status'] != 'ok'
                or process.get('surviving_pids') or e0_process.get('surviving_pids')
                or process['wall_seconds'] != row['solver_process']['wall_seconds']
                or e0_process['wall_seconds'] != row['e0_process']['wall_seconds']
                or process['observed_peak_rss_bytes'] != row['solver_process']['observed_peak_rss_bytes']
                or e0_process['observed_peak_rss_bytes'] != row['e0_process']['observed_peak_rss_bytes']
                or row['solver_process']['status'] != 'ok' or row['e0_process']['status'] != 'ok'
                or row['solver_process']['path'] != f'{cell.name}/solver-process/process.json'
                or row['e0_process']['path'] != f'{cell.name}/e0-process/process.json'
                or result['makespan'] != row['official']['makespan']
                or result['num_cores'] != cores or result['scene'] != 'B'
                or result['data_movement_bytes'] != row['official']['movement']
                or result['cross_task_traffic'] != row['official']['cross_task_traffic']):
            raise ValueError('Accepted row differs from raw evidence')
        calls, attempts = ledger['calls'], ledger['attempts']
        if (ledger['status'] != 'ok' or ledger['request_in_flight']
                or ledger['solver_checkout_commit'] != RUNNER
                or ledger['graph_sha256'] != spec['graph']['sha256']
                or ledger['config_sha256'] != old['config']['sha256']
                or ledger['cores'] != cores or ledger['plan_sha256'] != sha(plan_raw)
                or calls['E2_api_attempted'] != len(attempts)
                or calls['native_returns'] != len(attempts) or len(attempts) > 3
                or calls['E0_fallback'] or ledger['possible_E0_fallback_calls']
                or row['calls']['E2_api_attempted'] != len(attempts)
                or row['calls']['E0_independent_started'] != 1
                or row['calls']['native_returns'] != len(attempts)
                or row['calls']['E0_fallback_confirmed']
                or row['calls']['E0_fallback_possible']
                or row['request_in_flight']
                or ledger.get('detail', {}).get('score_evidence') == 'unknown'
                or any(a.get('status') != 'native' or not isinstance(a.get('record'), dict)
                       or a['record'].get('route') != 'native'
                       or a['record'].get('status') != 'ok' or a['record'].get('problem') != 2
                       for a in attempts)):
            raise ValueError('Online E2/call ledger mismatch')
        expected_sources = {Path(p).name: h for p, h in manifest['solver_sources'].items()}
        expected_sources['hypergap_full500.py'] = sha(subprocess.check_output(
            ['git', 'show', RUNNER+':src/q2_nikolastarx/hypergap_full500.py'], cwd=ROOT))
        if ledger['solver_source_sha256'] != expected_sources:
            raise ValueError('Runtime source hashes differ')
        if attempts and (not ledger['source_checked']
                         or ledger['source']['commit'] != E2
                         or ledger['source']['manifest_sha256'] != old['e2_manifest']['sha256']
                         or ledger['source']['native_binary_sha256'] !=
                            summary['source']['e2']['native_binary_sha256']):
            raise ValueError('E2 source readback differs')
        plan = json.loads(plan_raw)
        canonical = sha(json.dumps(plan, sort_keys=True, allow_nan=False).encode())
        old_plan = pinned(spec['baseline_plan'])
        old_truth = pinned(spec['baseline_truth'])
        if attempts:
            first = attempts[0]
            if first['plan_sha256'] != sha(json.dumps(old_plan, sort_keys=True, allow_nan=False).encode()) or not matching_metrics(first['record'], old_truth):
                raise ValueError('First E2 baseline differs')
            selected_records = [a['record'] for a in attempts if a['plan_sha256'] == canonical]
            if len(selected_records) != 1 or not matching_metrics(selected_records[0], result):
                raise ValueError('Selected E2 score differs from independent E0')
        elif (plan['node_to_subgraph'] != old_plan['node_to_subgraph']
              or plan['core_schedules'] != old_plan['core_schedules']
              or not matching_metrics(old_truth, result)):
            raise ValueError('Zero-call plan differs from frozen baseline')
        base = baselines[(case, cores)]['baseline']
        if (base['route'] != 'E0' or base['graph_sha256'] != spec['graph']['sha256']
                or base['config_sha256'] != old['config']['sha256']
                or base['official_sha256'] != official):
            raise ValueError('Single-core denominator identity differs')
        base_path = ROOT / base['result']['path']
        if sha(base_path.read_bytes()) != base['result']['sha256']:
            raise ValueError('Single-core denominator artifact differs')
        cell_raw = (cell/'cell.json').read_bytes()
        process_raw = (cell/'solver-process/process.json').read_bytes()
        e0_raw = (cell/'e0-process/process.json').read_bytes()
        evidence = {
            'cell_receipt': sanitized_receipt(cell_raw, archive / 'cell.json'),
            'solver_process': sanitized_receipt(process_raw, archive / 'solver-process.json'),
            'e0_process': sanitized_receipt(e0_raw, archive / 'e0-process.json'),
            'online_ledger': sanitized_receipt(ledger_raw, archive / 'online-ledger.json'),
        }
        artifacts = {
            'plan': archive_file(cell / 'plan.json', archive / 'plan.json.gz', pack=True),
            'result': archive_file(cell / 'result.json', archive / 'result.json.gz', pack=True),
            'run': archive_bytes(jbytes({'accepted_row': sanitized(row), 'archived_evidence': evidence,
                                         'original_sha256': {'cell_receipt': sha(cell_raw),
                                                             'solver_process': sha(process_raw),
                                                             'e0_process': sha(e0_raw),
                                                             'online_ledger': sha(ledger_raw)}}), archive / 'run.json'),
        }
        movement = result['data_movement_bytes']
        p = process
        env = {'os': ledger['runtime'].get('platform'), 'cpu': None, 'gpu': None,
               'ram_bytes': None, 'python': ledger['runtime'].get('python'),
               'dependencies': 'frozen solver and E2 source identities in archived online ledger',
               'threads': None, 'workers': manifest['limits']['workers'],
               'peak_rss_bytes': max(p['observed_peak_rss_bytes'], e0_process['observed_peak_rss_bytes'])}
        provenance = {
            'producer_session': producer_session, 'task_url': task_url,
            'solver': {'source': source(SOLVER, 'src/q2_nikolastarx/adaptive_hypergap_guarded.py',
                                        'src.q2_nikolastarx.adaptive_hypergap_guarded.main'),
                       'authors': ['NikolaStarx', 'yuanzhifang30-sudo'],
                       'method': 'Adaptive budget baseline versus bounded hypergap candidates; native E2 selects a complete plan and independent E0 confirms it.',
                       'references': [f'https://github.com/{REPO}/blob/{FANG}/src/q2/feedback/gap_packet.py',
                                      f'https://github.com/{REPO}/blob/{P3_CALENDAR}/src/q3_yuanzhifang/gap_calendar.py'],
                       'upstream': [source(FANG, 'src/q2/feedback/gap_packet.py', None),
                                    source(P3_CALENDAR, 'src/q3_yuanzhifang/gap_calendar.py', None)],
                       'selected_algorithm_id': None,
                       'selected_solver_commit': None},
            'runner': {'source': source(RUNNER, 'src/q2_nikolastarx/hypergap_full500.py',
                                        'src.q2_nikolastarx.hypergap_full500.main'),
                       'argv': sanitized(process['argv']), 'working_directory': '.'},
            'environment': env,
            'measurement': {'started_at': p['started_at'], 'finished_at': p['finished_at'],
                            'seed': None, 'repeat_index': 0, 'cold_start': None,
                            'solver_scope': 'Outer child start through exit includes graph read, candidate construction, online native E2, plan/evidence writes and cleanup.',
                            'evaluation_scope': 'Separate independent official E0 child; its wall is not included in solver wall.',
                            'budget': {'wall_seconds': 60, 'candidate_limit': 3,
                                       'stop_reason': 'completed'},
                            'calls': {'solver': 1, 'E0': 1, 'E1': 0,
                                      'E2': ledger['calls']['E2_api_attempted']},
                            'offline_costs': 'No offline work specific to this case; uses the prebuilt pinned E2 native binary. Earlier compilation/calibration wall is not measured in this run.', 'failure': None},
            'missing_reasons': {
                'provenance.environment.cpu': 'Per-run CPU model was not recorded.',
                'provenance.environment.gpu': 'GPU presence was not recorded.',
                'provenance.environment.ram_bytes': 'Physical RAM size was not recorded.',
                'provenance.environment.threads': 'Thread count was not sampled.',
                'provenance.measurement.seed': 'Deterministic construction; no seed.',
                'provenance.measurement.cold_start': 'Fresh child process, but OS cache state not controlled.',
            },
        }
        record = {
            'attempt_id': f'{run_id}-P2-{case}-k{cores}', 'revision': 1,
            'run_id': run_id, 'algorithm_id': 'q2-adaptive-hypergap-guarded',
            'algorithm_name': 'Adaptive hypergap guarded candidate',
            'variant': 'bounded-hypergap-native-e2-select-independent-e0',
            'solver_commit': SOLVER,
            'parameters': {'global_budget': manifest['limits'], 'candidate_limit': 3,
                           'selection': 'strict_lexicographic_makespan_added_copy_bytes',
                           'retry': False},
            'problem': 'P2', 'case_id': case, 'cores': cores, 'status': 'ok',
            'metrics': {'makespan_cycles': result['makespan'],
                        'solver_wall_seconds': p['wall_seconds'],
                        'evaluation_wall_seconds': e0_process['wall_seconds'],
                        'ddr_bytes': movement['scheduled_copy_bytes'],
                        'extra_ddr_bytes': movement['added_copy_bytes'],
                        'spill_bytes': movement['spill_added_copy_bytes'],
                        'cache_hit_rate': None},
            'evaluator': {'route': 'E0', 'commit': OFFICIAL,
                          'entrypoint': 'multicore_cut_evaluate_problem_2.evaluate_problem_2'},
            'identity': {'graph_sha256': spec['graph']['sha256'],
                         'config_sha256': old['config']['sha256'],
                         'official_sha256': official, 'plan_sha256': artifacts['plan']['sha256']},
            'artifacts': artifacts, 'runtime_id': runtime_id,
            'observed_at': e0_process['finished_at'],
            'timing': {'solver_includes_evaluation': False,
                       'evaluation_precision': 'Outer perf_counter child wall; online E2 is included in solver wall.',
                       'utc': 'UTC'},
            'provenance': provenance,
            'notes': ['One accepted hypergap cell; this case group is not a full500 result.',
                      'Online E2 is selection evidence; independent E0 is final score.',
                      'runner.argv records the actual solver child launched by the frozen batch runner, with local home paths replaced; it is not the batch-launch argv.',
                      'Archived process and ledger receipts are sanitized derivatives; their original raw SHA-256 values are in run.json.',
                      'Single-core denominator is fixed 60afc38 official E0, not the old solver makespan.'],
            'source_url': task_url, 'baseline': base, 'cache_pair': None,
        }
        records.append(record)
    feed = {'schema_version': 1, 'submission_version': 1, 'records': records}
    validate_feed(feed, submission=True)
    snapshot = {'summary_sha256': sha(summary_raw), 'summary_status': summary['status'],
                'accepted_cells': summary['accepted_cells'], 'cases': [case_start, case_end],
                'source_summary_reference': source_reference,
                'manifest_sha256': sha(manifest_raw), 'run_id': run_id}
    if not snapshot_path.exists():
        archive_bytes(jbytes(snapshot), snapshot_path)
    feed_path = folder / 'board-feed.json'
    archive_bytes(jbytes(feed), feed_path)
    return {'feed': str(feed_path.relative_to(ROOT)), 'records': len(records),
            'summary_sha256': sha(summary_raw), 'evaluations': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--summary', required=True, type=Path)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--output-root', required=True, type=Path)
    p.add_argument('--run-id', required=True)
    p.add_argument('--case-range', required=True, help='001-010, inclusive, at most ten cases')
    p.add_argument('--producer-session', required=True)
    p.add_argument('--task-url', required=True)
    p.add_argument('--runtime-id', required=True)
    p.add_argument('--source-reference', required=True)
    args = p.parse_args()
    import re
    if not re.fullmatch(r'\d{3}-\d{3}', args.case_range):
        p.error('--case-range must be NNN-NNN')
    lo, hi = (int(x) for x in args.case_range.split('-'))
    print(json.dumps(export(args.summary.resolve(), args.manifest.resolve(),
                            args.output_root.resolve(), args.run_id, lo, hi,
                            args.producer_session, args.task_url, args.runtime_id,
                            args.source_reference), ensure_ascii=False))


if __name__ == '__main__':
    main()
