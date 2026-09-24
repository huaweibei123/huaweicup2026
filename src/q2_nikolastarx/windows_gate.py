"""Opt-in, seven-case Windows process gate. No solver/evaluator imports or calls.

`plan` verifies frozen files and prints scope without creating native resources.
`run --execute-native` is for a separately authorized Windows owner only.
"""
from __future__ import annotations

import argparse
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from . import windows_process as wp

ROOT = Path(__file__).resolve().parents[2]
FILES = ('src/q2_nikolastarx/windows_process.py', 'src/q2_nikolastarx/windows_gate.py')
CASES = ('normal', 'nonzero', 'timeout_grandchild', 'rss_limit',
         'observation_failure', 'assign_failure', 'cleanup_unknown')
BATCH_SECONDS = 60.0
WORK_SECONDS = 4.0
CLEANUP_SECONDS = 2.0
RSS_LIMIT = 512 * 1024**2


def frozen(commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('A full fixed runner commit is required')
    result = {}
    for name in FILES:
        raw = (ROOT / name).read_bytes()
        if raw != subprocess.check_output(['git', 'show', commit + ':' + name], cwd=ROOT):
            raise ValueError('Unfrozen gate source: ' + name)
        result[name] = hashlib.sha256(raw).hexdigest()
    return result


def plan(commit):
    return {'runner_commit': commit, 'files': frozen(commit), 'cases': list(CASES),
        'maximum_direct_CreateProcess_requests': 7, 'fixture_Popen_requests': 2,
        'actual_OS_process_count': 'record Job accounting; interpreter redirectors may add OS processes',
        'workers': 1, 'retries': 0, 'batch_seconds': BATCH_SECONDS,
        'case_work_seconds': WORK_SECONDS, 'adapter_cleanup_seconds': CLEANUP_SECONDS,
        'witness_cleanup_seconds': CLEANUP_SECONDS, 'job_active_limit': 16,
        'job_commit_limit_bytes': RSS_LIMIT, 'ordinary_rss_stop_bytes': RSS_LIMIT,
        'rss_test_stop_bytes': 96 * 1024**2, 'rss_test_allocation_bytes': 128 * 1024**2,
        'solver_calls': 0, 'E0': 0, 'E1': 0, 'E2': 0, 'dispatched': 0,
        'scope': 'Only native process/control synthetic fixtures; not algorithm or performance acceptance'}


def fixture(case, folder):
    if case == 'normal':
        return ("import sys;sys.stdout.buffer.write(" + repr('正常 stdout\n'.encode('utf-8'))
                + ");sys.stderr.buffer.write(" + repr(b'stderr\n') + ")")
    if case == 'nonzero':
        return 'raise SystemExit(7)'
    if case == 'timeout_grandchild':
        grandchild_file = str(folder / 'grandchild-pid.txt')
        middle_file = str(folder / 'middle-pid.txt')
        leaf = 'import time;time.sleep(15)'
        middle = ('import subprocess,sys,time;from pathlib import Path;'
                  f'p=subprocess.Popen([sys.executable,"-B","-c",{leaf!r}]);'
                  f'Path({grandchild_file!r}).write_text(str(p.pid));time.sleep(15)')
        return ('import subprocess,sys,time;from pathlib import Path;'
                f'p=subprocess.Popen([sys.executable,"-B","-c",{middle!r}]);'
                f'Path({middle_file!r}).write_text(str(p.pid));time.sleep(15)')
    if case == 'rss_limit':
        return 'import time;data=bytearray(128*1024**2);data[::4096]=b"x"*(len(data)//4096);time.sleep(15)'
    if case == 'cleanup_unknown':
        return 'import time;time.sleep(.15)'
    return 'import time;time.sleep(15)'


class GateJob(wp.NativeJob):
    """Fault injection plus independent last-chance witness, scoped to this Job.

    The witness deliberately does not repair the adapter's unknown receipt. It
    verifies cleanup via the non-injected API before closing the final handle.
    This belongs only to the synthetic gate, never the production monitor.
    """
    def __init__(self, case, outer_deadline):
        super().__init__()
        self.case, self.outer_deadline = case, outer_deadline
        self.cleanup_fault_armed = False
        self.witness = {'verified': False}

    def prepare(self):
        super().prepare()
        limits = wp.ExtendedLimit()
        limits.basic.flags = wp.KILL_ON_JOB_CLOSE | 0x8 | 0x200
        limits.basic.active_limit = 16
        limits.job_memory = RSS_LIMIT  # Commit bound, deliberately not called RSS.
        self.call('SetInformationJobObject', self.job, 9, ct.byref(limits), ct.sizeof(limits))
        got = wp.ExtendedLimit()
        self.call('QueryInformationJobObject', self.job, 9, ct.byref(got), ct.sizeof(got), None)
        if (got.basic.flags, got.basic.active_limit, got.job_memory) != (limits.basic.flags, 16, RSS_LIMIT):
            raise RuntimeError('Synthetic gate Job limits did not read back')

    def call(self, name, *args):
        if self.case == 'assign_failure' and name == 'AssignProcessToJobObject':
            raise OSError(5, 'deliberately injected assignment failure; no Resume allowed')
        if self.case == 'observation_failure' and self.resumed and name == 'K32GetProcessMemoryInfo':
            raise OSError(5, 'deliberately injected memory observation failure')
        return super().call(name, *args)

    def poll(self):
        code = super().poll()
        if self.case == 'cleanup_unknown' and code is not None:
            self.cleanup_fault_armed = True
        return code

    def accounting(self):
        if self.cleanup_fault_armed:
            raise OSError(5, 'deliberately injected cleanup accounting failure')
        return super().accounting()

    def close(self):
        end = min(self.outer_deadline, time.perf_counter() + CLEANUP_SECONDS)
        try:
            if self.job is None and self.pid is None:
                self.witness = {'verified': True, 'created': False}
            else:
                # Direct base calls bypass only this case's injected accounting
                # error. Any real native error still fails the independent witness.
                if self.pid is not None and not self.assigned:
                    # Native termination checks the held handle and also tries
                    # cleanup when that observation itself fails.
                    wp.NativeJob.terminate(self)
                accounting = wp.NativeJob.accounting(self)
                if accounting['active_processes']:
                    wp.NativeJob.terminate(self)
                while True:
                    accounting = wp.NativeJob.accounting(self)
                    code = wp.NativeJob.poll(self)
                    observed = time.perf_counter()
                    self.witness = {'verified': False, 'accounting': accounting,
                                    'exit_code': code, 'observed_at': wp._utc(), 'within_budget': observed < end}
                    if accounting['active_processes'] == 0 and (self.pid is None or code is not None):
                        self.witness['verified'] = True
                        if observed >= end:
                            raise TimeoutError('Independent cleanup proven only after witness deadline')
                        break
                    if observed >= end:
                        raise TimeoutError('Independent cleanup witness deadline')
                    time.sleep(.01)
        except BaseException as error:
            self.witness.update(error=repr(error))
            raise
        finally:
            super().close()  # KILL_ON_JOB_CLOSE fallback is not itself proof.
            if time.perf_counter() >= end:
                self.witness.update(within_budget=False, error='Independent cleanup/close crossed witness deadline')
                raise TimeoutError('Independent cleanup/close crossed witness deadline')


def expected(case, receipt, folder, witness):
    if not witness.get('verified') or witness.get('within_budget') is False or witness.get('error') or receipt.get('close_error'):
        return False
    if case != 'cleanup_unknown' and receipt.get('cleanup_error'):
        return False
    if case not in ('assign_failure', 'observation_failure') and receipt.get('error'):
        return False
    if case == 'normal':
        return (receipt['status'] == 'ok' and receipt['exit_code'] == 0 and receipt['cleanup_verified']
                and (folder/'process/stdout.txt').read_bytes() == '正常 stdout\n'.encode('utf-8')
                and (folder/'process/stderr.txt').read_bytes() == b'stderr\n')
    if case == 'nonzero':
        return receipt['status'] == 'failed' and receipt['exit_code'] == 7 and receipt['cleanup_verified']
    if case == 'timeout_grandchild':
        return (receipt['status'] == 'timeout' and receipt['cleanup_verified']
                and (folder/'middle-pid.txt').is_file() and (folder/'grandchild-pid.txt').is_file()
                and witness.get('accounting', {}).get('total_processes', 0) >= 3)
    if case == 'rss_limit':
        return (receipt['status'] == 'rss_limit' and receipt['stop_dispatch'] and receipt['cleanup_verified']
                and receipt['observer_inclusive_peak_rss_bytes'] > 96*1024**2)
    if case == 'assign_failure':
        return (receipt['status'] == 'runner_error' and receipt['created'] and not receipt['resumed']
                and not receipt['assigned_before_resume'] and receipt['target_entry_entered'] is False
                and receipt['cleanup_verified'] and receipt['stop_dispatch']
                and 'deliberately injected assignment failure' in receipt.get('error', ''))
    if case == 'observation_failure':
        return (receipt['status'] == 'runner_error' and receipt['resumed'] and receipt['cleanup_verified']
                and receipt['stop_dispatch'] and 'deliberately injected memory observation failure' in receipt.get('error', ''))
    return (case == 'cleanup_unknown' and receipt['status'] == 'runner_error' and not receipt['cleanup_verified']
            and receipt['surviving_pids'] is None and receipt['stop_dispatch']
            and 'deliberately injected cleanup accounting failure' in receipt.get('cleanup_error', ''))


def run(output, identity, *, _factory=GateJob, _monitor=wp.monitored):
    if os.name != 'nt' or ct.sizeof(ct.c_void_p) != 8:
        raise RuntimeError('Native gate requires an explicitly authorized 64-bit Windows owner')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    end = start + BATCH_SECONDS
    report = {**identity, 'started_at': wp._utc(), 'status': 'running', 'results': [],
              'execution_environment': 'actual Windows; fill host provenance independently',
              'direct_creation_attempts': 0, 'direct_created_processes': 0}
    wp._save(output/'gate.json', report)
    for case in CASES:
        if time.perf_counter() + 2*CLEANUP_SECONDS >= end:
            report['stop_reason'] = 'insufficient_outer_cleanup_reserve'
            break
        folder = output / case
        folder.mkdir()
        code = fixture(case, folder)
        wp._save(folder/'fixture.json', {'argv': [sys.executable, '-B', '-c', code],
                                        'code_sha256': hashlib.sha256(code.encode()).hexdigest()})
        report['active_case'] = case
        wp._save(output/'gate.json', report)  # Durable reservation, no retry.
        backend = None
        receipt = None
        unexpected = None

        def make_backend():
            nonlocal backend
            backend = _factory(case, end)
            return backend

        try:
            receipt = _monitor([sys.executable, '-B', '-c', code], folder/'process',
                min(end - 2*CLEANUP_SECONDS, time.perf_counter() + WORK_SECONDS),
                96*1024**2 if case == 'rss_limit' else RSS_LIMIT,
                cwd=folder, env=dict(os.environ), cleanup_timeout=CLEANUP_SECONDS,
                _backend_factory=make_backend)
            witness = backend.witness if backend is not None else {'verified': False, 'reason': 'native backend not acquired'}
            ok = expected(case, receipt, folder, witness)
        except BaseException as error:
            unexpected, ok = repr(error), False
            # Controller/persistence failures never authorize a subsequent case.
            # If the monitor escaped before its cleanup, retain our held backend.
            if backend is not None and not backend.witness.get('verified'):
                try:
                    backend.close()
                except BaseException as cleanup_error:
                    unexpected += '; emergency close: ' + repr(cleanup_error)
            witness = backend.witness if backend is not None else {'verified': False, 'reason': 'no backend receipt'}
        row = {'case': case, 'passed': ok, 'receipt': receipt, 'independent_cleanup_witness': witness}
        if unexpected:
            row['controller_error'] = unexpected
        wp._save(folder/'result.json', row)
        report['results'].append({'case': case, 'passed': ok, 'status': receipt['status'] if receipt else 'controller_error'})
        # A controller exception may leave only the still-held native identity.
        report['direct_creation_attempts'] += int(receipt['creation_attempted'] if receipt else bool(backend and backend.creation_attempted))
        report['direct_created_processes'] += int(receipt['created'] if receipt else bool(backend and backend.pid is not None))
        wp._save(output/'gate.json', report)
        if not ok:
            report['stop_reason'] = 'first_unexpected_failure'
            break
    report.pop('active_case', None)
    report.update(finished_at=wp._utc(), wall_seconds=time.perf_counter()-start,
                  wall_scope='control execution, fixture and result persistence, cleanup witness; excludes final manifest serialization')
    report['status'] = 'pass' if len(report['results']) == len(CASES) and all(x['passed'] for x in report['results']) else 'failed'
    if report['wall_seconds'] > BATCH_SECONDS:
        report.update(status='failed', stop_reason='outer_budget_exceeded')
    report.setdefault('stop_reason', 'all_fixed_controls_completed')
    wp._save(output/'gate.json', report)
    wp._save(output/'manifest.json', {p.relative_to(output).as_posix(): {
        'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'manifest.json'})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'run'))
    parser.add_argument('--runner-commit', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--execute-native', action='store_true')
    args = parser.parse_args()
    identity = plan(args.runner_commit)
    if args.action == 'plan':
        print(json.dumps(identity, indent=2))
        return
    if not args.execute_native or args.output is None:
        parser.error('Native execution requires --execute-native and a new --output directory')
    report = run(args.output, identity)
    print(json.dumps({key: report[key] for key in ('status', 'stop_reason', 'wall_seconds', 'direct_created_processes')}))
    if report['status'] != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
