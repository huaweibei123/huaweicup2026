"""A single independently budgeted case/method worker. Launched by stage_b only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from .construct import ROOT, OFFICIAL
from .proposals import specifications

PYTHON = getattr(sys, '_base_executable', sys.executable)
CONFIG = ROOT / 'data/raw/a/official/data/config.txt'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    """Durable replacement; reservation is on disk before any evaluator launch."""
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def rel(path):
    return path.relative_to(ROOT).as_posix()


def allowance(remaining, final=False):
    return max(0, min(105 if final else 120, remaining - (15 if final else 120)))


class Calls:
    def __init__(self, folder):
        self.path = folder / 'calls.json'
        if self.path.exists():
            raise FileExistsError('A ledger cannot be reset; request carry-forward scheduling')
        self.records = []
        self.persist()

    def persist(self):
        save(self.path, {'maximum': 32, 'charged': len(self.records), 'calls': self.records})

    def reserve(self, phase, command, now):
        if len(self.records) >= (32 if phase == 'final' else 31):
            raise RuntimeError('official call budget exhausted (last slot reserved)')
        record = {'slot': 32 if phase == 'final' else len(self.records)+1,
                  'charged_index': len(self.records)+1, 'phase': phase,
                  'reserved_elapsed': now, 'command': command,
                  'launched': False, 'status': 'reserved'}
        self.records.append(record)
        self.persist()
        return record


def command_run(command, folder, timeout, on_launch=None):
    started = time.monotonic()
    with (folder/'stdout.txt').open('wb') as out, (folder/'stderr.txt').open('wb') as err:
        process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err)
        if on_launch is not None:
            on_launch(process.pid)
        try:
            returncode = process.wait(timeout=max(0, timeout-(time.monotonic()-started)))
            status = 'completed'
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
            status = 'timeout'
    elapsed = time.monotonic()-started
    return {'status': status, 'returncode': returncode, 'pid': process.pid, 'launched': True,
            'wall_seconds': elapsed, 'timeout_seconds': timeout,
            'timeout_overshoot_seconds':max(0,elapsed-timeout)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder', type=Path, required=True)
    p.add_argument('--case', choices=['002', '008', '044'], required=True)
    p.add_argument('--method', choices=['D', 'M1', 'M2'], required=True)
    p.add_argument('--started', type=float, required=True)
    p.add_argument('--deadline', type=float, required=True)
    a = p.parse_args()
    if sys.stdin.readline().strip() != 'GO':
        raise RuntimeError('worker must be assigned to its job before starting')
    folder = a.folder.resolve()
    folder.relative_to(ROOT/'results/a/q2-yuanzhifang/stage-b-20260924-042906')
    elapsed = lambda: time.monotonic()-a.started
    remaining = lambda: a.deadline-time.monotonic()
    calls = Calls(folder)
    graph = ROOT/f'data/raw/a/official/data/case_{a.case}.json'
    rows, proposals, seen, incumbent = [], [], {}, None
    metadata = {'case': a.case, 'method': a.method, 'cores': 4, 'seed': 0,
                'graph': rel(graph), 'graph_sha256': sha(graph), 'config_sha256': sha(CONFIG),
                'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                'source_hashes': {rel(s): sha(s) for s in sorted((ROOT/'src/q2').glob('*.py'))},
                'python': platform.python_version(), 'platform': platform.platform(),
                'uv_lock_sha256': sha(ROOT/'uv.lock'), 'status': 'running'}
    save(folder/'identity.json', metadata)

    def evaluate(plan, phase):
        nonlocal incumbent
        limit = allowance(remaining(), phase == 'final')
        if limit <= 0:
            return None
        sequence = len(calls.records)+1
        directory = folder/f'eval-{sequence:02d}-{phase}'
        directory.mkdir()
        command = [PYTHON, '-X', 'utf8', '-B', rel(OFFICIAL/'multicore_cut_evaluate_problem_2.py'),
                   rel(graph), rel(plan), '--config', rel(CONFIG), '-o', rel(directory/'result.json'),
                   '--trace-output', rel(directory/'trace.json'), '--log-output', rel(directory/'summary.txt')]
        row = calls.reserve(phase, ['python', *command[1:]], elapsed())
        row.update(plan=rel(plan), plan_sha256=sha(plan), output=rel(directory))
        calls.persist()
        # Reservation remains charged even if process creation fails or is interrupted.
        row['launch_attempted'] = True
        calls.persist()
        def launched(pid):
            row.update(launched=True, pid=pid)
            calls.persist()
        measured = command_run(command, directory, limit, launched)
        row.update(measured)
        if row['status'] == 'completed':
            if row['returncode'] == 0 and all((directory/name).is_file() for name in ('result.json','trace.json','summary.txt')):
                result = json.loads((directory/'result.json').read_text(encoding='utf-8'))
                row.update(status='ok', makespan=result['makespan'], movement=result['data_movement_bytes'],
                           peak=result['memory_peak_by_core'])
            else:
                text = (directory/'stderr.txt').read_text(encoding='utf-8', errors='replace')
                known = ('dependency order violation', 'subgraph priority order violates',
                         'dependency cycle', '[STEP2 ERROR] no spill victim')
                row['status'] = 'rejected' if any(marker in text for marker in known) else 'error'
        row['completed_elapsed'] = elapsed()
        calls.persist()
        save(directory/'record.json', row)
        rows.append(dict(row))
        if phase != 'final' and row['status'] == 'ok' and (incumbent is None or row['makespan'] < incumbent['makespan']):
            incumbent = dict(row)
            save(folder/'incumbent.json', incumbent)
        return row

    def generate(name, command):
        directory = folder/name
        directory.mkdir()
        limit = allowance(remaining())
        if limit <= 0:
            measured = {'name':name, 'status':'not_started_time_reserve', 'completed_elapsed':elapsed()}
            save(directory/'generation.json', measured)
            proposals.append(measured)
            return None
        actual_command = command(directory)
        measured = command_run(actual_command, directory, limit)
        measured.update(name=name, completed_elapsed=elapsed(), command=['python',*actual_command[1:]])
        if measured['status'] == 'completed' and measured['returncode'] != 0:
            text = (directory/'stdout.txt').read_text(encoding='utf-8',errors='replace')
            measured['status'] = 'construction_rejected' if measured['returncode']==2 and '"construction_rejected"' in text else 'generator_error'
        save(directory/'generation.json', measured)
        proposals.append(measured)
        path = directory/'plan.json'
        return path if measured['status']=='completed' and measured['returncode']==0 and path.is_file() else None

    try:
        baseline = generate('baseline', lambda d: [PYTHON,'-X','utf8','-B','-m','src.q2.construct',rel(graph),'--cores','4','--output',rel(d/'plan.json')])
        first = evaluate(baseline, 'initial') if baseline else None
        if not first or first['status'] != 'ok':
            metadata['status'] = 'baseline_failed'
            metadata['failure_kind'] = 'baseline_rejected' if first and first['status']=='rejected' else 'baseline_timeout_or_error'
            metadata['halt_stage'] = metadata['failure_kind'] != 'baseline_rejected'
        else:
            # Exact plan JSON with insertion order retained, not graph/isomorphic equivalence.
            def key(path):
                return json.dumps(json.loads(path.read_text(encoding='utf-8')), separators=(',', ':'), ensure_ascii=False)
            seen[key(baseline)] = rel(baseline)
            for number, specification in enumerate(specifications(a.method), 1):
                if remaining() <= 120 or len(calls.records) >= 31:
                    metadata['early_stop'] = 'time_reserve_or_call_limit'
                    break
                plan = generate(f'proposal-{number:02d}', lambda d: [PYTHON,'-X','utf8','-B','-m','src.q2.propose_cli',
                    '--graph',rel(graph),'--baseline',rel(baseline),'--method',a.method,
                    '--spec',json.dumps(specification,separators=(',',':')),'--output',rel(d/'plan.json')])
                proposals[-1]['specification'] = specification
                if plan is None:
                    proposals[-1]['outcome'] = 'generation_failed'
                    if proposals[-1]['status'] == 'not_started_time_reserve':
                        metadata['early_stop'] = 'time_reserve'
                        break
                    if proposals[-1]['status'] != 'construction_rejected':
                        metadata.update(halt_stage=True,failure_kind='proposal_timeout_or_error')
                        break
                    continue
                identity = key(plan)
                if identity in seen:
                    proposals[-1].update(outcome='duplicate_exact_plan', duplicate_of=seen[identity])
                    continue
                seen[identity] = rel(plan)
                row = evaluate(plan, 'explore')
                proposals[-1]['outcome'] = row['status'] if row else 'time_reserve'
                if row and row['status'] not in {'ok','rejected'}:
                    metadata.update(halt_stage=True,failure_kind='evaluation_timeout_or_error')
                    break
            final = evaluate(ROOT/incumbent['plan'], 'final') if not metadata.get('halt_stage') else None
            if final and final['status'] == 'ok':
                original = json.loads((ROOT/incumbent['output']/'result.json').read_text(encoding='utf-8'))
                confirmed = json.loads((ROOT/final['output']/'result.json').read_text(encoding='utf-8'))
                metadata['full_repeat_equal'] = original == confirmed
                metadata['status'] = 'confirmed' if original == confirmed else 'repeat_mismatch'
                metadata['final'] = final
            else:
                metadata['status'] = 'confirmation_missing_or_failed'
            metadata.setdefault('early_stop', 'declared_finite_family_exhausted')
    except Exception as error:
        metadata.update(status='worker_exception', failure={'type':type(error).__name__,'message':str(error)})
        raise
    finally:
        tail_started = time.monotonic()
        metadata.update(incumbent=incumbent, calls_charged=len(calls.records),
                        search_end_elapsed=elapsed(), proposals=proposals, results=rows)
        save(folder/'summary.json', metadata)
        # Entire output-dependent scan/hashing is inside the externally killable job.
        manifest = {p.relative_to(folder).as_posix(): {'bytes':p.stat().st_size,'sha256':sha(p)}
                    for p in sorted(folder.rglob('*')) if p.is_file()
                    and p.name not in {'controller-samples.jsonl','worker-stdout.txt','worker-stderr.txt'} }
        save(folder/'artifacts.json', manifest)
        save(folder/'worker-completion.json', {'elapsed_through_hashes':elapsed(),
                'worker_tail_seconds':time.monotonic()-tail_started,
                'boundary':'after evidence hashing; final marker write and process cleanup timed by controller'})
        print(json.dumps({'case':a.case,'method':a.method,'status':metadata['status'],
                          'calls':len(calls.records),'best':incumbent['makespan'] if incumbent else None}),flush=True)
    return 0 if metadata['status'] == 'confirmed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
