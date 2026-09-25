"""One-shot 003/K2 pair: exactly two sequential official E0 attempts."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LIMIT = 64 << 20


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def preflight():
    manifest = json.loads((ROOT / 'manifest.json').read_bytes())
    if manifest.get('schema') != 'q2-r05-pair-v1' or manifest.get('case') != '003' or manifest.get('cores') != 2:
        raise ValueError('Wrong fixed pair protocol')
    if manifest.get('order') != ['seed', 'recovered'] or manifest.get('limits') != {
        'workers': 1, 'E0': 2, 'E2': 0, 'retries': 0, 'stage_seconds': 180,
        'batch_seconds': 360, 'rss_bytes': 4 << 30, 'child_file_bytes': LIMIT}:
        raise ValueError('Pair limits changed')
    for rel, expected in manifest['files'].items():
        p = (ROOT / rel).resolve(strict=True)
        if not p.is_relative_to(ROOT.resolve()) or sha(p) != expected:
            raise ValueError('Capsule input hash mismatch: ' + rel)
    for label in ('seed', 'recovered'):
        p = ROOT / f'plans/{label}.json.gz'
        plan = json.loads(gzip.decompress(p.read_bytes()))
        if set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != 2:
            raise ValueError('Wrong frozen plan structure: ' + label)
    return manifest


def exec_official(label, folder):
    # File size limit is inherited by official E0 and covers its raw outputs,
    # stdout and stderr opened by the process monitor before this exec.
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
    code = ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'
    graph = ROOT / 'data/raw/a/official/data/case_003.json'
    config = ROOT / 'data/raw/a/official/data/config.txt'
    argv = [sys.executable, '-B', str(code), str(graph), str(folder / 'plan.json'),
            '--config', str(config), '--output', str(folder / 'result.json'),
            '--trace-output', str(folder / 'trace.json'),
            '--log-output', str(folder / 'official.log')]
    os.execv(sys.executable, argv)


def run(output):
    manifest = preflight()
    if output.exists():
        raise ValueError('Output already exists; no retry/resume')
    from src.q2_nikolastarx.evaluate_feedback import monitored
    started = time.perf_counter()
    deadline = started + 360
    output.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'running', 'manifest_sha256': sha(ROOT / 'manifest.json'),
               'scope': 'fixed saved-plan proxy-rejection audit; not online solver score',
               'calls': {'E0_reserved': 0, 'E2': 0}, 'rows': [],
               'limits': manifest['limits']}
    save(output / 'batch.json', receipt)
    try:
        for label in ('seed', 'recovered'):
            if time.perf_counter() >= deadline:
                raise TimeoutError('Batch deadline before E0 dispatch')
            folder = output / label
            folder.mkdir(exist_ok=False)
            plan_gz = ROOT / f'plans/{label}.json.gz'
            plan_raw = gzip.decompress(plan_gz.read_bytes())
            (folder / 'plan.json').write_bytes(plan_raw)
            row = {'label': label, 'status': 'E0_in_flight',
                   'original_plan_sha256': sha(plan_gz),
                   'plan_sha256': sha(folder / 'plan.json'), 'E0_reserved': 1}
            receipt['rows'].append(row)
            receipt['calls']['E0_reserved'] += 1
            save(output / 'batch.json', receipt)
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--exec-official', label, '--folder', str(folder)]
            process = monitored(command, folder / 'process',
                                min(deadline, time.perf_counter() + 180), 4 << 30)
            row['process'] = process
            save(output / 'batch.json', receipt)
            if process.get('status') != 'ok' or process.get('surviving_pids'):
                raise RuntimeError('E0 failed or uncertain: ' + str(process.get('status')))
            result = json.loads((folder / 'result.json').read_bytes())
            movement = result.get('data_movement_bytes')
            if (result.get('scene') != 'B' or result.get('num_cores') != 2
                    or type(result.get('makespan')) is not int
                    or not isinstance(movement, dict)):
                raise ValueError('Official result identity/metrics missing')
            row.update(status='verified', result_sha256=sha(folder / 'result.json'),
                       makespan=result['makespan'], data_movement_bytes=movement)
            save(output / 'batch.json', receipt)
        receipt['status'] = 'completed'
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt['batch_seconds'] = time.perf_counter() - started
        save(output / 'batch.json', receipt)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--exec-official', choices=('seed', 'recovered'))
    ap.add_argument('--folder', type=Path)
    a = ap.parse_args()
    if a.exec_official:
        if a.folder is None:
            ap.error('--folder required')
        exec_official(a.exec_official, a.folder)
    elif a.output:
        run(a.output.resolve())
    else:
        ap.error('--output required')


if __name__ == '__main__':
    main()
