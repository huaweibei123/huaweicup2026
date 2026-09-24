"""Bounded, sequential E0 execution and producer-side board export.

The frozen solver is a separate process. No evaluator is imported here. A ps
observer follows descendants even when they create another process group.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SOLVER = 'f17fcc2d84d20497482a1269de7bac95ab7a3138'
REPO = 'huaweibei123/huaweicup2026'
SESSION = 'nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894'
PREFIX = Path('results/a/q2-nikolastarx/feedback-20260924')
OFFICIAL = Path('data/raw/a/official')
ENTRY = OFFICIAL / 'code/multicore_cut_evaluate_problem_2.py'
CONFIG = OFFICIAL / 'data/config.txt'
METHODS = ['contiguous', 'chain_critical', 'affine_eighth', 'guarded_reentry']
SAMPLE_INTERVAL = 0.05


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(raw, encoding='utf-8')
    temporary.replace(path)


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def git_bytes(commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)


def artifact(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path.read_bytes())}


def source(commit, path, entrypoint):
    git_bytes(commit, path)
    return {'repo': REPO, 'commit': commit, 'path': path, 'entrypoint': entrypoint}


def process_snapshot():
    raw = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,pgid=,rss=,lstart='], text=True)
    processes = {}
    for line in raw.splitlines():
        fields = line.split(maxsplit=4)
        if len(fields) == 5:
            pid, parent, group, rss = map(int, fields[:4])
            processes[pid] = {'parent': parent, 'group': group,
                              'rss': rss * 1024, 'birth': fields[4]}
    return processes


def discover(snapshot, root, known):
    """Keep only the same live PID incarnation; then close under parenthood."""
    alive = {pid for pid, birth in known.items()
             if pid in snapshot and snapshot[pid]['birth'] == birth}
    if root in snapshot and root not in known:
        alive.add(root)
    changed = True
    while changed:
        new = {pid for pid, data in snapshot.items() if data['parent'] in alive}
        changed = bool(new - alive)
        alive |= new
    known.update({pid: snapshot[pid]['birth'] for pid in alive})
    return alive


def cleanup_tree(root, known):
    """Freeze the tree before rescanning so the solver cannot launch another E0."""
    killed = set()
    for _ in range(3):
        snapshot = process_snapshot()
        alive = discover(snapshot, root, known)
        for pid in alive:
            try:
                os.kill(pid, signal.SIGSTOP)
            except ProcessLookupError:
                pass
    snapshot = process_snapshot()
    for pid in sorted(discover(snapshot, root, known), reverse=True):
        try:
            os.kill(pid, signal.SIGKILL)
            killed.add(pid)
        except ProcessLookupError:
            pass
    return sorted(killed)


def is_windows():
    return os.name == 'nt'


def monitored(argv, folder, deadline, rss_limit, *, cleanup_timeout=5.0):
    """Platform dispatch; POSIX behavior stays in the original implementation."""
    if is_windows():
        from .windows_process import monitored as windows_monitored
        return windows_monitored(argv, folder, deadline, rss_limit, cwd=ROOT,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}, cleanup_timeout=cleanup_timeout)
    return _monitored_posix(argv, folder, deadline, rss_limit)


def _monitored_posix(argv, folder, deadline, rss_limit):
    folder.mkdir(parents=True, exist_ok=True)
    receipt = {'argv': argv, 'started_at': utc(), 'status': 'starting',
               'sample_interval_seconds': SAMPLE_INTERVAL, 'observed_peak_rss_bytes': 0,
               'rss_samples': 0, 'cleanup_killed_pids': []}
    known = {}
    start = time.perf_counter()
    process = None
    with (folder / 'stdout.txt').open('w') as out, (folder / 'stderr.txt').open('w') as err:
        try:
            process = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=err,
                                       start_new_session=True,
                                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            receipt['pid'] = process.pid
            receipt['status'] = 'running'
            while True:
                snapshot = process_snapshot()
                alive = discover(snapshot, process.pid, known)
                rss = sum(snapshot[pid]['rss'] for pid in alive)
                observer_rss = snapshot.get(os.getpid(), {}).get('rss', 0)
                receipt['rss_samples'] += 1
                receipt['observed_peak_rss_bytes'] = max(receipt['observed_peak_rss_bytes'], rss)
                receipt['observer_inclusive_peak_rss_bytes'] = max(
                    receipt.get('observer_inclusive_peak_rss_bytes', 0), rss + observer_rss)
                if rss + observer_rss > rss_limit:
                    receipt['status'] = 'rss_limit'
                    break
                if process.poll() is not None:
                    receipt['status'] = 'ok' if process.returncode == 0 else 'failed'
                    break
                if time.perf_counter() >= deadline:
                    receipt['status'] = 'timeout'
                    break
                try:
                    process.wait(timeout=min(SAMPLE_INTERVAL, max(0, deadline - time.perf_counter())))
                except subprocess.TimeoutExpired:
                    pass
        except BaseException as error:
            receipt.update(status='runner_error', error=repr(error))
            raise
        finally:
            if process is not None:
                receipt['cleanup_killed_pids'] = cleanup_tree(process.pid, known)
                process.wait()
                receipt['exit_code'] = process.returncode
                receipt['surviving_pids'] = sorted(discover(process_snapshot(), process.pid, known))
                # Direct child has been reaped. Grandchild zombies have no RSS/work.
            receipt.update(finished_at=utc(), wall_seconds=time.perf_counter() - start)
            dump(folder / 'process.json', receipt)
    return receipt


def verify_inputs(runner_commit):
    protocol_path = PREFIX / 'protocol.json'
    protocol = read(ROOT / protocol_path)
    assert (ROOT / protocol_path).read_bytes() == git_bytes(SOLVER, protocol_path)
    assert protocol['cases'] == ['002', '008', '044', '064', '051', '016']
    assert protocol['methods'] == METHODS and protocol['max_E0'] == 30
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', SOLVER,
                                     'src/q2_nikolastarx'], cwd=ROOT, text=True).splitlines()
    source_hashes = {}
    for path in paths:
        if path.endswith('.py'):
            raw = (ROOT / path).read_bytes()
            if raw != git_bytes(SOLVER, path):
                raise ValueError('Solver source changed: ' + path)
            source_hashes[path] = digest(raw)
    runner = Path(__file__).relative_to(ROOT).as_posix()
    assert (ROOT / runner).read_bytes() == git_bytes(runner_commit, runner)
    manifest = read(ROOT / 'docs/a/source-manifest.json')
    selected = {f'data/case_{case}.json' for case in protocol['cases']}
    inputs, official = {}, {}
    for row in manifest['files']:
        path = row['path']
        if path.startswith('code/') or path in selected or path == 'data/config.txt':
            raw = (ROOT / OFFICIAL / path).read_bytes()
            if digest(raw) != row['sha256'] or len(raw) != row['bytes']:
                raise ValueError('Frozen file changed: ' + path)
            (official if path.startswith('code/') else inputs)[path] = row['sha256']
    code_hash = digest(''.join(f'{p}\t{h}\n' for p, h in sorted(official.items())).encode())
    assert code_hash == manifest['official_code_hash'] == protocol['official_sha256']
    assert inputs['data/config.txt'] == protocol['config_sha256']
    return protocol, {'solver_files': source_hashes, 'runner_sha256': digest((ROOT / runner).read_bytes()),
                      'inputs': inputs, 'official_files': official, 'official_sha256': code_hash}


def _windows_host_info():
    """Read current host facts without PowerShell/subprocess or guessed defaults."""
    cpu = ram = None
    missing = {}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            cpu = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
            if not cpu:
                raise ValueError('empty ProcessorNameString')
    except Exception as error:
        cpu = None
        missing['cpu'] = 'Windows registry CPU query unavailable: ' + repr(error)
    try:
        import ctypes as ct

        class MemoryStatus(ct.Structure):
            _fields_ = [('length', ct.c_uint32), ('load', ct.c_uint32)] + [
                (name, ct.c_uint64) for name in ('total_phys', 'available_phys', 'total_page',
                    'available_page', 'total_virtual', 'available_virtual', 'available_extended')]

        api = ct.WinDLL('kernel32', use_last_error=True)
        api.GlobalMemoryStatusEx.argtypes = [ct.POINTER(MemoryStatus)]
        api.GlobalMemoryStatusEx.restype = ct.c_int32
        info = MemoryStatus()
        info.length = ct.sizeof(info)
        ok = api.GlobalMemoryStatusEx(ct.byref(info))
        error = ct.get_last_error()
        if not ok or not info.total_phys:
            raise OSError(error, 'GlobalMemoryStatusEx failed or returned zero total memory')
        ram = int(info.total_phys)
    except Exception as error:
        missing['ram_bytes'] = 'Windows physical RAM query unavailable: ' + repr(error)
    return cpu, ram, missing


def environment():
    def sysctl(key):
        return subprocess.check_output(['sysctl', '-n', key], text=True).strip()
    if is_windows():
        cpu, ram, missing = _windows_host_info()
    else:
        cpu, ram, missing = sysctl('machdep.cpu.brand_string'), int(sysctl('hw.memsize')), {}
    result = {'os': platform.platform(), 'cpu': cpu,
            'gpu': 'not used; CPU-only Python solver and official evaluator',
            'ram_bytes': ram, 'python': platform.python_version(),
            'dependencies': 'uv.lock sha256=' + digest((ROOT / 'uv.lock').read_bytes()) +
                            '; uv sync --locked prepared before this run; no compilation/training',
            'threads': 1, 'workers': 1, 'logical_cpus_available': os.cpu_count()}
    if missing:
        result['_missing_reasons'] = missing
    return result


def observed_rss_peak(row):
    """Whole-attempt peak is unknown if any launched stage lacks a sample."""
    stages = [row[key] for key in ('solver', 'final') if key in row]
    values = [stage.get('observed_peak_rss_bytes') for stage in stages]
    if not values or any(type(value) is not int or value < 0 for value in values):
        return None
    return max(values)


def compress_jsons(folder):
    manifest = {}
    for path in sorted(folder.rglob('*.json')):
        if path.name not in ('result.json', 'trace.json'):
            continue
        raw = path.read_bytes()
        packed = gzip.compress(raw, mtime=0)
        assert gzip.decompress(packed) == raw
        target = path.with_suffix(path.suffix + '.gz')
        target.write_bytes(packed)
        manifest[path.relative_to(folder).as_posix()] = {
            'stored': target.relative_to(folder).as_posix(), 'raw_sha256': digest(raw),
            'stored_sha256': digest(packed), 'raw_bytes': len(raw), 'stored_bytes': len(packed)}
        path.unlink()
    return manifest


def valid_result(path, cores):
    result = read(path)
    score = result['makespan']
    if type(score) not in (int, float) or not math.isfinite(score) or score <= 0:
        raise ValueError('Invalid official Makespan/type')
    if result['scene'] != 'B' or result['num_cores'] != cores or result.get('problem') == 3:
        raise ValueError('Not a P2 result with expected core count')
    return result


def execute(output, runner_commit):
    protocol, hashes = verify_inputs(runner_commit)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    batch = {'started_at': utc(), 'status': 'running', 'solver_commit': SOLVER,
             'runner_commit': runner_commit, 'protocol': protocol, 'verified_sha256': hashes,
             'environment': environment(), 'cases': [], 'reserved_E0': 0,
             'command': ['.venv/bin/python', '-B', '-m', 'src.q2_nikolastarx.evaluate_feedback',
                         'run', '--runner-commit', runner_commit, '--output', output.relative_to(ROOT).as_posix()],
             'observer': 'ps sum RSS of solver/evaluator descendants, 50ms target sampling; RSS stop also includes this observer. Other sessions excluded; short peaks may be missed; no hard memory guarantee. Concurrent P1/Q3 research loads are not isolated; measured wall is not an exclusive-machine speed claim.',
             'offline_costs': 'uv environment sync, source/case extraction and static development precede the run; their wall time was not measured here. No training/compiled evaluator/precomputed per-case plan is loaded by solver.'}
    dump(output / 'batch.json', batch)
    deadline = started + protocol['batch_wall_seconds']
    try:
        for case in protocol['cases']:
            row = {'case': case, 'status': 'not_run', 'started_at': utc(),
                   'online_E0_calls': 0, 'final_E0_calls': 0}
            batch['cases'].append(row)
            if time.perf_counter() >= deadline or batch['reserved_E0'] + 5 > protocol['max_E0']:
                row['reason'] = 'batch_budget_no_dispatch'
                row['finished_at'] = utc()
                dump(output / case / 'run.json', row)
                continue
            verify_inputs(runner_commit)
            folder = output / case
            folder.mkdir()
            graph = OFFICIAL / f'data/case_{case}.json'
            relative = folder.relative_to(ROOT)
            solver_argv = ['.venv/bin/python', '-B', '-m', 'src.q2_nikolastarx.solve', str(graph),
                           '--config', str(CONFIG), '--cores', str(protocol['cores']),
                           '--output', str(relative / 'plan.json'), '--evidence', str(relative / 'online'),
                           '--evaluation-timeout', str(protocol['evaluation_timeout_seconds']),
                           '--wall', str(protocol['solver_wall_seconds'])]
            row['solver'] = monitored(solver_argv, folder / 'solver-process',
                                      min(deadline, time.perf_counter() + protocol['solver_wall_seconds']),
                                      protocol['rss_observation_stop_bytes'])
            ledger = read(folder / 'online/solver.json') if (folder / 'online/solver.json').exists() else {}
            row['online'] = ledger
            reserved = ledger.get('calls', {}).get('E0', 4)
            row['online_reserved_E0'] = reserved
            uncertain = not ledger or any(a['status'] == 'dispatching' for a in ledger.get('attempts', []))
            row['online_E0_calls'] = None if uncertain else reserved
            batch['reserved_E0'] += reserved
            if row['solver']['status'] != 'ok' or ledger.get('status') != 'ok':
                row.update(status='timeout' if row['solver']['status'] == 'timeout' else 'failed',
                           reason='solver_did_not_complete_successfully')
            elif time.perf_counter() >= deadline:
                row.update(status='not_run', reason='final_E0_not_dispatched_batch_deadline')
            else:
                plan = read(folder / 'plan.json')
                assert set(plan) == {'node_to_subgraph', 'core_schedules'}
                assert digest((folder / 'plan.json').read_bytes()) == ledger['plan_sha256']
                final = folder / 'final'
                final.mkdir()
                final_argv = ['.venv/bin/python', '-B', str(ENTRY), str(graph), str(relative / 'plan.json'),
                              '--config', str(CONFIG), '-o', str(relative / 'final/result.json'),
                              '--trace-output', str(relative / 'final/trace.json'),
                              '--log-output', str(relative / 'final/official.log')]
                row['final_E0_calls'] = 1
                batch['reserved_E0'] += 1
                dump(output / 'batch.json', batch)
                row['final'] = monitored(final_argv, final,
                                         min(deadline, time.perf_counter() + protocol['evaluation_timeout_seconds']),
                                         protocol['rss_observation_stop_bytes'])
                if row['final']['status'] == 'ok':
                    result = valid_result(final / 'result.json', protocol['cores'])
                    selected = folder / 'online' / ledger['selected_result']
                    valid_result(selected, protocol['cores'])
                    row['full_result_bytes_equal'] = (final / 'result.json').read_bytes() == selected.read_bytes()
                    row['full_result_json_equal'] = result == read(selected)
                    row['makespan_type'] = type(result['makespan']).__name__
                    row['makespan_cycles'] = result['makespan']
                    row.update(status='ok' if row['full_result_bytes_equal'] else 'failed',
                               reason='confirmed_complete_result' if row['full_result_bytes_equal'] else 'final_result_mismatch')
                else:
                    row.update(status='timeout' if row['final']['status'] == 'timeout' else 'failed',
                               reason='independent_final_E0_failed')
            row['finished_at'] = utc()
            dump(folder / 'run.json', row)
            dump(output / 'batch.json', batch)
            print(json.dumps({'case': case, 'status': row['status'], 'selected': ledger.get('selected'),
                              'makespan': row.get('makespan_cycles'), 'E0': row['online_E0_calls'],
                              'solver_wall': row['solver']['wall_seconds']}), flush=True)
            if row['solver']['status'] == 'rss_limit' or row.get('final', {}).get('status') == 'rss_limit':
                batch['stop_reason'] = 'rss_observation_limit'
                break
        batch['status'] = 'complete'
        batch.setdefault('stop_reason', 'fixed_six_cases_completed' if all(c['status'] == 'ok' for c in batch['cases']) else 'finished_with_incomplete_cases')
    finally:
        completed = {row['case'] for row in batch['cases']}
        for case in protocol['cases']:
            if case not in completed:
                row = {'case': case, 'status': 'not_run', 'started_at': utc(), 'finished_at': utc(),
                       'online_E0_calls': 0, 'final_E0_calls': 0,
                       'reason': batch.get('stop_reason', 'batch_interrupted_no_dispatch')}
                batch['cases'].append(row)
                dump(output / case / 'run.json', row)
        batch.update(finished_at=utc(), execution_wall_seconds=time.perf_counter() - started)
        batch['compression'] = compress_jsons(output)
        dump(output / 'batch.json', batch)
    export(output)


def export(output):
    batch = read(output / 'batch.json')
    protocol = batch['protocol']
    records, summary = [], []
    before = read(ROOT / PREFIX / 'board-before.json')
    previous = {c['case_id']: c['best']['metrics']['makespan_cycles'] for c in before['cells']}
    run_id = 'nikolastarx-q2-structural-' + batch['started_at'].replace('-', '').replace(':', '').split('.')[0]
    for row in batch['cases']:
        case = row['case']
        folder = output / case
        graph_hash = batch['verified_sha256']['inputs'][f'data/case_{case}.json']
        baseline_folder = ROOT / f'results/benchmark-board/official-singlecore-20260924/{case}'
        baseline_run = read(baseline_folder / 'run.json')
        baseline_result = baseline_folder / 'result.json.gz'
        baseline = read(baseline_result)
        assert baseline_run['status'] == 'ok' and baseline['scene'] == 'A' and baseline['num_cores'] == 1
        assert baseline_run['graph_sha256'] == graph_hash
        assert baseline_run['config_sha256'] == protocol['config_sha256']
        assert baseline_run['official_code_hash'] == protocol['official_sha256']
        assert digest(baseline_result.read_bytes()) == baseline_run['artifacts']['result.json']['sha256']
        assert baseline['makespan'] == baseline_run['makespan_cycles']
        result = valid_result(folder / 'final/result.json.gz', protocol['cores']) if row['status'] == 'ok' else None
        ledger = row.get('online', {})
        attempts = ledger.get('attempts', [])
        calls = None if row.get('online_E0_calls') is None else row['online_E0_calls'] + row['final_E0_calls']
        row_environment = {k: v for k, v in batch['environment'].items() if k not in ('logical_cpus_available', '_missing_reasons')}
        row_environment['peak_rss_bytes'] = observed_rss_peak(row)
        missing = {'provenance.measurement.seed': 'Deterministic constructors; no random seed is used.'}
        missing.update({'provenance.environment.' + k: reason for k, reason in batch['environment'].get('_missing_reasons', {}).items()})
        if calls is None:
            missing['provenance.measurement.calls.E0'] = 'Interrupted dispatch or missing solver ledger leaves actual online launches unknown; reservations remain charged.'
        if row_environment['peak_rss_bytes'] is None:
            missing['provenance.environment.peak_rss_bytes'] = 'No observed live process RSS sample.'
        provenance = {
            'producer_session': SESSION, 'task_url': f'https://github.com/{REPO}/issues/33',
            'solver': {'source': source(SOLVER, 'src/q2_nikolastarx/solve.py', 'main'),
                       'authors': ['NikolaStarx'],
                       'method': 'From-graph deterministic four-constructor portfolio; exact serialized duplicates skipped; only successful strict E0 Makespan improvement promotes incumbent.',
                       'references': [f'https://github.com/{REPO}/blob/{SOLVER}/docs/a/q2-nikolastarx/FEEDBACK_METHOD.md'],
                       'upstream': [source('0b58c123cccf02fc993b741d79dcd8511e4dd38f', 'src/q2/construct.py', 'contiguous_plan'),
                                    source('a4e7ee13310d693ec4fb5cc236669ceb3b172d1f', 'src/q3/construct.py', 'Index')],
                       'selected_algorithm_id': ledger.get('selected', '').replace('_', '-') or None,
                       'selected_solver_commit': SOLVER if ledger.get('selected') else None},
            'runner': {'source': source(batch['runner_commit'], 'src/q2_nikolastarx/evaluate_feedback.py', 'execute'),
                       'argv': batch['command'], 'working_directory': '.'},
            'environment': row_environment,
            'measurement': {'started_at': row['started_at'], 'finished_at': row.get('finished_at'),
                            'seed': None, 'repeat_index': 0, 'cold_start': True,
                            'solver_scope': 'Fresh solver process Popen through exit, descendant cleanup and return; graph parsing, four constructors and all online E0 included; observer polling overhead included. OS file cache is not flushed.',
                            'evaluation_scope': 'Separate final official CLI Popen through exit and cleanup; outside solver wall. Full final result bytes compared with selected online E0.',
                            'budget': {'wall_seconds': protocol['solver_wall_seconds'], 'candidate_limit': 4,
                                       'stop_reason': ledger.get('stop_reason', row.get('reason'))},
                            'calls': {'solver': 1 if 'solver' in row else 0, 'E0': calls, 'E1': 0, 'E2': 0},
                            'offline_costs': batch['offline_costs'],
                            'failure': None if row['status'] == 'ok' else {'stage': row.get('reason', 'not_dispatched'),
                                'reason': row.get('reason', 'batch_stopped'), 'exit_code': row.get('final', row.get('solver', {})).get('exit_code'),
                                'elapsed_seconds': row.get('solver', {}).get('wall_seconds')}},
            'missing_reasons': missing}
        movement = result['data_movement_bytes'] if result else {}
        artifacts = {'run': artifact(folder / 'run.json')} if (folder / 'run.json').exists() else {}
        if result:
            artifacts.update(plan=artifact(folder / 'plan.json'), result=artifact(folder / 'final/result.json.gz'))
        record = {'attempt_id': f'{run_id}-p2-{case}-k4', 'revision': 1, 'run_id': run_id,
                  'algorithm_id': 'q2-structural-portfolio', 'algorithm_name': 'P2 四构造官方保护组合',
                  'variant': 'e0-protected-four-constructors', 'solver_commit': SOLVER,
                  'parameters': {'protocol': protocol, 'selected': ledger.get('selected'),
                                 'online_E0_calls': row.get('online_E0_calls'), 'final_E0_calls': row['final_E0_calls'],
                                 'sample_status': 'development; selected before outcomes; not holdout',
                                 'observer': batch['observer']},
                  'problem': 'P2', 'case_id': case, 'cores': 4, 'status': row['status'],
                  'metrics': {'makespan_cycles': result['makespan'] if result else None,
                              'solver_wall_seconds': row.get('solver', {}).get('wall_seconds'),
                              'evaluation_wall_seconds': row.get('final', {}).get('wall_seconds'),
                              'ddr_bytes': movement.get('scheduled_copy_bytes'),
                              'extra_ddr_bytes': movement.get('added_copy_bytes'),
                              'spill_bytes': movement.get('spill_added_copy_bytes'), 'cache_hit_rate': None},
                  'evaluator': {'route': 'E0', 'commit': SOLVER, 'entrypoint': ENTRY.as_posix()},
                  'identity': {'graph_sha256': graph_hash, 'config_sha256': protocol['config_sha256'],
                               'official_sha256': protocol['official_sha256'], 'plan_sha256': ledger.get('plan_sha256')},
                  'artifacts': artifacts, 'runtime_id': 'nikolastarx-q2-feedback-macos27-arm64-py31213',
                  'observed_at': row['started_at'],
                  'timing': {'solver_includes_evaluation': False,
                             'evaluation_precision': 'time.perf_counter seconds; outer observed process lifetime with up to 50ms polling granularity plus ps/cleanup overhead',
                             'utc': 'UTC timestamps recorded during execution'},
                  'provenance': provenance,
                  'baseline': {'graph_sha256': graph_hash, 'config_sha256': protocol['config_sha256'],
                               'official_sha256': protocol['official_sha256'], 'route': 'E0',
                               'entrypoint': 'singlecore_evaluate.evaluate_singlecore', 'result': artifact(baseline_result)},
                  'notes': ['Independent evaluator worker shares parent development context; not a blind scientific review.',
                            'Online E0 belongs to solver wall; timing.solver_includes_evaluation=false refers only to the separately reported final E0 wall.',
                            'All candidate attempts including regressions and duplicate skips remain in run/online; compressed JSON is lossless and raw hashes are in batch.compression.',
                            'RSS is sampled across owned descendants, including separate process groups; short peaks may be missed. Observed peak is not a hard bound.',
                            'Official singlecore denominator reused with verified hashes and original result; zero new singlecore evaluations.'],
                  'source_url': f'https://github.com/{REPO}/issues/33'}
        records.append(record)
        summary.append({'case': case, 'status': row['status'], 'candidates': [
            {k: a.get(k) for k in ('name', 'status', 'duplicate_of', 'makespan_cycles', 'evaluation_wall_seconds', 'plan_sha256')}
            for a in attempts], 'selected': ledger.get('selected'), 'makespan_cycles': row.get('makespan_cycles'),
            'board_before_makespan': previous[case], 'baseline_cycles': baseline['makespan'],
            'baseline_speedup': baseline['makespan'] / result['makespan'] if result else None,
            'solver_wall_seconds': row.get('solver', {}).get('wall_seconds'),
            'final_E0_wall_seconds': row.get('final', {}).get('wall_seconds'), 'E0_calls': calls,
            'full_result_bytes_equal': row.get('full_result_bytes_equal'), 'makespan_type': row.get('makespan_type')})
    dump(output / 'board-feed.json', {'schema_version': 1, 'submission_version': 1, 'records': records})
    dump(output / 'summary.json', summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'export'])
    parser.add_argument('--output', type=Path, default=PREFIX / 'run')
    parser.add_argument('--runner-commit')
    args = parser.parse_args()
    output = args.output.resolve()
    if output != ROOT / PREFIX / 'run':
        raise ValueError('This batch owns only the frozen run directory')
    if args.action == 'run':
        if not args.runner_commit:
            parser.error('--runner-commit is required before running')
        execute(output, args.runner_commit)
    else:
        export(output)


if __name__ == '__main__':
    main()
