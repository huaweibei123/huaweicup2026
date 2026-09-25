"""One-worker Linux P2 COPY-event pilot. No implicit retry or resume."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
CASES = ('005', '009', '015')
LIMIT = 4 << 30
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes())


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def file_in_root(rel: str) -> Path:
    name = Path(rel)
    if name.is_absolute() or '..' in name.parts or not rel:
        raise ValueError('unsafe capsule path: ' + rel)
    path = (ROOT / name).resolve(strict=True)
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('capsule path escapes root: ' + rel)
    return path


def metrics(record, *, official: bool):
    if not isinstance(record, dict) or record.get('status') not in (None, 'ok'):
        raise ValueError('evaluation status is not ok')
    if official and (record.get('scene') != 'B' or record.get('num_cores') != 5):
        raise ValueError('expected official scene B / five cores')
    if not official and (record.get('route') != 'native' or record.get('problem') != 2):
        raise ValueError('E2 did not return native P2 score')
    movement = record.get('data_movement_bytes')
    keys = {'original_graph_copy_bytes', 'scheduled_copy_bytes', 'added_copy_bytes',
            'partition_added_copy_bytes', 'spill_added_copy_bytes'}
    if (type(record.get('makespan')) is not int or record['makespan'] < 0
            or not isinstance(movement, dict) or set(movement) != keys
            or any(type(v) is not int or v < 0 for v in movement.values())):
        raise ValueError('missing or incomplete exact evaluation metrics')
    return {'makespan': record['makespan'], 'data_movement_bytes': movement}


def plan_key(plan):
    if not isinstance(plan, dict) or set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('plan has wrong submission keys')
    if len(plan['core_schedules']) != 5:
        raise ValueError('plan does not have five schedules')
    return hashlib.sha256(json.dumps(plan, sort_keys=True, allow_nan=False).encode()).hexdigest()


def preflight():
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        raise RuntimeError('pilot requires Linux x86_64')
    manifest_path = ROOT / 'capsule-manifest.json'
    manifest = read(manifest_path)
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('capsule manifest needs a nonempty files map')
    required = {'fixed-p2-manifest.json', 'scripts/e2_linux_native.py',
                'src/q2_nikolastarx/adaptive_copyevent_guarded.py',
                'src/q2_nikolastarx/evaluate_feedback.py',
                'results/a/q2-nikolastarx/copyevent-linux-pilot-20260925/runner.py'}
    required |= {f'data/raw/a/official/data/case_{c}.json' for c in CASES}
    required |= {f'seeds/{c}-k5.json' for c in CASES}
    required |= {f'expected/{c}-k5.json' for c in CASES}
    required |= {'data/raw/a/official/data/config.txt',
                 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'}
    if not required <= files.keys() or not all(manifest.get(k) for k in
            ('solver_source_commit', 'runner_source_commit')):
        raise ValueError('capsule identity incomplete')
    for rel, expected in files.items():
        if sha(file_in_root(rel)) != expected:
            raise ValueError('capsule input drift: ' + rel)
    fixed = ROOT / 'fixed-p2-manifest.json'
    solver_alias = ROOT / 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json'
    if not solver_alias.exists() or sha(solver_alias) != sha(fixed):
        raise ValueError('solver fixed-P2 manifest alias differs or is missing')
    fixed_doc = read(fixed)
    if len(fixed_doc.get('e2_sources', {})) != 50:
        raise ValueError('fixed E2 source list must have 50 entries')
    for rel, expected in fixed_doc['e2_sources'].items():
        capsule_rel = 'e2-src/' + rel
        if files.get(capsule_rel) != expected:
            raise ValueError('E2 source missing from capsule identity: ' + rel)
    identity_path = ROOT / 'runtime-identity.json'
    identity = read(identity_path)
    receipt = ROOT / 'e2-linux-build.json'
    receipt_hash = identity.get('linux_receipt_sha256')
    binary_hash = identity.get('linux_binary_sha256')
    if (not receipt.exists() or sha(receipt) != receipt_hash or
            read(receipt).get('binary', {}).get('sha256') != binary_hash):
        raise ValueError('Linux build receipt identity mismatch')
    binary = ROOT / 'e2-src' / fixed_doc['binary']['path']
    if sha(binary) != binary_hash:
        raise ValueError('Linux native binary identity mismatch')
    return manifest, identity, receipt, manifest_path


def seed_check(case, out, receipt_hash, binary_hash):
    from src.q2_nikolastarx.adaptive_guarded import check_e2_source, native_e2
    source = check_e2_source(ROOT / 'e2-src',
        linux_build_receipt=ROOT / 'e2-linux-build.json',
        linux_build_receipt_sha256=receipt_hash, linux_binary_sha256=binary_hash)
    graph = read(ROOT / f'data/raw/a/official/data/case_{case}.json')
    plan = read(ROOT / f'seeds/{case}-k5.json')
    plan_key(plan)
    record = native_e2(source['root'], graph,
        ROOT / 'data/raw/a/official/data/config.txt', plan, 75)
    save(out, record)


def monitored_process(argv, folder, deadline):
    from src.q2_nikolastarx.evaluate_feedback import monitored
    return monitored(argv, folder, deadline, LIMIT)


def require_ok(process):
    if process.get('status') != 'ok' or process.get('surviving_pids'):
        raise RuntimeError('process failed or outcome uncertain: ' + str(process.get('status')))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--seed-check', choices=CASES)
    ap.add_argument('--seed-out', type=Path)
    ap.add_argument('--receipt-sha256')
    ap.add_argument('--binary-sha256')
    args = ap.parse_args()
    if args.seed_check:
        if not args.seed_out or not args.receipt_sha256 or not args.binary_sha256:
            ap.error('seed check needs output and both hashes')
        seed_check(args.seed_check, args.seed_out, args.receipt_sha256, args.binary_sha256)
        return
    if args.output is None:
        ap.error('--output required')
    started = time.perf_counter()
    deadline = started + 600
    manifest, identity, receipt_path, manifest_path = preflight()
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('write output outside frozen capsule root')
    output.mkdir(parents=True, exist_ok=False)
    batch = {'status': 'running', 'capsule_sha256': sha(manifest_path),
             'runtime_identity_sha256': sha(ROOT / 'runtime-identity.json'),
             'linux_receipt_sha256': sha(receipt_path),
             'solver_source_commit': manifest['solver_source_commit'],
             'runner_source_commit': manifest['runner_source_commit'],
             'platform': platform.platform(), 'python': sys.version,
             'limits': {'workers': 1, 'seed_E2': 3, 'online_E2': 12,
                        'total_E2': 15, 'final_E0': 3, 'retries': 0,
                        'solver_seconds': 90, 'E0_seconds': 60,
                        'batch_seconds': 600, 'rss_bytes': LIMIT},
             'calls': {'seed_E2_reserved': 0, 'solver_reserved': 0,
                       'online_E2_attempted': 0, 'final_E0_reserved': 0},
             'rows': []}
    save(output / 'batch.json', batch)
    try:
        # Revalidate saved E0 truth before any cold solver dispatch.
        for case in CASES:
            if time.perf_counter() >= deadline:
                raise TimeoutError('batch deadline before seed checks')
            folder = output / f'{case}-k5'
            folder.mkdir()
            row = {'case': case, 'cores': 5, 'status': 'seed_check_running',
                   'seed_E2_attempted': None, 'online_E2_attempted': None}
            batch['rows'].append(row)
            expected = read(ROOT / f'expected/{case}-k5.json')
            seed_truth = metrics(expected, official=True)
            seed = read(ROOT / f'seeds/{case}-k5.json')
            plan_key(seed)
            row['seed_plan_sha256'] = sha(ROOT / f'seeds/{case}-k5.json')
            row['expected_sha256'] = sha(ROOT / f'expected/{case}-k5.json')
            row['seed_E0'] = seed_truth
            row['seed_E2_attempted'] = 1  # Reserve before crossing native boundary.
            batch['calls']['seed_E2_reserved'] += 1
            save(output / 'batch.json', batch)
            cmd = [sys.executable, '-B', str(Path(__file__).resolve()),
                   '--seed-check', case, '--seed-out', str(folder / 'seed-e2.json'),
                   '--receipt-sha256', identity['linux_receipt_sha256'],
                   '--binary-sha256', identity['linux_binary_sha256']]
            row['seed_process'] = monitored_process(cmd, folder / 'seed-process',
                min(deadline, time.perf_counter() + 90))
            save(output / 'batch.json', batch)
            require_ok(row['seed_process'])
            native = read(folder / 'seed-e2.json')
            if metrics(native, official=False) != seed_truth:
                raise ValueError('saved E0 / native E2 seed mismatch: ' + case)
            row['seed_E2'] = metrics(native, official=False)
            row['status'] = 'seed_verified'
            save(output / 'batch.json', batch)
        for row in batch['rows']:
            case = row['case']
            if time.perf_counter() >= deadline:
                raise TimeoutError('batch deadline before solver')
            folder = output / f'{case}-k5'
            row['status'] = 'solver_running'
            batch['calls']['solver_reserved'] += 1
            save(output / 'batch.json', batch)
            cmd = [sys.executable, '-B', '-m', 'src.q2_nikolastarx.adaptive_copyevent_guarded',
                   str(ROOT / f'data/raw/a/official/data/case_{case}.json'),
                   '--config', str(ROOT / 'data/raw/a/official/data/config.txt'),
                   '--cores', '5', '--output', str(folder / 'plan.json'),
                   '--evidence', str(folder / 'online'), '--e2-root', str(ROOT / 'e2-src'),
                   '--linux-build-receipt', str(ROOT / 'e2-linux-build.json'),
                   '--linux-build-receipt-sha256', identity['linux_receipt_sha256'],
                   '--linux-binary-sha256', identity['linux_binary_sha256'], '--wall', '90']
            try:
                row['solver_process'] = monitored_process(cmd, folder / 'solver-process',
                    min(deadline, time.perf_counter() + 90))
            finally:
                ledger_path = folder / 'online/solver.json'
                if ledger_path.exists():
                    ledger = read(ledger_path)
                    row['online_E2_attempted'] = ledger.get('calls', {}).get('E2_api_attempted')
                    row['online_E0_fallback'] = ledger.get('calls', {}).get('E0_fallback')
                    row['solver_ledger_sha256'] = sha(ledger_path)
                    if type(row['online_E2_attempted']) is int:
                        batch['calls']['online_E2_attempted'] += row['online_E2_attempted']
                save(output / 'batch.json', batch)
            require_ok(row['solver_process'])
            if not ledger_path.exists():
                raise ValueError('solver ledger absent; online E2 count unknown')
            ledger = read(ledger_path)
            if (ledger.get('status') != 'ok' or ledger.get('request_in_flight')
                    or ledger.get('possible_E0_fallback_calls') != 0
                    or row['online_E0_fallback'] != 0
                    or ledger.get('calls', {}).get('E0') != 0
                    or type(row['online_E2_attempted']) is not int
                    or not 1 <= row['online_E2_attempted'] <= 4
                    or len(ledger.get('attempts', [])) != row['online_E2_attempted']
                    or any(a.get('status') != 'native' for a in ledger['attempts'])):
                raise ValueError('solver E2 ledger incomplete, fallback or uncertain')
            plan_path = folder / 'plan.json'
            plan = read(plan_path)
            key = plan_key(plan)
            if ledger.get('plan_sha256') != sha(plan_path):
                raise ValueError('solver selected plan bytes mismatch')
            matching = [a['record'] for a in ledger['attempts'] if a.get('plan_sha256') == key]
            if not matching:
                raise ValueError('selected plan has no native E2 score')
            selected = metrics(matching[-1], official=False)
            row['selected_E2'] = selected
            row['plan_sha256'] = sha(plan_path)
            row['solver_wall_seconds'] = row['solver_process']['wall_seconds']
            row['status'] = 'final_E0_running'
            batch['calls']['final_E0_reserved'] += 1
            save(output / 'batch.json', batch)
            cmd = [sys.executable, '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                   str(ROOT / f'data/raw/a/official/data/case_{case}.json'), str(plan_path),
                   '--config', str(ROOT / 'data/raw/a/official/data/config.txt'),
                   '--output', str(folder / 'result.json'),
                   '--trace-output', str(folder / 'trace.json'),
                   '--log-output', str(folder / 'official.log')]
            row['E0_process'] = monitored_process(cmd, folder / 'e0-process',
                min(deadline, time.perf_counter() + 60))
            save(output / 'batch.json', batch)
            require_ok(row['E0_process'])
            actual = metrics(read(folder / 'result.json'), official=True)
            if actual != selected:
                raise ValueError('selected native E2 / independent official E0 mismatch')
            row['final_E0'] = actual
            row['result_sha256'] = sha(folder / 'result.json')
            row['status'] = 'verified'
            save(output / 'batch.json', batch)
            print(json.dumps({'case': case, 'M': actual['makespan'],
                              'solver_wall_seconds': row['solver_wall_seconds']}), flush=True)
        batch['status'] = 'completed'
    except BaseException as error:
        batch.update(status='stopped', error=repr(error))
        raise
    finally:
        batch['batch_seconds'] = time.perf_counter() - started
        save(output / 'batch.json', batch)


if __name__ == '__main__':
    main()
