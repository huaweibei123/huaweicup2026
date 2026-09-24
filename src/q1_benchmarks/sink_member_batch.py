"""Portable, fixed eight-cell sink-peel batch. Preparation/export never score.

The run action is for a separately assigned member only. Each solver/E0 process
is a single Python process; kill+wait cleans that direct child on all platforms.
This controller does not claim to clean arbitrary descendant process trees.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'results/a/q1-sink-member-package-20260924'
MANIFEST_PATH = PACKAGE / 'manifest.json'
RESULT_ROOT = ROOT / 'results/a/q1-sink-member-runs'
RUNNER_PATH = 'src/q1_benchmarks/sink_member_batch.py'
CLI_PATH = 'src/q1_benchmarks/sink_peel_cli.py'
SOLVER_PATH = 'src/q1/sink_peel.py'
OFFICIAL = ROOT / 'data/raw/a/official'
REPO = 'huaweibei123/huaweicup2026'
TASK = 'https://github.com/huaweibei123/huaweicup2026/issues/98'


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def write(p, value):
    p = Path(p)
    temporary = p.with_name(p.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, p)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def public_path(path):
    return Path(path).relative_to(ROOT).as_posix()


def artifact(path):
    return {'path': public_path(path), 'sha256': sha(path)}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def verify(expected_runner_commit=None):
    """Static byte checks only; never import/call construct or an evaluator."""
    m = read(MANIFEST_PATH)
    head = git('rev-parse', 'HEAD').decode().strip()
    if expected_runner_commit and head != expected_runner_commit:
        raise RuntimeError('Check out the assigned fixed runner commit before execution')
    if git('diff', '--name-only', 'HEAD').strip():
        raise RuntimeError('Tracked worktree differs from its Git commit')
    checked = []
    for entry in m['files']:
        path = ROOT / entry['path']
        if sha(path) != entry['sha256']:
            raise RuntimeError(f"Frozen byte mismatch: {entry['path']}")
        checked.append(entry['path'])
    source = read(ROOT / 'docs/a/source-manifest.json')
    for entry in source['files']:
        if entry['path'].startswith('code/') or entry['path'] == 'data/config.txt':
            path = OFFICIAL / entry['path']
            if sha(path) != entry['sha256']:
                raise RuntimeError(f"Official byte mismatch: {entry['path']}")
            checked.append(public_path(path))
    files = {x['path']: x for x in source['files']}
    code_hash = digest(''.join(f"{p}\t{files[p]['sha256']}\n" for p in sorted(files) if p.startswith('code/')).encode())
    if code_hash != m['official_code_hash'] or code_hash != source['official_code_hash']:
        raise RuntimeError('Official code identity mismatch')
    import zipfile
    with zipfile.ZipFile(ROOT / source['case_archive']['path']) as z:
        for case in m['cases']:
            name = f'data/case_{case}.json'
            if digest(z.read(name)) != files[name]['sha256']:
                raise RuntimeError(f'Input graph hash mismatch: {case}')
    for case, record in read(PACKAGE / 'reference-index.json').items():
        for ref in (record['bounded04_result'], record['baseline']['result']):
            if sha(ROOT / ref['path']) != ref['sha256']:
                raise RuntimeError(f'Reference result changed: {case}')
    return {'status': 'ok', 'observed_at': utc(), 'head': head,
            'checked_files': checked, 'input_graphs': m['cases'],
            'scope': 'static byte checks; zero solver/E0/E1/E2'}, m, source


def direct_process(argv, folder, name, timeout):
    """One direct child. kill() and wait() are available on POSIX and Windows."""
    outp, errp = folder / f'{name}.stdout.txt', folder / f'{name}.stderr.txt'
    started, t0 = utc(), time.perf_counter()
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    child, status, reason, cleaned = None, 'failed', None, True
    with outp.open('xb') as out, errp.open('xb') as err:
        try:
            child = subprocess.Popen([str(v) for v in argv], cwd=ROOT, env=env, stdout=out, stderr=err)
            try:
                child.wait(timeout=timeout)
                status = 'ok' if child.returncode == 0 else 'failed'
                if child.returncode:
                    reason = f'Process exited {child.returncode}'
            except subprocess.TimeoutExpired:
                status, reason = 'timeout', f'Direct child exceeded {timeout:.6f} seconds'
                child.kill()
                child.wait(timeout=10)
        except BaseException as exc:
            status, reason = 'failed', f'{type(exc).__name__}: {exc}'
        finally:
            if child is not None and child.poll() is None:
                try:
                    child.kill()
                    child.wait(timeout=10)
                except BaseException as cleanup_error:
                    cleaned = False
                    reason = f'{reason}; cleanup failed: {type(cleanup_error).__name__}'
    def label(value):
        return str(value).replace(str(ROOT), '.').replace(str(Path(sys.executable)), '<python>')
    return {'argv': [label(x) for x in argv], 'cwd': '.', 'started_at': started, 'finished_at': utc(),
            'wall_seconds': time.perf_counter() - t0, 'timeout_seconds': timeout,
            'status': status, 'reason': reason, 'launched': child is not None,
            'exit_code': child.returncode if child else None,
            'cleanup_confirmed': cleaned, 'child_pid': child.pid if child else None,
            'stdout': artifact(outp), 'stderr': artifact(errp),
            'log_derivation': 'Unmodified subprocess output bytes; inspect stderr paths before external publication',
            'cleanup_scope': 'Direct child only; frozen solver/E0 do not launch descendant processes'}


def ram_bytes():
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('dwLength', wintypes.DWORD), ('dwMemoryLoad', wintypes.DWORD)] + [(x, ctypes.c_ulonglong) for x in ('ullTotalPhys', 'ullAvailPhys', 'ullTotalPageFile', 'ullAvailPageFile', 'ullTotalVirtual', 'ullAvailVirtual', 'ullAvailExtendedVirtual')]
            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        elif sys.platform == 'darwin':
            return int(subprocess.check_output(['sysctl', '-n', 'hw.memsize']))
        else:
            return int(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE'))
    except (AttributeError, OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def environment():
    cpu = platform.processor() or os.environ.get('PROCESSOR_IDENTIFIER') or None
    if sys.platform == 'darwin':
        try:
            cpu = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string']).decode().strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return {'os': platform.platform(), 'cpu': cpu, 'gpu': 'none (not used)', 'ram_bytes': ram_bytes(),
            'python': sys.version, 'dependencies': f"uv.lock sha256={sha(ROOT / 'uv.lock')}; uv sync --locked required",
            'threads': None, 'workers': 1, 'peak_rss_bytes': None}


def compress_json(path):
    raw = path.read_bytes()
    json.loads(raw)
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    assert gzip.decompress(packed) == raw
    target = path.with_suffix(path.suffix + '.gz')
    target.write_bytes(packed)
    path.unlink()
    return artifact(target)


def run(args):
    if not args.execute_authorized:
        raise ValueError('Only the assigned member may use --execute-authorized after the board owner grants a resource window')
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('Use uv sync --locked and Python3.12')
    batch = RESULT_ROOT / args.run_id
    batch.mkdir(parents=True, exist_ok=False)
    start_wall, start_utc = time.monotonic(), utc()
    deadline = start_wall + 600
    manifest = read(MANIFEST_PATH)
    meta = {'run_id': args.run_id, 'status': 'preflight', 'started_at': start_utc, 'finished_at': None,
            'runner_commit': args.expected_runner_commit, 'runner_sha256': sha(__file__),
            'solver_commit': manifest['solver_commit'], 'producer_session': args.producer_session,
            'runtime_id': args.runtime_id, 'environment': environment(),
            'argv': ['python', '-B', RUNNER_PATH, 'run', '--run-id', args.run_id,
                     '--expected-runner-commit', args.expected_runner_commit,
                     '--producer-session', args.producer_session, '--runtime-id', args.runtime_id,
                     '--execute-authorized', '--concurrency-context', args.concurrency_context],
            'concurrency_context': args.concurrency_context,
            'budget': manifest['budget'], 'actual_calls': dict.fromkeys(('solver','E0','E1','E2'), 0),
            'manifest_sha256': sha(MANIFEST_PATH)}
    write(batch / 'batch.json', meta)
    cells = []
    for case in manifest['cases']:
        folder = batch / 'cells' / case / 'k4'
        folder.mkdir(parents=True)
        cell = {'case_id': case, 'cores': 4, 'status': 'not_run', 'started_at': None, 'finished_at': None,
                'calls': dict.fromkeys(('solver','E0','E1','E2'),0), 'artifacts': {}, 'failure': None,
                'makespan_cycles': None, 'graph_sha256': manifest['graphs'][case]}
        write(folder / 'run.json', cell)
        cells.append((folder, cell))
    stopped = None
    try:
        preflight, _, source = verify(args.expected_runner_commit)
        write(batch / 'preflight.json', preflight)
        meta['status'] = 'running'
        write(batch / 'batch.json', meta)
        import zipfile
        with tempfile.TemporaryDirectory(prefix='verified-inputs-', dir=batch) as td:
            inputs = Path(td)
            prep_t0 = time.perf_counter()
            with zipfile.ZipFile(ROOT / source['case_archive']['path']) as z:
                for case in manifest['cases']:
                    raw = z.read(f'data/case_{case}.json')
                    if digest(raw) != manifest['graphs'][case]:
                        raise RuntimeError('Input changed after preflight')
                    (inputs / f'case_{case}.json').write_bytes(raw)
            meta['input_preparation_wall_seconds'] = time.perf_counter() - prep_t0
            for folder, cell in cells:
                case = cell['case_id']
                if stopped or time.monotonic() >= deadline:
                    cell['not_run_reason'] = stopped or 'Batch600s deadline reached'
                    stopped = cell['not_run_reason']
                    write(folder / 'run.json', cell)
                    continue
                cell['started_at'] = utc()
                graph = public_path(inputs / f'case_{case}.json')
                plan = folder / f'case_{case}_multicore_res.json'
                result, trace, log = folder / 'result.json', folder / 'trace.json', folder / 'official.log'
                diag = folder / 'diagnostics.json'
                stage = 'solver'
                try:
                    for stage, argv, limit in (
                        ('solver', [sys.executable, '-B', CLI_PATH, graph, '--cores','4', '--max-rounds','64', '--max-sinks','64', '--output',public_path(plan),'--diagnostics',public_path(diag)], 30),
                        ('E0', [sys.executable, '-B', public_path(OFFICIAL / 'code/multicore_cut_evaluate_problem_1.py'), graph, public_path(plan), '--config', public_path(OFFICIAL / 'data/config.txt'), '--output', public_path(result), '--trace-output', public_path(trace), '--log-output', public_path(log)], 60)):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError('Batch600s deadline reached before dispatch')
                        receipt = direct_process(argv, folder, stage, min(limit, remaining))
                        cell[stage] = receipt
                        cell['calls'][stage] += int(receipt['launched'])
                        meta['actual_calls'][stage] += int(receipt['launched'])
                        write(folder / 'run.json', cell)
                        write(batch / 'batch.json', meta)
                        if not receipt['cleanup_confirmed']:
                            raise RuntimeError('Direct-child cleanup unconfirmed; never dispatch again')
                        if receipt['status'] != 'ok':
                            raise RuntimeError(receipt['reason'])
                        if stage == 'solver':
                            if set(read(plan)) != {'node_to_subgraph','core_schedules'}:
                                raise ValueError('Plan has unexpected keys')
                            cell['plan_sha256'] = sha(plan)
                            cell['diagnostics'] = read(diag)
                    official = read(result)
                    if official.get('scene') != 'A' or official.get('num_cores') != 4 or type(official.get('makespan')) not in (int,float) or not math.isfinite(official['makespan']) or official['makespan'] <= 0:
                        raise ValueError('Official result identity or Makespan invalid')
                    cell.update(status='ok', makespan_cycles=official['makespan'], data_movement_bytes=official['data_movement_bytes'])
                except BaseException as error:
                    receipt = cell.get(stage,{})
                    cell['status'] = 'timeout' if receipt.get('status') == 'timeout' or isinstance(error,TimeoutError) else 'failed'
                    cell['failure'] = {'stage': stage, 'reason': f'{type(error).__name__}: {error}', 'exit_code': receipt.get('exit_code'), 'elapsed_seconds': receipt.get('wall_seconds')}
                    stopped = f"Stopped after {case}/k4 {stage}: {cell['failure']['reason']}"
                finally:
                    # Preserve all produced evidence, including failure/partial files.
                    for name,path in [('plan',plan),('result',result),('trace',trace),('log',log),('diagnostics',diag)]:
                        if path.exists():
                            if name in ('result','trace') and cell['status']=='ok':
                                cell['artifacts'][name] = compress_json(path)
                            else:
                                cell['artifacts'][name] = artifact(path)
                    cell['finished_at'] = utc()
                    write(folder / 'run.json', cell)
                    print(json.dumps({'case':case,'status':cell['status'],'makespan':cell['makespan_cycles']}),flush=True)
    except BaseException as error:
        stopped = f'Supervisor/preflight failure: {type(error).__name__}: {error}'
        meta['supervisor_failure'] = stopped
    finally:
        try:
            postflight, _, _ = verify(args.expected_runner_commit)
            write(batch / 'postflight.json', postflight)
        except BaseException as error:
            stopped = f'Final byte identity verification failed: {type(error).__name__}: {error}'
            meta['identity_failure'] = stopped
        for folder,cell in cells:
            if cell['status'] == 'not_run':
                cell['not_run_reason'] = stopped or 'No successful dispatch recorded'
                write(folder / 'run.json',cell)
        meta.update(status='stopped' if stopped else 'complete', stop_reason=stopped or 'All8 predeclared cells completed', finished_at=utc(), batch_wall_seconds=time.monotonic()-start_wall)
        write(batch / 'batch.json',meta)
    return int(bool(stopped))


def code_source(commit,path,entrypoint):
    return {'repo': REPO, 'commit': commit, 'path': path, 'entrypoint': entrypoint}


def export(args):
    batch = RESULT_ROOT / args.run_id
    meta, manifest = read(batch/'batch.json'), read(MANIFEST_PATH)
    if meta.get('finished_at') is None:
        raise ValueError('Do not export an in-progress batch')
    refs = read(PACKAGE/'reference-index.json')
    records, comparisons = [], []
    for case in manifest['cases']:
        folder=batch/'cells'/case/'k4'; c=read(folder/'run.json')
        movement=c.get('data_movement_bytes',{})
        status, failure = c['status'],c['failure']
        if meta.get('identity_failure') and status=='ok':
            status='failed'; failure={'stage':'postflight','reason':meta['identity_failure'],'exit_code':None,'elapsed_seconds':None}
        metrics={'makespan_cycles':c['makespan_cycles'] if status=='ok' else None,
                 'solver_wall_seconds':c.get('solver',{}).get('wall_seconds'),
                 'evaluation_wall_seconds':c.get('E0',{}).get('wall_seconds'),
                 'ddr_bytes':movement.get('scheduled_copy_bytes'),'extra_ddr_bytes':movement.get('added_copy_bytes'),'spill_bytes':movement.get('spill_added_copy_bytes')}
        artifacts={k:v for k,v in c['artifacts'].items() if k!='diagnostics'};artifacts['run']=artifact(folder/'run.json')
        missing={'provenance.measurement.seed':'Deterministic construction does not use RNG',
                 'provenance.environment.threads':'Not sampled; BLAS/OMP/MKL environment set to1',
                 'provenance.environment.peak_rss_bytes':'Peak RSS was not measured'}
        for field in ('cpu','ram_bytes'):
            if meta['environment'][field] is None:missing[f'provenance.environment.{field}']='Platform information unavailable'
        if c['started_at'] is None:missing['provenance.measurement.started_at']=c.get('not_run_reason','Not dispatched')
        if c['finished_at'] is None:missing['provenance.measurement.finished_at']=c.get('not_run_reason','Not dispatched')
        row={'attempt_id':f"{meta['producer_session'].split('/')[0]}-{args.run_id}-P1-{case}-k4-r0",'revision':1,'run_id':args.run_id,
             'algorithm_id':'q1-sink-peel','algorithm_name':'P1 sink-exclusive suffix waves','variant':'exclusive-suffix-waves',
             'solver_commit':manifest['solver_commit'],'parameters':manifest['parameters'],'problem':'P1','case_id':case,'cores':4,
             'status':status,'metrics':metrics,'runtime_id':meta['runtime_id'],'observed_at':c['finished_at'],
             'evaluator':{'route':'E0','commit':manifest['solver_commit'],'entrypoint':'multicore_cut_evaluate_problem_1.py -> contest_io.run_problem_cli(1)'},
             'identity':{'graph_sha256':c['graph_sha256'],'config_sha256':manifest['config_sha256'],'official_sha256':manifest['official_code_hash'],'plan_sha256':c.get('plan_sha256')},
             'artifacts':artifacts,'baseline':refs[case]['baseline'],'source_url':TASK,
             'timing':{'solver_includes_evaluation':False,'evaluation_precision':'perf_counter outer subprocess wall, includes process completion detection','utc':'ISO UTC Z; durations from monotonic clocks'},
             'provenance':{'producer_session':meta['producer_session'],'task_url':TASK,
                 'solver':{'source':code_source(manifest['solver_commit'],SOLVER_PATH,'construct'),'authors':['NikolaStarx'],
                           'method':'Bounded04 fallback, recursively peel sink-exclusive suffix packets, reverse waves, per-wave pipe-work packing; no online scoring',
                           'references':[f"https://github.com/{REPO}/blob/{manifest['solver_commit']}/docs/a/Q1_SINK_PEEL.md"],
                           'upstream':[code_source(manifest['solver_commit'],'src/q1/bounded_tasks.py','construct'),code_source(meta['runner_commit'],CLI_PATH,'main')],
                           'selected_algorithm_id':None,'selected_solver_commit':None},
                 'runner':{'source':code_source(meta['runner_commit'],RUNNER_PATH,'run'),'argv':meta['argv'],'working_directory':'.'},
                 'environment':meta['environment'],'measurement':{'started_at':c['started_at'],'finished_at':c['finished_at'],'seed':None,'repeat_index':0,'cold_start':True,
                    'solver_scope':'Fresh Python process through graph reading, bounded fallback, sink construction, structural validation and plan/diagnostics writes and exit; OS file cache not flushed',
                    'evaluation_scope':'Independent frozen E0 process through complete result/trace/log writes and exit; gzip/export excluded',
                    'budget':{'wall_seconds':30,'candidate_limit':1,'stop_reason':'direct candidate complete' if status=='ok' else c.get('not_run_reason','Failure stopped batch')},
                    'calls':c['calls'],'offline_costs':f"uv sync --locked before run; no training or case-specific precompute; batch byte verification and ZIP preparation outside per-cell wall, included in batch wall. ZIP extraction seconds={meta.get('input_preparation_wall_seconds')}",'failure':failure},
                 'missing_reasons':missing},
             'notes':['Predeclared eight-case development batch, not full100. Only005/047/064/069/075/082/085/086 k4;048/071 are reference-only, not re-evaluated.',
                      meta['concurrency_context'],'Fresh process; OS cache not flushed; runtime comparisons across different machines are descriptive only.',
                      'Baseline and bounded04 originals reused; no baseline rerun. Direct-child timeout cleanup does not supervise arbitrary descendant trees.']}
        records.append(row)
        base=json.loads(gzip.decompress((ROOT/refs[case]['baseline']['result']['path']).read_bytes()))['makespan']
        m=metrics['makespan_cycles'];comparisons.append({'case':case,'status':status,**metrics,'bounded04_cycles':refs[case]['bounded04_cycles'],'singlecore_cycles':base,'speedup':base/m if m else None,
                                                       'tasks':c.get('diagnostics',{}).get('tasks'),'waves':c.get('diagnostics',{}).get('wave_count')})
    write(batch/'board-feed.json',{'schema_version':1,'submission_version':1,'records':records})
    write(batch/'comparison.json',comparisons)
    print(json.dumps({'exported_records':len(records),'path':public_path(batch/'board-feed.json'),'new_calls':{'solver':0,'E0':0,'E1':0,'E2':0}}))


def self_test():
    """Synthetic direct-child controller tests only; no algorithm/evaluator."""
    observations=[]
    with tempfile.TemporaryDirectory(prefix='controller-fixture-',dir=PACKAGE) as td:
        folder=Path(td)
        for name,code,timeout,expected in [('success','print("fixture-ok")',5,'ok'),('exit3','raise SystemExit(3)',5,'failed'),('timeout','import time; time.sleep(30)',.15,'timeout')]:
            result=direct_process([sys.executable,'-c',code],folder,name,timeout)
            assert result['status']==expected and result['cleanup_confirmed'] and result['exit_code'] is not None
            observations.append({'fixture':name,'status':result['status'],'exit_code':result['exit_code'],'cleanup_confirmed':result['cleanup_confirmed'],'wall_seconds':result['wall_seconds']})
        failed=direct_process([str(folder/'definitely-missing-program')],folder,'spawn-failure',5)
        assert failed['status']=='failed' and not failed['launched'] and failed['cleanup_confirmed']
        observations.append({'fixture':'spawn-failure','status':failed['status'],'launched':failed['launched'],'cleanup_confirmed':failed['cleanup_confirmed']})
    print(json.dumps({'observed_at':utc(),'platform':platform.platform(),'python':sys.version,'tests':observations,'solver_E0_E1_E2_calls':0,'scope':'Synthetic child process tests on this OS only; not Windows execution evidence'},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('preflight');sub.add_parser('self-test')
    r=sub.add_parser('run')
    r.add_argument('--run-id',required=True);r.add_argument('--producer-session',required=True);r.add_argument('--runtime-id',required=True)
    r.add_argument('--expected-runner-commit',required=True);r.add_argument('--execute-authorized',action='store_true')
    r.add_argument('--concurrency-context',required=True,help='Real member resource window and concurrent workloads')
    e=sub.add_parser('export');e.add_argument('--run-id',required=True)
    args=p.parse_args()
    if hasattr(args,'run_id') and (not args.run_id or len(args.run_id)>100 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.run_id)):
        p.error('run-id accepts only letters/digits/dash/underscore')
    if args.action=='run':
        if not re.fullmatch(r'[a-z0-9-]+/s-[0-9a-f]{32}',args.producer_session):
            p.error('producer-session must be the assigned lowercase login/s-UUID32')
        if not re.fullmatch(r'[0-9a-f]{40}',args.expected_runner_commit):
            p.error('expected-runner-commit must be a full40-character Git SHA')
    if args.action=='preflight':print(json.dumps(verify()[0],indent=2));return 0
    if args.action=='self-test':self_test();return 0
    return run(args) if args.action=='run' else export(args)


if __name__=='__main__':
    raise SystemExit(main())
