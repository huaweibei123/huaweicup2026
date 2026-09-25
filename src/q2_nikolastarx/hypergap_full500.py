"""Manifest-worker frozen P2 hypergap batch. Preflight never scores.

Run requires a separately frozen manifest and explicit scheduling release. Every
cell keeps full originals; summary.json contains only compact receipts.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from .adaptive_guarded import check_e2_source
from .chain_pilot import FIELDS, git_bytes, pinned, save
from .evaluate_feedback import monitored

ROOT = Path(__file__).resolve().parents[2]
COORDS = tuple((f'{c:03d}', k) for c in range(1, 101) for k in range(1, 6))
LIMITS = {'cells': 500, 'workers': 4, 'E2_api': 1500,
          'E0_fallback_reserved': 1500, 'E0_independent': 500,
          'solver_seconds': 60, 'e0_seconds': 60, 'batch_seconds': 7200,
          'rss_bytes_per_cell': 4 << 30, 'retries': 0}
ROUTES = {
    'hypergap_full500_v1': ('src.q2_nikolastarx.adaptive_hypergap_guarded', 3),
    'copyevent_full500_v1': ('src.q2_nikolastarx.adaptive_copyevent_guarded', 4),
}


def route_limits(schema):
    if schema not in ROUTES:
        raise ValueError('Unknown fixed P2 full500 route')
    _, requests = ROUTES[schema]
    return {**LIMITS, 'E2_api': 500 * requests,
            'E0_fallback_reserved': 500 * requests}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(plan):
    return digest(json.dumps(plan, sort_keys=True, allow_nan=False).encode())


def same_metrics(a, b):
    return (a['makespan'] == b['makespan']
            and a['cross_task_traffic'] == b['cross_task_traffic']
            and all(a['data_movement_bytes'][key] == b['data_movement_bytes'][key]
                    for key in FIELDS))


def import_preflight(python, e2_root):
    """Load E2 modules with the chosen venv; never construct/evaluate a scene."""
    code = '''import json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
import numpy
import research.a.e2_search as package
import research.a.e2_search.scene_b as scene_b
import src.eval_exact._official as official
modules = (package, scene_b, official)
if any(not pathlib.Path(m.__file__).resolve().is_relative_to(root) for m in modules):
    raise RuntimeError("foreign E2 import")
print(json.dumps({"python": sys.executable, "numpy": numpy.__version__,
                  "modules": [str(pathlib.Path(m.__file__).resolve()) for m in modules]}))
'''
    result = subprocess.run([str(python), '-B', '-c', code, str(e2_root)],
                            text=True, capture_output=True, timeout=10)
    if result.returncode:
        raise RuntimeError(f'E2 import preflight failed: returncode={result.returncode}; '
                           f'stdout={result.stdout!r}; stderr={result.stderr!r}')
    return json.loads(result.stdout)


def source_preflight(doc, runner_commit, frozen):
    commit = doc.get('solver_commit')
    if not commit:
        if frozen or doc.get('solver_sources'):
            raise ValueError('Run requires a frozen solver source set')
        return
    if len(commit) != 40 or (frozen and (not runner_commit or len(runner_commit) != 40)):
        raise ValueError('Full solver and runner commits required')
    own = Path(__file__).relative_to(ROOT).as_posix()
    if frozen:
        manifest_path = doc['_manifest_path'].relative_to(ROOT).as_posix()
        for relative in (own, 'src/q2_nikolastarx/evaluate_feedback.py',
                         'src/q2_nikolastarx/chain_pilot.py',
                         manifest_path):
            if (ROOT / relative).read_bytes() != git_bytes(runner_commit, relative):
                raise ValueError('Runner/manifest/monitor drift: ' + relative)
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit,
                                     'src/q2_nikolastarx'], cwd=ROOT, text=True).splitlines()
    paths = sorted(p for p in paths if p.endswith('.py'))
    source_paths = set(paths) - {own}
    if (not paths or source_paths != set(doc['solver_sources'])
            or doc['solver_module'].replace('.', '/') + '.py' not in paths):
        raise ValueError('Frozen solver source set/module mismatch')
    actual = sorted(p.relative_to(ROOT).as_posix()
                    for p in (ROOT / 'src/q2_nikolastarx').glob('*.py'))
    if actual != sorted(set(paths) | {own}):
        raise ValueError('Solver checkout file set differs from freeze')
    for relative in sorted(source_paths):
        raw = (ROOT / relative).read_bytes()
        if digest(raw) != doc['solver_sources'][relative] or raw != git_bytes(commit, relative):
            raise ValueError('Solver source drift: ' + relative)


def preflight(manifest, raw_root, e2_root, python, runner_commit=None, frozen=False):
    doc = json.loads(manifest.read_bytes())
    limits = doc.get('limits')
    schema = doc.get('schema')
    if (schema not in ROUTES or not isinstance(limits, dict)
            or type(limits.get('workers')) is not int or limits['workers'] not in (1, 2, 4)
            or {k: v for k, v in limits.items() if k != 'workers'} !=
               {k: v for k, v in route_limits(schema).items() if k != 'workers'}
            or doc.get('solver_module') != ROUTES[schema][0]):
        raise ValueError('Unexpected algorithm, schema or batch budget')
    doc['_manifest_path'] = manifest
    if not python.is_file() or Path(sys.executable).absolute() != python.absolute():
        raise ValueError('Parent must use requested venv Python entry, without resolving symlink')
    source_preflight(doc, runner_commit, frozen)
    ref = doc['baseline_manifest']
    old_raw = (ROOT / ref['path']).read_bytes()
    if digest(old_raw) != ref['sha256']:
        raise ValueError('Frozen baseline manifest changed')
    old = json.loads(old_raw)
    if (old['solver_commit'] != '923b25ecb0b9d6d0e2d3f149fccef431b5403f99'
            or old['baseline_commit'] != '60afc38b327680fbda0ff10182e3e05a01edd72d'
            or old['coordinates'] != [list(x) for x in COORDS]
            or len(old['rows']) != 500):
        raise ValueError('Baseline manifest identity/coverage mismatch')
    e2 = check_e2_source(e2_root)
    if (e2['commit'] != old['e2_commit']
            or e2['manifest_sha256'] != old['e2_manifest']['sha256']):
        raise ValueError('E2 source mismatch')
    imports = import_preflight(python, e2_root)
    source_raw = (ROOT / 'docs/a/source-manifest.json').read_bytes()
    if digest(source_raw) != old['source_manifest_sha256']:
        raise ValueError('Official manifest drift')
    official = json.loads(source_raw)
    files = {f['path']: f for f in official['files']}
    for rel in (*old['official_files'], 'data/config.txt',
                *(f'data/case_{c:03d}.json' for c in range(1, 101))):
        path = raw_root / rel
        raw = path.read_bytes()
        if digest(raw) != files[rel]['sha256'] or len(raw) != files[rel]['bytes']:
            raise ValueError('Official raw mismatch: ' + rel)
        if rel.startswith('code/'):
            local = (ROOT / 'data/raw/a/official' / rel).read_bytes()
            if local != raw:
                raise ValueError('Imported official code differs from --raw-root: ' + rel)
    if old['config']['sha256'] != files['data/config.txt']['sha256']:
        raise ValueError('Official config identity mismatch')
    feed = pinned(old['baseline_feed'])['records']
    by_cell = {(r['case_id'], r['cores']): r for r in feed}
    if len(by_cell) != 500:
        raise ValueError('Baseline feed lacks 500 unique cells')
    for row, (case, cores) in zip(old['rows'], COORDS):
        if (row['case'], row['cores']) != (case, cores):
            raise ValueError('Baseline row order mismatch')
        graph = files[f'data/case_{case}.json']['sha256']
        baseline = by_cell.get((case, cores))
        if (row['graph']['sha256'] != graph or baseline is None
                or baseline['identity']['graph_sha256'] != graph
                or baseline['identity']['config_sha256'] != old['config']['sha256']
                or baseline['identity']['official_sha256'] != official['official_code_hash']
                or baseline['artifacts']['plan'] != {k: row['baseline_plan'][k] for k in ('path','sha256')}
                or baseline['artifacts']['result'] != {k: row['baseline_truth'][k] for k in ('path','sha256')}
                or baseline['metrics']['makespan_cycles'] != row['baseline_m']):
            raise ValueError('Baseline feed identity mismatch: ' + case)
        plan, truth = pinned(row['baseline_plan']), pinned(row['baseline_truth'])
        if (set(plan) != {'node_to_subgraph','core_schedules'}
                or len(plan['core_schedules']) != cores or truth['scene'] != 'B'
                or truth['num_cores'] != cores or truth['makespan'] != row['baseline_m']
                or set(truth['data_movement_bytes']) != set(FIELDS)):
            raise ValueError('Frozen baseline artifacts mismatch: ' + case)
    return doc, old, {'e2': e2, 'e2_imports': imports,
                      'official_manifest_sha256': digest(source_raw),
                      'baseline_manifest_sha256': digest(old_raw)}


def inspect_solver(folder, row, process, baseline, e2_identity, max_requests=3):
    ledger_path = folder / 'online/solver.json'
    if not ledger_path.exists():
        raise ValueError('Solver ledger missing; calls unknown')
    ledger = json.loads(ledger_path.read_bytes())
    if (process['status'] != 'ok' or process.get('surviving_pids')
            or ledger.get('status') != 'ok' or ledger.get('request_in_flight')):
        raise ValueError('Solver process or ledger failed/uncertain')
    calls, attempts = ledger['calls'], ledger['attempts']
    if (calls['E2_api_attempted'] != len(attempts)
            or calls['native_returns'] != len(attempts) or len(attempts) > max_requests
            or calls['E0_fallback'] or ledger['possible_E0_fallback_calls']
            or any(a.get('status') != 'native' or a.get('record', {}).get('route') != 'native'
                   or a['record'].get('status') != 'ok' or a['record'].get('problem') != 2
                   for a in attempts)):
        raise ValueError('Fallback, unknown or excess E2 request')
    if attempts and (ledger.get('source_checked') is not True
                     or not isinstance(ledger.get('source'), dict)
                     or any(ledger['source'].get(key) != e2_identity[key]
                            for key in ('commit', 'manifest_sha256', 'native_binary_sha256'))):
        raise ValueError('Online E2 source readback differs from preflight')
    detail = ledger.get('detail')
    if (not isinstance(detail, dict) or detail.get('score_evidence') == 'unknown'
            or (attempts and detail.get('score_evidence') !=
                'injected_oracle_complete_plan_scores')):
        raise ValueError('Solver score evidence unavailable')
    base_detail = detail.get('base_detail', detail)
    if not isinstance(base_detail, dict):
        raise ValueError('Nested base detail missing')
    if (base_detail.get('score_evidence') == 'unknown'
            or any(item.get('kind') == 'unexpected'
                   for item in base_detail.get('construction_errors', []))
            or (isinstance(detail.get('postprocess_error'), dict)
                and detail['postprocess_error'].get('kind') == 'unexpected')):
        raise ValueError('Unexpected candidate construction error')
    if (ledger.get('graph_sha256') != row['graph']['sha256']
            or ledger.get('config_sha256') != baseline['config']['sha256']
            or ledger.get('cores') != row['cores']):
        raise ValueError('Solver input readback mismatch')
    expected = {Path(p).name: h for p, h in baseline['_new_sources'].items()}
    expected['hypergap_full500.py'] = baseline['_runner_source_hash']
    if ledger.get('solver_source_sha256') != expected:
        raise ValueError('Solver runtime source mismatch')
    raw = (folder / 'plan.json').read_bytes()
    if digest(raw) != ledger.get('plan_sha256'):
        raise ValueError('Selected plan bytes mismatch')
    plan = json.loads(raw)
    if set(plan) != {'node_to_subgraph','core_schedules'} or len(plan['core_schedules']) != row['cores']:
        raise ValueError('Selected plan invalid')
    key = canonical(plan)
    old_plan, old_truth = pinned(row['baseline_plan']), pinned(row['baseline_truth'])
    if attempts:
        first = attempts[0]
        if first['plan_sha256'] != canonical(old_plan) or not same_metrics(first['record'], old_truth):
            raise ValueError('First native baseline differs from frozen truth')
    selected = [a for a in attempts if a['plan_sha256'] == key]
    if selected:
        if len(selected) != 1:
            raise ValueError('Ambiguous selected native score')
        score = selected[0]['record']
        route = 'selected_native'
    else:
        if attempts or plan != old_plan:
            raise ValueError('Unscored selected plan differs from frozen baseline')
        score = old_truth
        route = 'frozen_baseline_zero_score'
    return ledger, {'kind': route, 'record': score,
                    'selected_plan_canonical_sha256': key, 'plan_sha256': digest(raw)}


def cell(row, doc, old, identity, raw_root, e2_root, python, output, deadline):
    from .evaluate_feedback import monitored
    folder = output / f"{row['case']}-k{row['cores']}"
    folder.mkdir(exist_ok=False)
    receipt = {'case': row['case'], 'cores': row['cores'], 'status': 'running',
               'graph_sha256': row['graph']['sha256'],
               'config_sha256': old['config']['sha256'],
               'baseline_plan_sha256': row['baseline_plan']['sha256'],
               'paths': {'folder': folder.relative_to(output).as_posix(),
                         'plan': (folder / 'plan.json').relative_to(output).as_posix(),
                         'solver_ledger': (folder / 'online/solver.json').relative_to(output).as_posix(),
                         'result': (folder / 'result.json').relative_to(output).as_posix(),
                         'trace': (folder / 'trace.json').relative_to(output).as_posix(),
                         'log': (folder / 'official.log').relative_to(output).as_posix()},
               'calls': {'E2_api_attempted': 0, 'native_returns': 0,
                         'E0_fallback_confirmed': 0, 'E0_fallback_possible': 0,
                         'E0_independent_started': 0}}
    save(folder / 'cell.json', receipt)
    try:
        graph = raw_root / 'data' / f"case_{row['case']}.json"
        config = raw_root / 'data/config.txt'
        argv = [str(python), '-B', '-m', doc['solver_module'], str(graph),
                '--config', str(config), '--cores', str(row['cores']),
                '--output', str(folder / 'plan.json'), '--evidence', str(folder / 'online'),
                '--e2-root', str(e2_root), '--wall', '60']
        receipt['solver_process_in_flight'] = True
        save(folder / 'cell.json', receipt)
        process = monitored(argv, folder / 'solver-process', min(deadline, time.perf_counter()+60),
                            LIMITS['rss_bytes_per_cell'])
        receipt['solver_process_in_flight'] = False
        receipt['solver_process'] = {'status': process['status'], 'wall_seconds': process['wall_seconds'],
                                     'observed_peak_rss_bytes': process['observed_peak_rss_bytes'],
                                     'path': (folder / 'solver-process/process.json').relative_to(output).as_posix()}
        ledger_path = folder / 'online/solver.json'
        if ledger_path.exists():
            ledger = json.loads(ledger_path.read_bytes())
            calls = ledger['calls']
            receipt['calls'].update(E2_api_attempted=calls['E2_api_attempted'],
                                    native_returns=calls['native_returns'],
                                    E0_fallback_confirmed=calls['E0_fallback'],
                                    E0_fallback_possible=ledger['possible_E0_fallback_calls'])
            receipt['request_in_flight'] = ledger['request_in_flight']
            receipt['solver_ledger_sha256'] = digest(ledger_path.read_bytes())
        else:
            receipt['call_count_complete'] = False
        save(folder / 'cell.json', receipt)
        score_ledger, comparison = inspect_solver(folder, row, process, old, identity['e2'],
                                                 ROUTES[doc['schema']][1])
        receipt['selected_comparison_kind'] = comparison['kind']
        receipt['plan_sha256'] = comparison['plan_sha256']
        receipt['selected_plan_canonical_sha256'] = comparison['selected_plan_canonical_sha256']
        if time.perf_counter() >= deadline:
            raise TimeoutError('Batch deadline reached before E0')
        receipt['calls']['E0_independent_started'] = 1
        receipt['independent_e0_in_flight'] = True
        save(folder / 'cell.json', receipt)
        e0_argv = [str(python), '-B', str(raw_root / 'code/multicore_cut_evaluate_problem_2.py'),
                   str(graph), str(folder / 'plan.json'), '--config', str(config),
                   '--output', str(folder / 'result.json'),
                   '--trace-output', str(folder / 'trace.json'),
                   '--log-output', str(folder / 'official.log')]
        e0 = monitored(e0_argv, folder / 'e0-process', min(deadline, time.perf_counter()+60),
                       LIMITS['rss_bytes_per_cell'])
        receipt['independent_e0_in_flight'] = False
        receipt['e0_process'] = {'status': e0['status'], 'wall_seconds': e0['wall_seconds'],
                                 'observed_peak_rss_bytes': e0['observed_peak_rss_bytes'],
                                 'path': (folder / 'e0-process/process.json').relative_to(output).as_posix()}
        if e0['status'] != 'ok' or e0.get('surviving_pids'):
            raise ValueError('Independent E0 failed/uncertain')
        result_raw = (folder / 'result.json').read_bytes()
        result = json.loads(result_raw)
        if not same_metrics(comparison['record'], result):
            raise ValueError('Online/frozen truth differs from independent E0')
        receipt['official'] = {'makespan': result['makespan'],
                               'cross_task_traffic': result['cross_task_traffic'],
                               'movement': {k: result['data_movement_bytes'][k] for k in FIELDS},
                               'result_sha256': digest(result_raw)}
        receipt['baseline'] = {'makespan': row['baseline_m'],
                               'added_copy_bytes': pinned(row['baseline_truth'])['data_movement_bytes']['added_copy_bytes']}
        receipt['status'] = 'accepted'
    except Exception as error:
        receipt.update(status='stopped', error=repr(error))
    finally:
        save(folder / 'cell.json', receipt)
    return receipt


def compact(entry):
    # No plan, trace, official raw object or full online ledger in summary.
    return {k: v for k, v in entry.items() if k not in ('solver_process_in_flight', 'independent_e0_in_flight')}


def run(doc, old, identity, manifest, raw_root, e2_root, python, output, runner_commit, started):
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('Pinned E2 binary requires macOS arm64')
    if output.exists():
        raise ValueError('Output exists; no overwrite/resume/retry')
    old['_new_sources'] = doc['solver_sources']
    old['_runner_source_hash'] = digest(Path(__file__).read_bytes())
    limits = doc['limits']
    deadline = started + limits['batch_seconds']
    output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'running', 'runner_commit': runner_commit,
               'solver_commit': doc['solver_commit'], 'manifest_sha256': digest(manifest.read_bytes()),
               'source': identity, 'limits': limits, 'accepted_cells': 0,
               'rows': [], 'in_flight': [], 'calls': {'solver_started': 0,
               'E2_api_attempted': 0, 'native_returns': 0, 'E0_fallback_confirmed': 0,
               'E0_fallback_possible': 0, 'E0_independent_started': 0},
               'call_count_complete': True,
               'scope': 'one frozen algorithm, 100x1-5; only 500 accepted cells is a full result'}
    save(output / 'summary.json', summary)
    next_index = 0
    running = {}
    stop = False
    with ThreadPoolExecutor(max_workers=limits['workers']) as pool:
        while next_index < len(old['rows']) or running:
            while (not stop and next_index < len(old['rows'])
                   and len(running) < limits['workers'] and time.perf_counter() < deadline):
                row = old['rows'][next_index]
                next_index += 1
                key = f"{row['case']}-k{row['cores']}"
                summary['in_flight'].append(key)
                summary['calls']['solver_started'] += 1
                save(output / 'summary.json', summary)
                running[pool.submit(cell, row, doc, old, identity, raw_root, e2_root,
                                    python, output, deadline)] = key
            if not running:
                if not stop and next_index < len(old['rows']):
                    stop = True
                    summary['status'] = 'stopped_batch_deadline'
                break
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in done:
                key = running.pop(future)
                try:
                    entry = future.result()
                except Exception as error:
                    entry = {'case': key.split('-')[0], 'cores': int(key.split('k')[1]),
                             'status': 'stopped', 'error': 'Worker raised: '+repr(error),
                             'call_count_complete': False}
                summary['in_flight'].remove(key)
                summary['rows'].append(compact(entry))
                for name in ('E2_api_attempted', 'native_returns', 'E0_fallback_confirmed',
                             'E0_fallback_possible', 'E0_independent_started'):
                    summary['calls'][name] += entry.get('calls', {}).get(name, 0)
                if entry.get('call_count_complete') is False:
                    summary['call_count_complete'] = False
                if entry.get('status') != 'accepted':
                    stop = True
                    summary['status'] = 'stopped_first_failure'
                else:
                    summary['accepted_cells'] += 1
                if (summary['calls']['E2_api_attempted'] > limits['E2_api']
                        or summary['calls']['E0_fallback_possible'] > limits['E0_fallback_reserved']
                        or summary['calls']['E0_independent_started'] > limits['E0_independent']):
                    stop = True
                    summary['status'] = 'stopped_budget_exceeded'
                summary['total_wall_seconds'] = time.perf_counter()-started
                save(output / 'summary.json', summary)
        summary['total_wall_seconds'] = time.perf_counter()-started
        if not stop and summary['accepted_cells'] == 500:
            summary['status'] = 'completed'
        elif summary['status'] == 'running':
            summary['status'] = 'stopped_incomplete'
        save(output / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight','run'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--raw-root', type=Path, required=True,
                        help='actual official directory containing code/ and data/')
    parser.add_argument('--e2-root', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True,
                        help='venv bin/python entry; symlink is preserved')
    parser.add_argument('--runner-commit')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    raw_root = args.raw_root.resolve(strict=True)
    e2_root = args.e2_root.resolve(strict=True)
    python = args.python.absolute()  # Do not resolve venv symlink to its base interpreter.
    manifest = args.manifest.resolve(strict=True)
    doc, old, identity = preflight(manifest, raw_root, e2_root, python,
                                   args.runner_commit,
                                   frozen=args.mode == 'run' or bool(args.runner_commit))
    if args.mode == 'preflight':
        print(json.dumps({'status': 'preflight_ok', 'cells': 500, 'calls': 0,
                          'solver_frozen': bool(doc['solver_commit'])}))
        return
    if args.output is None:
        raise ValueError('Run requires a new --output directory')
    summary = run(doc, old, identity, manifest, raw_root, e2_root, python,
                  args.output.absolute(), args.runner_commit, started)
    if summary['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
