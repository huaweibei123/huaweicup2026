"""Frozen 295ec9c P2 full500 Linux producer; preflight has no score calls."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOLVER = '295ec9cf4351b77f5c6fffe8fbb23e8bc8d2f323'
MODULE = 'src.q2_nikolastarx.adaptive_copyevent_guarded'
COORDS = tuple((f'{c:03d}', k) for c in range(1, 101) for k in range(1, 6))
FIELDS = ('original_graph_copy_bytes', 'scheduled_copy_bytes', 'added_copy_bytes',
          'partition_added_copy_bytes', 'spill_added_copy_bytes')
LIMITS = {'cells': 500, 'workers': 2, 'E2_api': 2000,
          'E0_independent': 500, 'solver_seconds': 180, 'e0_seconds': 180,
          'batch_seconds': 7200, 'rss_bytes_per_cell': 4 << 30,
          'rss_bytes_total': 8 << 30, 'retries': 0}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def canonical(plan):
    if not isinstance(plan, dict) or set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('Wrong complete-plan keys')
    return digest(json.dumps(plan, sort_keys=True, allow_nan=False).encode())


def metrics(record, *, official, cores=None):
    if not isinstance(record, dict) or record.get('status') not in (None, 'ok'):
        raise ValueError('Evaluation status unavailable')
    if official and (record.get('scene') != 'B' or record.get('num_cores') != cores):
        raise ValueError('Official scene/core identity mismatch')
    if not official and (record.get('route') != 'native' or record.get('problem') != 2):
        raise ValueError('Online score is not native P2')
    movement = record.get('data_movement_bytes')
    if (type(record.get('makespan')) is not int or record['makespan'] <= 0
            or not isinstance(movement, dict) or set(movement) != set(FIELDS)
            or any(type(movement[k]) is not int or movement[k] < 0 for k in FIELDS)
            or type(record.get('cross_task_traffic')) is not int
            or record['cross_task_traffic'] < 0):
        raise ValueError('Incomplete exact P2 metrics')
    return {'makespan': record['makespan'], 'cross_task_traffic': record['cross_task_traffic'],
            'data_movement_bytes': {k: movement[k] for k in FIELDS}}


def safe_file(relative):
    rel = Path(relative)
    if not relative or rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe capsule path: ' + relative)
    path = (ROOT / rel).resolve(strict=True)
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Capsule path escapes root: ' + relative)
    return path


def preflight():
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        raise ValueError('Requires Linux x86_64')
    manifest_path = ROOT / 'capsule-manifest.json'
    doc = read(manifest_path)
    files, sources = doc.get('files'), doc.get('solver_sources')
    if (doc.get('schema') != 'q2-copyevent-linux-full500-v1'
            or doc.get('solver_source_commit') != SOLVER
            or not re.fullmatch(r'[0-9a-f]{40}', doc.get('runner_source_commit', ''))
            or doc.get('solver_module') != MODULE
            or doc.get('coordinates') != [list(x) for x in COORDS]
            or not isinstance(doc.get('limits'), dict)
            or doc['limits'].get('workers') not in (1, 2)
            or {k: v for k, v in doc['limits'].items() if k != 'workers'} !=
               {k: v for k, v in LIMITS.items() if k != 'workers'}
            or not isinstance(files, dict) or not isinstance(sources, dict)):
        raise ValueError('Capsule algorithm/source identity mismatch')
    required = {'scripts/q2_copyevent_linux_full500.py', 'fixed-p2-manifest.json',
                'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json',
                'docs/a/source-manifest.json',
                'scripts/e2_linux_native.py', 'data/raw/a/official/data/config.txt',
                *(f'data/raw/a/official/data/case_{c:03d}.json' for c in range(1, 101))}
    fixed_path = ROOT / 'fixed-p2-manifest.json'
    fixed = read(fixed_path)
    if len(fixed.get('e2_sources', {})) != 50:
        raise ValueError('E2 source manifest must list 50 fixed files')
    required.update('e2-src/' + p for p in fixed['e2_sources'])
    official_code = {p for p in fixed['e2_sources'] if p.startswith('data/raw/a/official/code/')}
    required.update(official_code)
    if not required <= files.keys():
        raise ValueError('Capsule omits runner, official inputs or E2 sources')
    if sha(ROOT / 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json') != sha(fixed_path):
        raise ValueError('Solver fixed-P2 manifest alias differs')
    for rel, expected in files.items():
        if not re.fullmatch(r'[0-9a-f]{64}', expected) or sha(safe_file(rel)) != expected:
            raise ValueError('Capsule byte drift: ' + rel)
    source_manifest = read(ROOT / 'docs/a/source-manifest.json')
    if doc.get('official_source_manifest_sha256') != sha(ROOT / 'docs/a/source-manifest.json'):
        raise ValueError('Official source manifest pin differs')
    official = {entry['path']: entry for entry in source_manifest['files']}
    selected = {'data/config.txt', *(f'data/case_{c:03d}.json' for c in range(1, 101))}
    selected |= {p.removeprefix('data/raw/a/official/') for p in official_code}
    for relative in selected:
        entry = official.get(relative)
        actual = ROOT / 'data/raw/a/official' / relative
        if (entry is None or not actual.is_file() or sha(actual) != entry['sha256']
                or actual.stat().st_size != entry['bytes']):
            raise ValueError('Official source-manifest mismatch: ' + relative)
    code_hash = digest(''.join(f'{p}\t{official[p]["sha256"]}\n'
                               for p in sorted(official) if p.startswith('code/')).encode())
    if code_hash != source_manifest.get('official_code_hash') or code_hash != doc.get('official_code_hash'):
        raise ValueError('Official code identity mismatch')
    for rel, expected in fixed['e2_sources'].items():
        if files.get('e2-src/' + rel) != expected:
            raise ValueError('Fixed E2 source differs: ' + rel)
    source_prefix = 'src/q2_nikolastarx/'
    listed = {k: v for k, v in files.items() if k.startswith(source_prefix) and k.endswith('.py')}
    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / source_prefix).rglob('*.py')}
    if (not sources or sources != listed or actual != set(sources)
            or 'src/q2_nikolastarx/adaptive_copyevent_guarded.py' not in sources):
        raise ValueError('Frozen algorithm package file set/hash mismatch')
    baseline_ref = doc.get('singlecore_baseline')
    if (not isinstance(baseline_ref, dict) or set(baseline_ref) != {'path', 'sha256'}
            or files.get(baseline_ref['path']) != baseline_ref['sha256']):
        raise ValueError('Fixed single-core baseline artifact identity absent')
    baseline_artifact = read(safe_file(baseline_ref['path']))
    rows = baseline_artifact.get('records') if isinstance(baseline_artifact, dict) else None
    if (not isinstance(rows, list) or len(rows) != 100
            or baseline_artifact.get('scope') != 'report-only official single-core denominators; no solver input'):
        raise ValueError('Fixed 100-case single-core baseline absent')
    baselines = {}
    for row in rows:
        case, value = row.get('case'), row.get('makespan')
        if (case in baselines or case not in {f'{c:03d}' for c in range(1, 101)}
                or type(value) is not int or value <= 0
                or row.get('graph_sha256') != files[f'data/raw/a/official/data/case_{case}.json']
                or row.get('config_sha256') != files['data/raw/a/official/data/config.txt']
                or not isinstance(row.get('result'), dict)
                or not re.fullmatch(r'[0-9a-f]{64}', row['result'].get('sha256', ''))):
            raise ValueError('Single-core baseline row identity mismatch')
        baselines[case] = value
    if set(baselines) != {f'{c:03d}' for c in range(1, 101)}:
        raise ValueError('Single-core baseline coverage mismatch')
    doc['baseline_provenance'] = {k: baseline_artifact[k] for k in
                                  ('source_commit', 'feed_path', 'feed_sha256')}
    doc['singlecore_baseline_m'] = baselines
    identity = read(ROOT / 'runtime-identity.json')
    receipt = ROOT / 'e2-linux-build.json'
    receipt_sha, binary_sha = identity.get('linux_receipt_sha256'), identity.get('linux_binary_sha256')
    binary = ROOT / 'e2-src' / fixed['binary']['path']
    if (not re.fullmatch(r'[0-9a-f]{64}', receipt_sha or '')
            or not re.fullmatch(r'[0-9a-f]{64}', binary_sha or '')
            or sha(receipt) != receipt_sha or sha(binary) != binary_sha
            or read(receipt).get('binary', {}).get('sha256') != binary_sha):
        raise ValueError('Linux receipt/binary identity mismatch')
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from src.q2_nikolastarx.adaptive_guarded import check_e2_source
    from src.q2_nikolastarx.evaluate_feedback import monitored
    e2 = check_e2_source(ROOT / 'e2-src', linux_build_receipt=receipt,
                         linux_build_receipt_sha256=receipt_sha, linux_binary_sha256=binary_sha)
    if e2['native_binary_sha256'] != binary_sha:
        raise ValueError('E2 preflight binary readback mismatch')
    runtime_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    return doc, identity, e2, monitored, runtime_head, sha(manifest_path)


def inspect_solver(folder, case, cores, process, sources, e2):
    ledger_path = folder / 'online/solver.json'
    if not ledger_path.exists():
        raise ValueError('Solver ledger absent; E2 count unknown')
    ledger = read(ledger_path)
    calls, attempts = ledger.get('calls', {}), ledger.get('attempts', [])
    if (process.get('status') != 'ok' or process.get('surviving_pids')
            or ledger.get('status') != 'ok' or ledger.get('request_in_flight')
            or type(calls.get('E2_api_attempted')) is not int
            or not 0 <= calls['E2_api_attempted'] <= 4
            or len(attempts) != calls['E2_api_attempted']
            or calls.get('native_returns') != len(attempts)
            or calls.get('E0_fallback') != 0 or calls.get('E0') != 0
            or ledger.get('possible_E0_fallback_calls') != 0
            or any(a.get('status') != 'native' for a in attempts)):
        raise ValueError('Solver failed, fallback, over cap or E2 outcome unknown')
    if (ledger.get('source_checked') != bool(attempts)
            or (attempts and any(ledger.get('source', {}).get(k) != e2[k]
                                 for k in ('commit', 'manifest_sha256', 'native_binary_sha256')))):
        raise ValueError('Online E2 source identity differs from preflight')
    expected_hashes = {Path(p).name: h for p, h in sources.items()}
    if (ledger.get('solver_source_sha256') != expected_hashes
            or ledger.get('graph_sha256') != sha(ROOT / f'data/raw/a/official/data/case_{case}.json')
            or ledger.get('config_sha256') != sha(ROOT / 'data/raw/a/official/data/config.txt')
            or ledger.get('cores') != cores):
        raise ValueError('Solver runtime input/source readback mismatch')
    detail = ledger.get('detail')
    base = detail.get('base_detail') if isinstance(detail, dict) else None
    if (not isinstance(base, dict) or detail.get('score_evidence') == 'unknown'
            or base.get('score_evidence') == 'unknown'
            or any(x.get('kind') == 'unexpected' for x in base.get('construction_errors', []))
            or (isinstance(detail.get('postprocess_error'), dict)
                and detail['postprocess_error'].get('kind') == 'unexpected')):
        raise ValueError('Unknown or unexpected route detail')
    plan_path = folder / 'plan.json'
    if sha(plan_path) != ledger.get('plan_sha256'):
        raise ValueError('Selected plan byte hash differs from ledger')
    plan = read(plan_path)
    if len(plan.get('core_schedules', [])) != cores:
        raise ValueError('Selected plan core count mismatch')
    key = canonical(plan)
    selected = [a['record'] for a in attempts if a.get('plan_sha256') == key]
    if attempts:
        if (detail.get('score_evidence') != 'injected_oracle_complete_plan_scores'
                or len(selected) != 1):
            raise ValueError('Selected plan lacks unique native E2 score')
        score = metrics(selected[0], official=False)
        route = 'selected_native'
    else:
        if (base.get('score_evidence') != 'not_requested'
                or base.get('unique_plans') != 1 or detail.get('selected') != 'base'
                or detail.get('score_evidence') != 'not_requested'):
            raise ValueError('Zero E2 allowed only for one-plan structural route')
        score, route = None, 'single_plan_independent_E0_only'
    return ledger, score, route


def cell(case, cores, doc, identity, e2, monitored, output, deadline):
    folder = output / f'{case}-k{cores}'
    folder.mkdir(exist_ok=False)
    row = {'case': case, 'cores': cores, 'status': 'running',
           'calls': {'solver_started': 1, 'E2_api_attempted': None,
                     'native_returns': None, 'E0_fallback_possible': None,
                     'E0_independent_started': 0},
           'paths': {'folder': folder.relative_to(output).as_posix(),
                     'plan': (folder / 'plan.json').relative_to(output).as_posix(),
                     'solver_ledger': (folder / 'online/solver.json').relative_to(output).as_posix(),
                     'result': (folder / 'result.json').relative_to(output).as_posix()}}
    save(folder / 'cell.json', row)
    try:
        graph = ROOT / f'data/raw/a/official/data/case_{case}.json'
        config = ROOT / 'data/raw/a/official/data/config.txt'
        cmd = [sys.executable, '-B', '-m', MODULE, str(graph), '--config', str(config),
               '--cores', str(cores), '--output', str(folder / 'plan.json'),
               '--evidence', str(folder / 'online'), '--e2-root', str(ROOT / 'e2-src'),
               '--linux-build-receipt', str(ROOT / 'e2-linux-build.json'),
               '--linux-build-receipt-sha256', identity['linux_receipt_sha256'],
               '--linux-binary-sha256', identity['linux_binary_sha256'], '--wall', '180']
        row['solver_process_in_flight'] = True
        save(folder / 'cell.json', row)
        process = monitored(cmd, folder / 'solver-process', min(deadline, time.perf_counter() + 180),
                            LIMITS['rss_bytes_per_cell'])
        row['solver_process_in_flight'] = False
        row['solver_process'] = {k: process.get(k) for k in
            ('status', 'wall_seconds', 'observed_peak_rss_bytes', 'surviving_pids')}
        row['solver_process']['path'] = (folder / 'solver-process/process.json').relative_to(output).as_posix()
        ledger_path = folder / 'online/solver.json'
        if ledger_path.exists():
            ledger = read(ledger_path)
            calls = ledger.get('calls', {})
            row['calls'].update(E2_api_attempted=calls.get('E2_api_attempted'),
                                native_returns=calls.get('native_returns'),
                                E0_fallback_possible=ledger.get('possible_E0_fallback_calls'))
            row['request_in_flight'] = ledger.get('request_in_flight')
            row['call_count_complete'] = (ledger.get('request_in_flight') is False
                                          and type(calls.get('E2_api_attempted')) is int
                                          and ledger.get('possible_E0_fallback_calls') ==
                                          calls.get('E0_fallback'))
            row['solver_ledger_sha256'] = sha(ledger_path)
        else:
            row['call_count_complete'] = False
        save(folder / 'cell.json', row)
        ledger, score, route = inspect_solver(folder, case, cores, process,
                                              doc['solver_sources'], e2)
        row['selected_comparison_kind'] = route
        row['selected_E2'] = score
        row['plan_sha256'] = sha(folder / 'plan.json')
        row['solver_wall_seconds'] = process['wall_seconds']
        if time.perf_counter() >= deadline:
            raise TimeoutError('Batch deadline before independent E0')
        row['calls']['E0_independent_started'] = 1
        row['independent_e0_in_flight'] = True
        save(folder / 'cell.json', row)
        e0_cmd = [sys.executable, '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                  str(graph), str(folder / 'plan.json'), '--config', str(config),
                  '--output', str(folder / 'result.json'),
                  '--trace-output', str(folder / 'trace.json'),
                  '--log-output', str(folder / 'official.log')]
        result_process = monitored(e0_cmd, folder / 'e0-process',
                                   min(deadline, time.perf_counter() + 180),
                                   LIMITS['rss_bytes_per_cell'])
        row['independent_e0_in_flight'] = False
        row['e0_process'] = {k: result_process.get(k) for k in
            ('status', 'wall_seconds', 'observed_peak_rss_bytes', 'surviving_pids')}
        row['e0_process']['path'] = (folder / 'e0-process/process.json').relative_to(output).as_posix()
        if result_process.get('status') != 'ok' or result_process.get('surviving_pids'):
            raise ValueError('Independent E0 failed/uncertain')
        official = metrics(read(folder / 'result.json'), official=True, cores=cores)
        if score is not None and score != official:
            raise ValueError('Selected native E2 and independent E0 differ')
        row['official'] = official
        row['result_sha256'] = sha(folder / 'result.json')
        row['singlecore_baseline_m'] = doc['singlecore_baseline_m'][case]
        row['speedup'] = row['singlecore_baseline_m'] / official['makespan']
        row['status'] = 'accepted'
    except Exception as error:
        row.update(status='stopped', error=repr(error))
    finally:
        save(folder / 'cell.json', row)
    return row


def run(doc, identity, e2, monitored, manifest_sha, runtime_head, output):
    if output.exists():
        raise ValueError('Output exists; no resume or repeat')
    started = time.perf_counter()
    deadline = started + LIMITS['batch_seconds']
    output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'running', 'solver_commit': SOLVER,
               'runner_source_commit': doc['runner_source_commit'],
               'capsule_runtime_head': runtime_head, 'capsule_sha256': manifest_sha,
               'linux_receipt_sha256': identity['linux_receipt_sha256'],
               'native_binary_sha256': identity['linux_binary_sha256'],
               'limits': doc['limits'], 'accepted_cells': 0, 'rows': [], 'in_flight': [],
               'calls': {'solver_started': 0, 'E2_api_attempted': 0,
                         'native_returns': 0, 'E0_independent_started': 0},
               'call_count_complete': True,
               'scope': 'one frozen algorithm, 100x1-5; only 500 accepted cells is full coverage',
               'baseline_scope': 'fixed 100-case single-core M only; no old-plan first-native comparison'}
    summary['baseline_provenance'] = doc['baseline_provenance']
    summary['singlecore_baseline_sha256'] = doc['singlecore_baseline']['sha256']
    save(output / 'summary.json', summary)
    next_index, stop, running = 0, False, {}
    with ThreadPoolExecutor(max_workers=doc['limits']['workers']) as pool:
        while next_index < len(COORDS) or running:
            while (not stop and next_index < len(COORDS)
                   and len(running) < doc['limits']['workers'] and time.perf_counter() < deadline):
                case, cores = COORDS[next_index]
                next_index += 1
                key = f'{case}-k{cores}'
                summary['in_flight'].append(key)
                summary['calls']['solver_started'] += 1
                save(output / 'summary.json', summary)
                running[pool.submit(cell, case, cores, doc, identity, e2, monitored,
                                    output, deadline)] = key
            if not running:
                break
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in done:
                key = running.pop(future)
                try:
                    entry = future.result()
                except Exception as error:
                    entry = {'case': key.split('-')[0], 'cores': int(key.split('k')[1]),
                             'status': 'stopped', 'error': 'Worker raised: '+repr(error),
                             'calls': {'E2_api_attempted': None, 'native_returns': None,
                                       'E0_independent_started': None}}
                summary['in_flight'].remove(key)
                summary['rows'].append({k: v for k, v in entry.items()
                                        if k not in ('solver_process_in_flight', 'independent_e0_in_flight')})
                for name in ('E2_api_attempted', 'native_returns', 'E0_independent_started'):
                    value = entry.get('calls', {}).get(name)
                    if type(value) is int:
                        summary['calls'][name] += value
                    else:
                        summary['call_count_complete'] = False
                if entry['status'] != 'accepted':
                    stop = True
                    summary['status'] = 'stopped_first_failure'
                else:
                    summary['accepted_cells'] += 1
                if entry.get('call_count_complete') is False:
                    summary['call_count_complete'] = False
                if (summary['calls']['E2_api_attempted'] > LIMITS['E2_api']
                        or summary['calls']['E0_independent_started'] > LIMITS['E0_independent']):
                    stop = True
                    summary['status'] = 'stopped_budget_exceeded'
                summary['total_wall_seconds'] = time.perf_counter() - started
                save(output / 'summary.json', summary)
        summary['total_wall_seconds'] = time.perf_counter() - started
        if not stop and summary['accepted_cells'] == 500:
            summary['status'] = 'completed'
        elif summary['status'] == 'running':
            summary['status'] = 'stopped_incomplete_or_deadline'
        save(output / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'run'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    doc, identity, e2, monitored, runtime_head, manifest_sha = preflight()
    if args.mode == 'preflight':
        print(json.dumps({'status': 'preflight_ok', 'cells': 500, 'calls': 0,
                          'upstream_solver': SOLVER, 'capsule_runtime_head': runtime_head}))
        return
    if args.output is None:
        parser.error('run needs --output')
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT.resolve()):
        raise ValueError('Write results outside fixed capsule root')
    summary = run(doc, identity, e2, monitored, manifest_sha, runtime_head, output)
    if summary['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
