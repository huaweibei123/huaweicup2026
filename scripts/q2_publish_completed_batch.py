"""Publish one already completed P2 batch after read-only validation and audit.

Default mode only validates. --publish creates missing derived artifacts, stages
only this batch, commits, and pushes the current branch once. Never runs solver/E0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / 'results/a/q2-yuanzhifang/feedback-20260924'


def utc():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(path.read_bytes())


def execute(argv, *, cwd=ROOT, timeout=120):
    return subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout, check=True)


def receipt_save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + '.tmp')
    staged.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(staged, path)


def clean_index(command=execute):
    staged = command(['git', 'diff', '--cached', '--name-only', '-z']).stdout
    if staged:
        raise ValueError('unrelated staged files exist; refusing to publish')


def batch_files_only(batch, spec):
    """Keep accidental files and other batches out of this commit."""
    root_names = {'spec.json', 'ledger.json', 'summary.json', 'summary.csv',
                  'measurement-audit.json', 'MEASUREMENT.md'}
    run_names = {'run.json', 'solver.stdout.txt', 'solver.stderr.txt',
                 'E0.stdout.txt', 'E0.stderr.txt', 'result.json.gz',
                 'trace.json.gz', 'result.txt'}
    folders = {case + '-' + spec['methods'][0]['variant'] for case in spec['cases']}
    for path in batch.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(batch)
        parts = relative.parts
        if len(parts) == 1:
            if parts[0] in root_names or (parts[0].startswith('board-feed-')
                    and parts[0].endswith('.json')):
                continue
        elif len(parts) == 2 and parts[0] in folders:
            if parts[1] in run_names or parts[1] == f"case_{parts[0][:3]}_multicore_res.json":
                continue
        raise ValueError('unexpected file inside completed batch: ' + relative.as_posix())


def validate(batch):
    spec, ledger = load(batch / 'spec.json'), load(batch / 'ledger.json')
    if ledger['state'] != 'completed' or ledger['stop_reason'] != 'all declared comparison units completed':
        raise ValueError('batch did not complete successfully')
    if hashlib.sha256((SCOPE / (batch.name + '-spec.json')).read_bytes()).hexdigest() != ledger['spec_sha256']:
        raise ValueError('frozen spec bytes differ from ledger')
    if len(spec['methods']) != 1 or spec['output'] != batch.relative_to(ROOT).as_posix():
        raise ValueError('single fixed method/output required')
    method = spec['methods'][0]
    if len(spec['cases']) != len(set(spec['cases'])):
        raise ValueError('duplicate declared case')
    n = len(spec['cases'])
    if ledger['charged_calls'] != {'solver': n, 'E0': n, 'E1': 0, 'E2': 0}:
        raise ValueError('charged call grid incomplete')
    expected = [f"{spec['output']}/{case}-{method['variant']}/run.json" for case in spec['cases']]
    if ledger['attempts'] != expected or len(ledger['reservations']) != 2*n:
        raise ValueError('attempt grid or reservations incomplete')
    reservations = [(r['attempt_id'], r['stage']) for r in ledger['reservations']]
    if len(set(reservations)) != 2*n:
        raise ValueError('duplicate reservation')
    last_e0 = None
    for case, name in zip(spec['cases'], expected):
        run_path = ROOT / name
        run = load(run_path)
        if (run['status'] != 'ok' or run['case_id'] != case or run['cores'] != spec['cores']
                or run['method'] != method or run['solver_commit'] != spec['solver_commit']
                or run['source_hashes'] != ledger['source_hashes']
                or run['calls'] != {'solver': 1, 'E0': 1, 'E1': 0, 'E2': 0}
                or run['stages']['E0']['status'] != 'ok'):
            raise ValueError('unsuccessful or mismatched run: ' + name)
        if {(run['attempt_id'], stage) for stage in ('solver', 'E0')} - set(reservations):
            raise ValueError('run lacks reservation: ' + name)
        report = load(run_path.parent / 'solver.stdout.txt')
        certified = report.get('capacity_certified')
        spill = run['metrics']['data_movement_bytes']['spill_added_copy_bytes']
        if type(certified) is not bool or (certified and spill > 0):
            raise ValueError('capacity certificate missing or contradicted by spill: ' + name)
        stamp = run['stages']['E0']['finished_at']
        last_e0 = max(last_e0, stamp) if last_e0 else stamp
    return spec, ledger, last_e0


def one_feed(batch):
    feeds = [p for p in batch.glob('board-feed-*.json') if not p.name.endswith('-preflight.json')]
    if len(feeds) > 1:
        raise ValueError('ambiguous existing board feeds')
    return feeds[0] if feeds else None


def verify_audit(batch, commit, sidecar, command=execute):
    command([sys.executable, '-X', 'utf8', '-B', '-m', 'src.q2.feedback.audit_batch',
             '--batch', str(batch), '--spec-commit', commit, '--output', str(sidecar)])
    fresh = load(sidecar)
    saved = batch / 'measurement-audit.json'
    if saved.exists():
        old = load(saved)
        fresh.pop('created_at_utc', None)
        old.pop('created_at_utc', None)
        if fresh != old:
            raise ValueError('existing measurement audit disagrees with fresh audit')
    else:
        shutil.copyfile(sidecar, saved)
    return saved


def stage_commit_push(batch, command=execute):
    clean_index(command)
    rel = batch.relative_to(ROOT).as_posix()
    branch = command(['git', 'branch', '--show-current']).stdout.decode().strip()
    if not branch or not branch.startswith('codex/'):
        raise ValueError('expected a named codex/ branch')
    command(['git', 'add', '-A', '--', rel])
    staged = [p for p in command(['git', 'diff', '--cached', '--name-only', '-z']).stdout.decode().split('\0') if p]
    if not staged or any(p != rel and not p.startswith(rel + '/') for p in staged):
        raise ValueError('staged paths exceed named batch or are empty')
    command(['git', 'diff', '--cached', '--check'])
    command(['git', 'commit', '-m', f'Audit and publish completed P2 {batch.name} batch'])
    head = command(['git', 'rev-parse', 'HEAD']).stdout.decode().strip()
    return branch, head


def process(batch, spec_commit, receipt, publish=False, command=execute):
    batch = batch.resolve()
    receipt = receipt.resolve()
    if not batch.is_relative_to(SCOPE) or receipt.is_relative_to(ROOT):
        raise ValueError('batch must be in P2 scope and receipt outside repository')
    if receipt.exists():
        raise FileExistsError('receipt path already exists; use a fresh run directory')
    record = {'batch': batch.relative_to(ROOT).as_posix(), 'mode': 'publish' if publish else 'validate',
              'started_at_utc': utc(), 'status': 'started', 'solver_calls': 0, 'E0_calls': 0}
    receipt_save(receipt, record)
    try:
        spec, ledger, last_e0 = validate(batch)
        spec_path = (SCOPE / (batch.name + '-spec.json')).relative_to(ROOT).as_posix()
        frozen = command(['git', 'show', f'{spec_commit}:{spec_path}']).stdout
        if frozen != (ROOT / spec_path).read_bytes() or json.loads(frozen) != spec:
            raise ValueError('spec commit does not match saved fixed spec')
        record.update(status='validated', last_E0_finished_at_utc=last_e0,
                      spec_sha256=ledger['spec_sha256'], complete_cells=len(spec['cases']))
        receipt_save(receipt, record)
        if not publish:
            return record
        clean_index(command)
        feed = one_feed(batch)
        exported_now = feed is None
        if feed is None:
            command([sys.executable, '-X', 'utf8', '-B', '-m', 'src.q2.feedback.export_board',
                     '--batch', str(batch)])
            feed = one_feed(batch)
        if feed is None or not feed.with_name(feed.stem + '-preflight.json').exists():
            raise ValueError('board feed/preflight missing after export')
        observed_key = ('post_successful_export_return_observed_at_utc' if exported_now
                        else 'existing_feed_observed_at_utc')
        record.update(feed=feed.relative_to(ROOT).as_posix(),
                      feed_sha256=hashlib.sha256(feed.read_bytes()).hexdigest(),
                      **{observed_key: utc()})
        receipt_save(receipt, record)
        summary = batch / 'summary.json'
        csv = batch / 'summary.csv'
        if summary.exists() != csv.exists():
            raise ValueError('partial existing analysis')
        if not summary.exists():
            command([sys.executable, '-X', 'utf8', '-B', '-m', 'src.q2.feedback.analyze',
                     '--batch', str(batch)])
        batch_files_only(batch, spec)
        sidecar = receipt.parent / (batch.name + '-fresh-audit.json')
        if sidecar.exists():
            raise FileExistsError(sidecar)
        verify_audit(batch, spec_commit, sidecar, command)
        record.update(status='audited', audit_completed_at_utc=utc(),
                      audit_sha256=hashlib.sha256((batch / 'measurement-audit.json').read_bytes()).hexdigest())
        receipt_save(receipt, record)
        branch, head = stage_commit_push(batch, command)
        record.update(status='committed', branch=branch, commit=head,
                      commit_completed_observed_at_utc=utc())
        receipt_save(receipt, record)
        record['push_started_at_utc'] = utc()
        receipt_save(receipt, record)
        try:
            command(['git', '-c', 'http.version=HTTP/1.1', '-c', 'http.postBuffer=52428800',
                     '-c', 'pack.threads=1', 'push', 'origin', f'HEAD:refs/heads/{branch}'], timeout=180)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            record.update(status='push_unknown', push_failed_or_ambiguous_observed_at_utc=utc(),
                          push_error_type=type(error).__name__)
            receipt_save(receipt, record)
            raise
        record.update(status='pushed', push_completed_at_utc=utc())
        receipt_save(receipt, record)
        return record
    except Exception as error:
        if record['status'] != 'push_unknown':
            record.update(status='failed', failed_at_utc=utc(), failure_type=type(error).__name__,
                          failure_message=str(error)[:240])
            receipt_save(receipt, record)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True, type=Path)
    parser.add_argument('--spec-commit', required=True)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    result = process(args.batch, args.spec_commit, args.receipt, args.publish)
    print(json.dumps({'status': result['status'], 'cells': result['complete_cells'],
                      'commit': result.get('commit')}))


if __name__ == '__main__':
    main()
