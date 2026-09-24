"""Windows process-tree monitor; importing this module launches nothing.

ABI/stdio/paused creation adapted from the limited G1-G4 Windows-tested helper:
569c65f:research/a/review/e2_p2_windows_20260924/gate_repair/gate_helper.py.
Working-set observation derives from 6f91055:research/a/review/
e2_cli_fix_validation_20260924/win_support.py. This adapter itself is unverified
on Windows. Creation is suspended, then assigned, then resumed exactly once.
"""
from __future__ import annotations

import ctypes as ct
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
DWORD, WORD, BOOL = ct.c_uint32, ct.c_uint16, ct.c_int32
HANDLE, SIZE_T = ct.c_void_p, ct.c_size_t
KILL_ON_JOB_CLOSE = 0x2000
HANDLE_LIST = 0x20002
CREATE_FLAGS = 0x4 | 0x08000000 | 0x400 | 0x80000
FORCED_EXIT = 0xE0000001


class BasicLimit(ct.Structure):
    _fields_ = [('user', ct.c_int64), ('job_user', ct.c_int64), ('flags', DWORD),
                ('min_ws', SIZE_T), ('max_ws', SIZE_T), ('active_limit', DWORD),
                ('affinity', SIZE_T), ('priority', DWORD), ('scheduling', DWORD)]


class IOCounters(ct.Structure):
    _fields_ = [(n, ct.c_uint64) for n in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class ExtendedLimit(ct.Structure):
    _fields_ = [('basic', BasicLimit), ('io', IOCounters), ('process_memory', SIZE_T),
                ('job_memory', SIZE_T), ('peak_process_memory', SIZE_T), ('peak_job_memory', SIZE_T)]


class Accounting(ct.Structure):
    _fields_ = [(n, ct.c_int64) for n in ('user', 'kernel', 'period_user', 'period_kernel')] + [
        (n, DWORD) for n in ('faults', 'total', 'active', 'terminated')]


class StartupInfo(ct.Structure):
    _fields_ = [('cb', DWORD), ('reserved', ct.c_wchar_p), ('desktop', ct.c_wchar_p), ('title', ct.c_wchar_p)] + [
        (n, DWORD) for n in ('x', 'y', 'xsize', 'ysize', 'xchars', 'ychars', 'fill', 'flags')] + [
        ('show', WORD), ('reserved_size', WORD), ('reserved_bytes', ct.c_void_p),
        ('stdin', HANDLE), ('stdout', HANDLE), ('stderr', HANDLE)]


class StartupInfoEx(ct.Structure):
    _fields_ = [('info', StartupInfo), ('attributes', ct.c_void_p)]


class ProcessInfo(ct.Structure):
    _fields_ = [('process', HANDLE), ('thread', HANDLE), ('pid', DWORD), ('tid', DWORD)]


class ProcessMemory(ct.Structure):
    _fields_ = [('cb', DWORD), ('faults', DWORD)] + [(n, SIZE_T) for n in (
        'peak_working_set', 'working_set', 'peak_paged', 'paged', 'peak_nonpaged',
        'nonpaged', 'pagefile', 'peak_pagefile', 'private_bytes')]


def _save(path, record):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class NativeJob:
    """All native resources remain owned here even if creation/resume fails."""

    def __init__(self):
        if os.name != 'nt':
            raise OSError('Windows only; no POSIX or uncontained fallback')
        import msvcrt
        self.msvcrt = msvcrt
        self.k = ct.WinDLL('kernel32', use_last_error=True)
        self.job = self.process = self.thread = None
        self.pid = None
        self.handles = []
        self.events = []
        self.creation_attempted = self.assigned = self.resumed = self.resume_attempted = False
        signatures = {
            'GetCurrentProcess': ([], HANDLE), 'CloseHandle': ([HANDLE], BOOL),
            'GetHandleInformation': ([HANDLE, ct.POINTER(DWORD)], BOOL),
            'CreateJobObjectW': ([ct.c_void_p, ct.c_wchar_p], HANDLE),
            'SetInformationJobObject': ([HANDLE, ct.c_int, ct.c_void_p, DWORD], BOOL),
            'QueryInformationJobObject': ([HANDLE, ct.c_int, ct.c_void_p, DWORD, ct.POINTER(DWORD)], BOOL),
            'IsProcessInJob': ([HANDLE, HANDLE, ct.POINTER(BOOL)], BOOL),
            'AssignProcessToJobObject': ([HANDLE, HANDLE], BOOL),
            'TerminateJobObject': ([HANDLE, DWORD], BOOL),
            'TerminateProcess': ([HANDLE, DWORD], BOOL),
            'OpenProcess': ([DWORD, BOOL, DWORD], HANDLE),
            'WaitForSingleObject': ([HANDLE, DWORD], DWORD),
            'GetExitCodeProcess': ([HANDLE, ct.POINTER(DWORD)], BOOL),
            'ResumeThread': ([HANDLE], DWORD),
            'DuplicateHandle': ([HANDLE, HANDLE, HANDLE, ct.POINTER(HANDLE), DWORD, BOOL, DWORD], BOOL),
            'InitializeProcThreadAttributeList': ([ct.c_void_p, DWORD, DWORD, ct.POINTER(SIZE_T)], BOOL),
            'UpdateProcThreadAttribute': ([ct.c_void_p, DWORD, SIZE_T, ct.c_void_p, SIZE_T, ct.c_void_p, ct.c_void_p], BOOL),
            'DeleteProcThreadAttributeList': ([ct.c_void_p], None),
            'CreateProcessW': ([ct.c_wchar_p, ct.c_void_p, ct.c_void_p, ct.c_void_p, BOOL,
                                DWORD, ct.c_void_p, ct.c_wchar_p, ct.POINTER(StartupInfoEx), ct.POINTER(ProcessInfo)], BOOL),
            'K32GetProcessMemoryInfo': ([HANDLE, ct.POINTER(ProcessMemory), DWORD], BOOL),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.k, name)
            fn.argtypes, fn.restype = args, result

    def call(self, name, *args):
        result = getattr(self.k, name)(*args)
        error = ct.get_last_error()  # Before any subsequent native call/logging.
        if not result:
            raise OSError(error, name + ' failed')
        return result

    def own(self, value, kind):
        if not value:
            raise RuntimeError('Null handle: ' + kind)
        self.handles.append([value, kind, False])
        return value

    def close_one(self, value):
        entry = next(e for e in reversed(self.handles) if e[0] == value and not e[2])
        try:
            self.call('CloseHandle', value)
        except Exception as error:
            self.events.append({'close': entry[1], 'ok': False, 'error': repr(error)})
            raise
        entry[2] = True
        self.events.append({'close': entry[1], 'ok': True})

    def inherit(self, value, expected=False):
        flags = DWORD()
        self.call('GetHandleInformation', value, ct.byref(flags))
        if bool(flags.value & 1) != expected:
            raise RuntimeError('Unexpected inheritable handle')

    def prepare(self):
        # Anonymous, non-inheritable, unique: never manipulate another Job.
        self.job = self.own(self.call('CreateJobObjectW', None, None), 'job')
        self.inherit(self.job)
        limits = ExtendedLimit()
        limits.basic.flags = KILL_ON_JOB_CLOSE
        self.call('SetInformationJobObject', self.job, 9, ct.byref(limits), ct.sizeof(limits))
        got = ExtendedLimit()
        self.call('QueryInformationJobObject', self.job, 9, ct.byref(got), ct.sizeof(got), None)
        if got.basic.flags != KILL_ON_JOB_CLOSE:
            raise RuntimeError('Job limit readback mismatch')

    def create(self, argv, cwd, env, stdout, stderr, before_create):
        attributes = None
        duplicates = []
        try:
            current = self.k.GetCurrentProcess()
            with open(os.devnull, 'rb') as incoming:
                for stream in (incoming, stdout, stderr):
                    duplicate = HANDLE()
                    self.call('DuplicateHandle', current, self.msvcrt.get_osfhandle(stream.fileno()),
                              current, ct.byref(duplicate), 0, True, 2)
                    duplicates.append(self.own(duplicate.value, 'stdio_duplicate'))
                    self.inherit(duplicate.value, True)
                size = SIZE_T()
                result = self.k.InitializeProcThreadAttributeList(None, 1, 0, ct.byref(size))
                error = ct.get_last_error()
                if result or error != 122 or not size.value:
                    raise OSError(error, 'Attribute list sizing failed')
                storage = ct.create_string_buffer(size.value)
                self.call('InitializeProcThreadAttributeList', storage, 1, 0, ct.byref(size))
                attributes = storage
                whitelist = (HANDLE * 3)(*duplicates)
                self.call('UpdateProcThreadAttribute', attributes, 0, HANDLE_LIST,
                          ct.cast(whitelist, ct.c_void_p), ct.sizeof(whitelist), None, None)
                startup = StartupInfoEx()
                startup.info.cb, startup.info.flags = ct.sizeof(startup), 0x100
                startup.info.stdin, startup.info.stdout, startup.info.stderr = duplicates
                startup.attributes = ct.cast(attributes, ct.c_void_p)
                command = ct.create_unicode_buffer(subprocess.list2cmdline(argv))
                environment = ct.create_unicode_buffer('\0'.join(
                    f'{k}={v}' for k, v in sorted(env.items(), key=lambda p: p[0].upper())) + '\0\0')
                info = ProcessInfo()
                before_create()  # Persist reservation/check work deadline before OS call.
                self.creation_attempted = True
                self.call('CreateProcessW', argv[0], command, None, None, True, CREATE_FLAGS,
                          environment, str(cwd), ct.byref(startup), ct.byref(info))
                # Capture all successful native handles/PID before any fallible readback.
                self.pid = int(info.pid)
                self.process = self.own(info.process, 'process')
                self.thread = self.own(info.thread, 'primary_thread')
                self.inherit(self.process)
                self.inherit(self.thread)
                self.call('AssignProcessToJobObject', self.job, self.process)
                self.assigned = True
                member = BOOL()
                self.call('IsProcessInJob', self.process, self.job, ct.byref(member))
                if not member.value:
                    raise RuntimeError('Pre-resume Job membership readback failed')
        finally:
            if attributes is not None:
                self.k.DeleteProcThreadAttributeList(attributes)
            # All duplicate handles stay in the owner list if a close fails.
            errors = []
            for handle in duplicates:
                try:
                    self.close_one(handle)
                except Exception as error:
                    errors.append(repr(error))
            if errors:
                raise RuntimeError('Stdio handle cleanup failed: ' + repr(errors))

    def resume(self):
        if not self.assigned:
            raise RuntimeError('Cannot resume an unassigned process')
        self.resume_attempted = True
        previous = self.k.ResumeThread(self.thread)
        error = ct.get_last_error()
        if previous != 1:
            raise OSError(error if previous == 0xFFFFFFFF else 0, 'ResumeThread count was ' + str(previous))
        self.resumed = True
        self.close_one(self.thread)

    def accounting(self):
        info = Accounting()
        self.call('QueryInformationJobObject', self.job, 1, ct.byref(info), ct.sizeof(info), None)
        return {'active_processes': int(info.active), 'total_processes': int(info.total),
                'terminated_processes': int(info.terminated)}

    def pids(self):
        for capacity in (16, 64, 256, 1024, 4096, 16384):
            class PIDList(ct.Structure):
                _fields_ = [('assigned', DWORD), ('listed', DWORD), ('ids', SIZE_T * capacity)]
            info = PIDList()
            result = self.k.QueryInformationJobObject(self.job, 3, ct.byref(info), ct.sizeof(info), None)
            error = ct.get_last_error()
            if not result and error != 234:
                raise OSError(error, 'Job PID query failed')
            if result and info.assigned == info.listed <= capacity:
                pids = [int(info.ids[i]) for i in range(info.listed)]
                if len(pids) != len(set(pids)) or any(pid <= 0 for pid in pids):
                    raise RuntimeError('Invalid Job PID list')
                return pids
        raise RuntimeError('Complete Job PID list unavailable')

    def exited(self, handle):
        result = self.k.WaitForSingleObject(handle, 0)
        error = ct.get_last_error()
        if result not in (0, 258):
            raise OSError(error, 'Process wait failed')
        return result == 0

    def poll(self):
        if self.process is None or not self.exited(self.process):
            return None
        code = DWORD()
        self.call('GetExitCodeProcess', self.process, ct.byref(code))
        return int(code.value)

    def memory(self, handle):
        info = ProcessMemory()
        info.cb = ct.sizeof(info)
        self.call('K32GetProcessMemoryInfo', handle, ct.byref(info), ct.sizeof(info))
        return int(info.working_set)

    def sample(self):
        pids, rss, exits = self.pids(), 0, []
        for pid in pids:
            value = self.k.OpenProcess(0x100000 | 0x1000 | 0x10, False, pid)
            error = ct.get_last_error()
            if not value:
                # A listed process can exit before OpenProcess. Only a fresh complete
                # Job list excluding it disambiguates that race; access errors fail.
                if error == 87 and pid not in self.pids():
                    exits.append(pid)
                    continue
                raise OSError(error, 'OpenProcess for Job member failed')
            handle = self.own(value, 'sample_member')
            try:
                member = BOOL()
                self.call('IsProcessInJob', handle, self.job, ct.byref(member))
                if not member.value:
                    raise RuntimeError('Listed PID no longer names an owned Job member')
                if self.exited(handle):
                    exits.append(pid)
                    continue
                rss += self.memory(handle)
            finally:
                self.close_one(handle)
        return {**self.accounting(), 'pids': pids, 'rss_bytes': rss,
                'observer_rss_bytes': self.memory(self.k.GetCurrentProcess()), 'exited_during_sample': exits}

    def terminate(self):
        errors = []
        for name, handle in (('TerminateJobObject', self.job),
                             ('TerminateProcess', self.process if not self.assigned else None)):
            if handle is not None:
                if name == 'TerminateProcess':
                    try:
                        if self.exited(handle):
                            continue
                    except Exception as error:
                        errors.append(repr(error))
                        # Observation failure cannot release ownership. Still try
                        # to terminate this held, unassigned child; retain the
                        # observation error even if termination succeeds.
                try:
                    self.call(name, handle, FORCED_EXIT)
                except Exception as error:
                    # ERROR_ACCESS_DENIED also names an already-exited process.
                    # Only a fresh wait on this same held handle proves that race.
                    if name == 'TerminateProcess' and isinstance(error, OSError) and (getattr(error, 'winerror', None) or error.errno) == 5:
                        try:
                            if self.exited(handle):
                                self.events.append({'terminate_exit_race': True, 'error': repr(error), 'held_handle_signaled': True})
                                continue
                        except Exception as observation_error:
                            errors.append(repr(observation_error))
                    errors.append(repr(error))
        if errors:
            raise RuntimeError('Termination failure: ' + repr(errors))

    def close(self):
        errors = []
        # Job was acquired first and closes last; its handle is never inherited.
        for value, kind, closed in reversed(self.handles):
            if not closed:
                try:
                    self.close_one(value)
                except Exception as error:
                    errors.append({'kind': kind, 'error': repr(error)})
        if errors:
            raise RuntimeError('Handle close failure: ' + repr(errors))


def monitored(argv, folder, deadline, rss_limit, *, cwd=ROOT, env=None,
              cleanup_timeout=5.0, sample_interval=0.05, _backend_factory=NativeJob,
              _clock=time.perf_counter, _sleep=time.sleep):
    """common.monitored-compatible positional API; a fresh, exclusive receipt folder.

    deadline is absolute perf_counter time. env is copied explicitly; its values
    are never logged. Test-only backend injection does not validate Windows APIs.
    Unknown cleanup always returns runner_error/stop_dispatch with survivors=None.
    """
    start = _clock()
    if not isinstance(argv, (tuple, list)) or not argv or any(not isinstance(a, str) or '\0' in a for a in argv):
        raise ValueError('argv must be a literal nonempty string list')
    for name, value in (('deadline', deadline), ('rss_limit', rss_limit), ('cleanup_timeout', cleanup_timeout), ('sample_interval', sample_interval)):
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid ' + name)
    cwd, folder = Path(cwd).resolve(), Path(folder)
    environment = dict(os.environ if env is None else env)
    if any(not isinstance(k, str) or not k or '=' in k or '\0' in k or not isinstance(v, str) or '\0' in v for k, v in environment.items()):
        raise ValueError('Invalid environment mapping')
    # Explicit executable resolution avoids PATH/cwd ambiguity in CreateProcessW.
    executable = Path(argv[0])
    if not executable.is_absolute():
        executable = (cwd / executable).resolve()
    argv = [str(executable), *argv[1:]]
    receipt = {'argv': argv, 'cwd': str(cwd), 'started_at': _utc(), 'status': 'starting',
        'pid': None, 'exit_code': None, 'sample_interval_seconds': sample_interval,
        'observed_peak_rss_bytes': None, 'observer_inclusive_peak_rss_bytes': None,
        'rss_samples': 0, 'surviving_pids': None, 'cleanup_killed_pids': [],
        'creation_reserved': False, 'creation_reservation_persisted': False,
        'creation_attempted': False, 'created': False, 'resume_attempted': False, 'resumed': False, 'assigned_before_resume': False,
        'target_entry_entered': 'unknown; no target instrumentation',
        'process_exit_observed': False, 'cleanup_verified': False, 'stop_dispatch': False,
        'work_deadline': deadline, 'work_within_budget': None, 'cleanup_within_budget': None, 'within_budget': None,
        'env_sha256': hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest(),
        'containment': 'suspended creation -> Job assignment -> one resume; KILL_ON_JOB_CLOSE; no breakaway flags',
        'rss_scope': 'sampled sum of Job-member working sets plus separate observer; not a hard RSS cap'}
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / 'process.json'
    _save(path, receipt)
    backend = None
    cause = None
    try:
        with (folder / 'stdout.txt').open('xb') as stdout, (folder / 'stderr.txt').open('xb') as stderr:
            try:
                if _clock() >= deadline:
                    receipt.update(status='timeout', target_entry_entered=False, work_within_budget=False, stop_dispatch=True)
                else:
                    backend = _backend_factory()
                    backend.prepare()

                    def before_create():
                        if _clock() >= deadline:
                            raise TimeoutError('Deadline before native process creation')
                        receipt['creation_reserved'] = True
                        _save(path, receipt)
                        receipt['creation_reservation_persisted'] = True
                        if _clock() >= deadline:
                            raise TimeoutError('Deadline after reservation persistence; no native creation attempted')

                    backend.create(argv, cwd, environment, stdout, stderr, before_create)
                    receipt.update(pid=backend.pid, created=True, assigned_before_resume=backend.assigned)
                    _save(path, receipt)  # Real OS creation, even if resume fails next.
                    if _clock() >= deadline:
                        receipt.update(status='timeout', target_entry_entered=False, work_within_budget=False, stop_dispatch=True)
                    else:
                        backend.resume()
                        receipt.update(resumed=backend.resumed, status='running')
                        _save(path, receipt)
                        while True:
                            if _clock() >= deadline:
                                receipt.update(status='timeout', work_within_budget=False, stop_dispatch=True)
                                break
                            sample = backend.sample()
                            receipt['rss_samples'] += 1
                            for metric, value in (('observed_peak_rss_bytes', sample['rss_bytes']),
                                ('observer_inclusive_peak_rss_bytes', sample['rss_bytes'] + sample['observer_rss_bytes'])):
                                receipt[metric] = max(receipt[metric] or 0, value)
                            receipt['last_sample'] = {**sample, 'elapsed_seconds': _clock() - start}
                            code = backend.poll()
                            observed = _clock()
                            if code is not None:
                                receipt.update(exit_code=code, process_exit_observed=True, exit_observed_elapsed_seconds=observed-start)
                            if observed >= deadline:
                                receipt.update(status='timeout', work_within_budget=False, stop_dispatch=True,
                                               deadline_reason='Work completion not observed before deadline')
                                break
                            receipt['work_within_budget'] = True
                            if receipt['observer_inclusive_peak_rss_bytes'] > rss_limit:
                                receipt['status'] = 'rss_limit'
                                receipt['stop_dispatch'] = True
                                break
                            if code is not None:
                                receipt.update(status='ok' if code == 0 else 'failed', exit_code=code)
                                break
                            _sleep(min(sample_interval, max(0, deadline - _clock())))
            except BaseException as error:
                cause = error
                receipt.update(status='runner_error', error=repr(error), stop_dispatch=True,
                               work_within_budget=_clock() < deadline)
            finally:
                if backend is not None:
                    receipt.update(pid=backend.pid, created=backend.pid is not None,
                                   resume_attempted=backend.resume_attempted, resumed=backend.resumed, assigned_before_resume=backend.assigned)
                    receipt['creation_attempted'] = backend.creation_attempted
                    if not backend.resume_attempted:
                        receipt['target_entry_entered'] = False
                    try:
                        cleanup_end = min(_clock() + cleanup_timeout, deadline + cleanup_timeout)
                        receipt['cleanup_deadline'] = cleanup_end
                        if backend.pid is not None and not backend.assigned:
                            # Assign may fail after successful creation: the held
                            # suspended process handle is still our responsibility.
                            backend.terminate()
                        if backend.job is not None:
                            before = backend.accounting()
                            receipt['cleanup_before'] = before
                            if before['active_processes']:
                                receipt['cleanup_killed_pids'] = backend.pids()
                                backend.terminate()
                            while True:
                                accounting = backend.accounting()
                                receipt['cleanup_last_accounting'] = {**accounting, 'elapsed_seconds': _clock() - start}
                                code = backend.poll()
                                observed = _clock()
                                if accounting['active_processes'] == 0 and (backend.pid is None or code is not None):
                                    receipt.update(cleanup_verified=True, surviving_pids=[], exit_code=code,
                                                   process_exit_observed=code is not None, cleanup_within_budget=observed < cleanup_end)
                                    if observed >= cleanup_end:
                                        receipt.update(status='timeout' if receipt['status'] in ('ok', 'failed', 'timeout') else receipt['status'],
                                                       stop_dispatch=True, deadline_reason='Cleanup verified only after its deadline')
                                    break
                                if observed >= cleanup_end:
                                    receipt['cleanup_within_budget'] = False
                                    raise TimeoutError('No observed ActiveProcesses=0 and signaled direct child before cleanup deadline')
                                _sleep(min(sample_interval, max(0, cleanup_end - _clock())))
                        elif backend.pid is None:
                            receipt.update(cleanup_verified=True, surviving_pids=[], cleanup_within_budget=_clock() < cleanup_end)
                    except BaseException as error:
                        receipt.update(status='runner_error', cleanup_error=repr(error),
                                       cleanup_verified=False, surviving_pids=None, stop_dispatch=True)
                    finally:
                        try:
                            backend.close()
                        except BaseException as error:
                            receipt.update(status='runner_error', close_error=repr(error), stop_dispatch=True)
                        receipt['handle_events'] = backend.events
                        closed_at = _clock()
                        receipt['close_finished_elapsed_seconds'] = closed_at-start
                        if closed_at >= receipt.get('cleanup_deadline', deadline + cleanup_timeout):
                            receipt.update(cleanup_within_budget=False, stop_dispatch=True,
                                           deadline_reason='Cleanup/handle close not observed before its deadline')
                            if receipt['status'] in ('ok', 'failed', 'timeout'):
                                receipt['status'] = 'timeout'
                else:
                    # Native layer never existed, so no child was created.
                    receipt.update(cleanup_verified=True, surviving_pids=[], target_entry_entered=False,
                                   cleanup_within_budget=_clock() < deadline + cleanup_timeout)
    finally:
        finished = _clock()  # Includes closing the parent's stdout/stderr streams.
        if finished >= receipt.get('cleanup_deadline', deadline + cleanup_timeout):
            receipt['cleanup_within_budget'] = False
            receipt['deadline_reason'] = 'Cleanup and stream closure not observed before deadline'
            if receipt['status'] in ('ok', 'failed', 'timeout'):
                receipt['status'] = 'timeout'
        receipt['within_budget'] = receipt['work_within_budget'] is True and receipt['cleanup_within_budget'] is True
        receipt['deadline_status'] = 'within_budget' if receipt['within_budget'] else 'deadline_unverified'
        if not receipt['within_budget']:
            receipt['stop_dispatch'] = True
        receipt.update(finished_at=_utc(), wall_seconds=finished - start)
        _save(path, receipt)
    if cause is not None and not isinstance(cause, Exception):
        raise cause
    return receipt
