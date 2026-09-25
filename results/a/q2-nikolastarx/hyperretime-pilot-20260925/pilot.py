"""Three frozen P2 gap→hyperrefine→retime cells; partial mechanism pilot.

One worker. No algorithm branch depends on case ID. One native E2 per cell;
independent E0 only if native M strictly improves that cell's old E0.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.direct import derive_multicore_plan
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config
from src.q2_nikolastarx.adaptive_guarded import check_e2_source, native_e2, score_adapter
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.evaluate_feedback import monitored
from src.q2_nikolastarx.gap_candidate import build as gap_build
from src.q2_nikolastarx.gap_hyperrefine import refine
from src.q2_nikolastarx.gap_retime import retime

CASES = ('003', '043', '056')
CORES = 5
LIMITS = {'cells': 3, 'workers': 1, 'construct_e2_seconds_per_cell': 60,
          'E0_seconds_per_cell': 60, 'batch_seconds': 360,
          'rss_bytes': 4 << 30, 'region_width': 16, 'E2': 3,
          'E0': 3, 'E1': 0, 'retries': 0}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def save(path, value):
    Path(path).write_bytes(encode(value))


def pack(path, value):
    raw = encode(value)
    zipped = gzip.compress(raw, mtime=0)
    if gzip.decompress(zipped) != raw:
        raise AssertionError('gzip roundtrip mismatch')
    Path(path).write_bytes(zipped)
    return {'raw_sha256': sha(raw), 'gzip_sha256': sha(zipped), 'raw_bytes': len(raw)}


def archive_file(path):
    raw = Path(path).read_bytes()
    zipped = gzip.compress(raw, mtime=0)
    if gzip.decompress(zipped) != raw:
        raise AssertionError('artifact gzip roundtrip mismatch')
    Path(str(path) + '.gz').write_bytes(zipped)
    return {'raw_sha256': sha(raw), 'gzip_sha256': sha(zipped), 'raw_bytes': len(raw)}


def import_preflight(executable, e2_root):
    """Check only imports; never construct or call the evaluator."""
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
    result = subprocess.run([str(executable), '-B', '-c', code, str(e2_root)],
                            text=True, capture_output=True, timeout=10)
    if result.returncode:
        raise RuntimeError(f'E2 import preflight failed: returncode={result.returncode}; '
                           f'stdout={result.stdout!r}; stderr={result.stderr!r}')
    return json.loads(result.stdout)


def manifest_inputs(args):
    manifest_raw = (ROOT / 'docs/a/source-manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    files = {row['path']: row for row in manifest['files']}
    checked = {}
    for name in sorted(files):
        if name.startswith('code/') or name == 'data/config.txt' or name in {
            f'data/case_{case}.json' for case in CASES}:
            path = (ROOT / 'data/raw/a/official' / name) if name.startswith('code/') else args.raw_root / Path(name).name
            raw = path.read_bytes()
            if sha(raw) != files[name]['sha256'] or len(raw) != files[name]['bytes']:
                raise ValueError('official source mismatch: ' + name)
            checked[name] = sha(raw)
    identity = check_e2_source(args.e2_root)
    return {'official_manifest_sha256': sha(manifest_raw), 'official_files': checked,
            'official_code_hash': manifest['official_code_hash'], 'e2': identity}


def old_cell(args, case):
    folder = args.old_run / f'{case}-k5'
    graph_path = args.raw_root / f'case_{case}.json'
    graph_raw = graph_path.read_bytes()
    config_raw = (args.raw_root / 'config.txt').read_bytes()
    plan_raw = (folder / 'plan.json').read_bytes()
    result_raw = (folder / 'result.json').read_bytes()
    ledger = json.loads((folder / 'online/solver.json').read_bytes())
    plan, result = json.loads(plan_raw), json.loads(result_raw)
    if (ledger.get('status') != 'ok' or ledger.get('request_in_flight')
            or ledger.get('graph_sha256') != sha(graph_raw)
            or ledger.get('config_sha256') != sha(config_raw)
            or ledger.get('plan_sha256') != sha(plan_raw)
            or result.get('scene') != 'B' or result.get('num_cores') != CORES
            or type(result.get('makespan')) is not int):
        raise ValueError('old scored cell identity mismatch: ' + case)
    derive_multicore_plan(json.loads(graph_raw), plan)
    return {'folder': str(folder), 'graph_sha256': sha(graph_raw),
            'config_sha256': sha(config_raw), 'plan_sha256': sha(plan_raw),
            'result_sha256': sha(result_raw), 'old_makespan': result['makespan'],
            'old_added_copy_bytes': result['data_movement_bytes']['added_copy_bytes']}


def worker(args):
    started = time.perf_counter()
    cell = args.case
    path = args.output / f'{cell}-k5'
    row = json.loads((path / 'old.json').read_bytes())
    graph = json.loads((args.raw_root / f'case_{cell}.json').read_bytes())
    config_path = args.raw_root / 'config.txt'
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    old_plan = json.loads((args.old_run / f'{cell}-k5/plan.json').read_bytes())
    stages = {}
    at = time.perf_counter()
    seed, seed_meta = gap_build(graph, CORES, config)
    stages['gap_seconds'] = time.perf_counter() - at
    if seed != old_plan:
        raise ValueError('cold gap seed differs from old production plan')
    seed_bytes = mandatory_copy_work(graph, seed, config['bandwidth'])['transfer_bytes']
    at = time.perf_counter()
    refined, refine_meta = refine(graph, seed, config, region_width=16)
    stages['hyperrefine_seconds'] = time.perf_counter() - at
    refined_bytes = mandatory_copy_work(graph, refined, config['bandwidth'])['transfer_bytes']
    if (seed_bytes != refine_meta['before_original_copy_bytes']
            or refined_bytes != refine_meta['after_original_copy_bytes']
            or refined_bytes > seed_bytes):
        raise AssertionError('independent original COPY byte mismatch')
    if refined_bytes < seed_bytes:
        at = time.perf_counter()
        selected, retime_meta = retime(graph, refined, config)
        stages['retime_seconds'] = time.perf_counter() - at
        if mandatory_copy_work(graph, selected, config['bandwidth'])['transfer_bytes'] != refined_bytes:
            raise AssertionError('fixed assignment retime changed original COPY bytes')
    else:
        selected, retime_meta = seed, None
        stages['retime_seconds'] = 0.0
    derive_multicore_plan(graph, selected)
    artifacts = {'seed': pack(path / 'seed-plan.json.gz', seed),
                 'refined': pack(path / 'refined-plan.json.gz', refined),
                 'selected': pack(path / 'selected-plan.json.gz', selected)}
    plan_raw = encode(selected)
    (path / 'plan.json').write_bytes(plan_raw)
    ledger_path = path / 'e2-ledger.json'
    ledger = {'status': 'running', 'request_in_flight': False,
              'possible_E0_fallback_calls': 0,
              'calls': {'E0': 0, 'E1': 0, 'E2': 0, 'E2_api_attempted': 0,
                        'native_returns': 0, 'E0_fallback': 0}, 'attempts': []}
    save(ledger_path, ledger)
    at = time.perf_counter()
    def checked_native(p):
        try:
            return native_e2(args.e2_root, graph, config_path, p,
                             timeout=max(0.001, 60 - (time.perf_counter() - started)))
        except subprocess.CalledProcessError as error:
            save(path / 'native-subprocess-error.json', {
                'kind': 'CalledProcessError', 'returncode': error.returncode,
                'stdout': error.stdout, 'stderr': error.stderr})
            raise

    oracle = score_adapter(
        checked_native,
        ledger, ledger_path, remaining_wall=lambda: 60 - (time.perf_counter() - started))
    score = oracle(selected)
    stages['native_e2_seconds'] = time.perf_counter() - at
    attempt = ledger['attempts'][0]
    record = attempt['record']
    if (len(ledger['attempts']) != 1 or attempt['status'] != 'native'
            or record.get('route') != 'native' or record.get('status') != 'ok'
            or record.get('problem') != 2 or score['status'] != 'ok'
            or type(score['makespan']) is not int
            or type(score['added_copy_bytes']) is not int
            or score['makespan'] < 0 or score['added_copy_bytes'] < 0
            or ledger['calls']['E0_fallback'] or ledger['request_in_flight']):
        raise ValueError('native P2 E2 evidence unavailable')
    ledger['status'] = 'ok'
    save(ledger_path, ledger)
    result = {'case': cell, 'cores': CORES, 'source_commit': args.runner_commit,
              'old': row, 'seed_matches_old_plan': True,
              'seed_original_copy_bytes': seed_bytes,
              'refined_original_copy_bytes': refined_bytes,
              'selected_original_copy_bytes': refined_bytes,
              'seed_meta': seed_meta, 'refine_meta': refine_meta,
              'retime_meta': retime_meta, 'stages': stages,
              'native_record': record, 'score': score,
              'artifacts': artifacts, 'selected_plan_sha256': sha(plan_raw),
              'cold_candidate_e2_to_plan_wall_seconds': time.perf_counter() - started,
              'needs_independent_E0': score['makespan'] < row['old_makespan'],
              'scope': 'Partial three-cell mechanism pilot; not a full production solver or 500-cell score'}
    save(path / 'candidate.json', result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', required=True, type=Path)
    parser.add_argument('--old-run', required=True, type=Path)
    parser.add_argument('--e2-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runner-commit', required=True)
    parser.add_argument('--python', required=True, type=Path)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--case', choices=CASES)
    args = parser.parse_args()
    args.raw_root, args.old_run, args.e2_root = (p.resolve(strict=True) for p in
                                                (args.raw_root, args.old_run, args.e2_root))
    args.output = args.output.resolve()
    args.python = args.python.absolute()
    if not args.python.is_file() or Path(sys.executable).absolute() != args.python:
        raise ValueError('parent and native worker must use requested Python')
    if args.worker:
        worker(args)
        return
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != args.runner_commit:
        raise ValueError('runner commit must be full current HEAD')
    relative = Path(__file__).resolve().relative_to(ROOT).as_posix()
    if Path(__file__).read_bytes() != subprocess.check_output(
            ['git', 'show', args.runner_commit + ':' + relative], cwd=ROOT):
        raise ValueError('runner script differs from frozen commit')
    source_names = ('gap_candidate.py', 'gap_hyperrefine.py', 'gap_retime.py',
                    'gap_calendar.py', 'binary_hypercut.py', 'hypergraph_cost.py',
                    'adaptive_guarded.py', 'candidate_ddr.py')
    source_hashes = {}
    for name in source_names:
        relative = 'src/q2_nikolastarx/' + name
        raw = (ROOT / relative).read_bytes()
        if raw != subprocess.check_output(['git', 'show', args.runner_commit + ':' + relative], cwd=ROOT):
            raise ValueError('constructor source drift: ' + name)
        source_hashes[relative] = sha(raw)
    started = time.perf_counter()
    identities = manifest_inputs(args)
    e2_imports = import_preflight(args.python, args.e2_root)
    old = {case: old_cell(args, case) for case in CASES}
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
               'runner_commit': args.runner_commit, 'limits': LIMITS,
               'source': identities, 'source_hashes': source_hashes, 'old': old,
               'python': str(args.python), 'e2_import_preflight': e2_imports,
               'prior_batch': {'status': 'stopped_uncertain_native_e2',
                               'E2_api_attempted': 1, 'possible_E0_fallback_calls': 1,
                               'independent_E0_calls': 0},
               'calls': {'E2': 0, 'E0': 0, 'E1': 0}, 'cells': []}
    save(args.output / 'batch.json', receipt)
    deadline = started + LIMITS['batch_seconds']
    try:
        for case in CASES:
            if time.perf_counter() >= deadline:
                raise TimeoutError('batch wall exhausted')
            folder = args.output / f'{case}-k5'
            folder.mkdir(exist_ok=False)
            save(folder / 'old.json', old[case])
            command = [str(args.python), '-B', str(Path(__file__).resolve()), '--worker',
                       '--case', case, '--raw-root', str(args.raw_root), '--old-run', str(args.old_run),
                       '--e2-root', str(args.e2_root), '--output', str(args.output),
                       '--runner-commit', args.runner_commit, '--python', str(args.python)]
            process = monitored(command, folder / 'candidate-process',
                                min(deadline, time.perf_counter() + 60), 4 << 30)
            receipt['cells'].append({'case': case, 'candidate_process': process})
            ledger_path = folder / 'e2-ledger.json'
            if ledger_path.exists():
                recorded = json.loads(ledger_path.read_bytes())
                receipt['calls']['E2'] += recorded['calls']['E2_api_attempted']
                receipt['cells'][-1]['e2_request_in_flight'] = recorded['request_in_flight']
                receipt['cells'][-1]['e0_fallback_count'] = recorded['calls']['E0_fallback']
            save(args.output / 'batch.json', receipt)
            if process['status'] != 'ok' or process.get('surviving_pids'):
                raise RuntimeError('candidate process failed; stop batch')
            candidate = json.loads((folder / 'candidate.json').read_bytes())
            ledger = json.loads(ledger_path.read_bytes())
            if ledger['status'] != 'ok' or ledger['request_in_flight'] or len(ledger['attempts']) != 1:
                raise RuntimeError('E2 evidence unknown; stop batch')
            receipt['cells'][-1]['native_artifacts'] = {
                'e2-ledger': archive_file(ledger_path),
                'candidate': archive_file(folder / 'candidate.json')}
            save(args.output / 'batch.json', receipt)
            if candidate['needs_independent_E0']:
                e0 = folder / 'e0'
                e0.mkdir()
                argv = [str(args.python), '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                        str(args.raw_root / f'case_{case}.json'), str(folder / 'plan.json'),
                        '--config', str(args.raw_root / 'config.txt'),
                        '--output', str(e0 / 'result.json'), '--trace-output', str(e0 / 'trace.json'),
                        '--log-output', str(e0 / 'official.log')]
                receipt['calls']['E0'] += 1
                save(args.output / 'batch.json', receipt)
                e0_process = monitored(argv, e0 / 'process',
                                       min(deadline, time.perf_counter() + 60), 4 << 30)
                receipt['cells'][-1]['e0_process'] = e0_process
                save(args.output / 'batch.json', receipt)
                if e0_process['status'] != 'ok' or e0_process.get('surviving_pids'):
                    raise RuntimeError('independent E0 failed; stop batch')
                actual = json.loads((e0 / 'result.json').read_bytes())
                native = candidate['native_record']
                if (actual['makespan'] != native['makespan']
                        or actual['cross_task_traffic'] != native['cross_task_traffic']
                        or actual['data_movement_bytes'] != native['data_movement_bytes']):
                    raise ValueError('native E2 and independent E0 mismatch; stop batch')
                receipt['cells'][-1]['E0_makespan'] = actual['makespan']
                receipt['cells'][-1]['e0_artifacts'] = {
                    'result': archive_file(e0 / 'result.json'),
                    'trace': archive_file(e0 / 'trace.json'),
                    'log': archive_file(e0 / 'official.log')}
                save(args.output / 'batch.json', receipt)
        receipt['status'] = 'completed'
    except Exception as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt.update(finished_at=datetime.now(timezone.utc).isoformat(),
                       batch_wall_seconds=time.perf_counter() - started)
        save(args.output / 'batch.json', receipt)


if __name__ == '__main__':
    main()
