"""Host substitutes only: no solver, evaluator, Windows API or child is started."""
import ctypes as ct
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import windows_process as win


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        self.value += .001
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeJob:
    def __init__(self, mode='ok'):
        self.mode = mode
        self.job = self.pid = None
        self.creation_attempted = self.assigned = self.resumed = self.resume_attempted = False
        self.terminated = self.closed = False
        self.events = []
        self.args = None

    def prepare(self):
        if self.mode == 'job_fail':
            raise OSError('synthetic Job creation failure')
        self.job = 10

    def create(self, argv, cwd, env, stdout, stderr, before):
        before()
        self.creation_attempted = True
        self.args = argv, cwd, env.copy()
        if self.mode == 'create_fail':
            raise OSError(203, 'synthetic native creation failure')
        self.pid = 1234
        if self.mode == 'assign_fail':
            raise OSError('synthetic assignment failure')
        self.assigned = True
        stdout.write(b'synthetic bytes\n')

    def resume(self):
        self.resume_attempted = True
        if self.mode == 'resume_fail':
            raise OSError('synthetic ResumeThread failure')
        self.resumed = True

    def sample(self):
        if self.mode == 'observe_fail':
            raise OSError('synthetic RSS observation failure')
        return {'active_processes': 3, 'total_processes': 3, 'terminated_processes': 0,
                'pids': [1234, 1235, 1236], 'rss_bytes': 2000 if self.mode == 'rss' else 100,
                'observer_rss_bytes': 10, 'exited_during_sample': []}

    def poll(self):
        if self.mode == 'poll_fail':
            raise OSError('synthetic process wait failure')
        if self.mode == 'cleanup_stuck':
            return None
        if self.terminated:
            return win.FORCED_EXIT
        if self.mode == 'nonzero':
            return 7
        return 0 if self.mode in ('ok', 'close_fail', 'cleanup_query_fail') else None

    def accounting(self):
        if self.mode == 'cleanup_query_fail':
            raise OSError('synthetic Job accounting failure')
        active = 0 if self.terminated or self.mode in ('ok', 'nonzero', 'close_fail') or self.pid is None else 3
        if self.mode == 'cleanup_stuck':
            active = 3
        return {'active_processes': active, 'total_processes': int(self.pid is not None), 'terminated_processes': int(self.terminated)}

    def pids(self):
        return [1234, 1235, 1236]

    def terminate(self):
        self.terminated = True

    def close(self):
        self.closed = True
        if self.mode == 'close_fail':
            raise OSError('synthetic handle close failure')


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'receipt'
        self.clock = Clock()

    def run_fake(self, mode='ok', **kwargs):
        backend = FakeJob(mode)
        result = win.monitored(['python.exe', '-c', 'synthetic'], self.folder, 100.08, 1000,
            cwd=Path(self.temp.name), env={'SECRET_TEST_VALUE': 'must-not-be-logged'},
            cleanup_timeout=.08, _backend_factory=lambda: backend,
            _clock=self.clock, _sleep=self.clock.sleep, **kwargs)
        self.assertEqual(result, json.loads((self.folder / 'process.json').read_text()))
        self.assertGreater(result['wall_seconds'], 0)
        self.assertNotIn('must-not-be-logged', (self.folder / 'process.json').read_text())
        self.assertTrue(backend.closed)
        return backend, result

    def test_success_fixed_argv_environment_and_timing(self):
        backend, result = self.run_fake()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['exit_code'], 0)
        self.assertTrue(result['cleanup_verified'])
        self.assertEqual(result['surviving_pids'], [])
        self.assertEqual(result['observed_peak_rss_bytes'], 100)
        self.assertEqual(result['observer_inclusive_peak_rss_bytes'], 110)
        self.assertTrue(Path(backend.args[0][0]).is_absolute())
        self.assertFalse(result['stop_dispatch'])
        self.assertEqual((self.folder / 'stdout.txt').read_bytes(), b'synthetic bytes\n')

    def test_nonzero_is_completed_failure_with_known_cleanup(self):
        _, result = self.run_fake('nonzero')
        self.assertEqual((result['status'], result['exit_code']), ('failed', 7))
        self.assertTrue(result['cleanup_verified'])

    def test_timeout_cleans_all_synthetic_descendants(self):
        backend, result = self.run_fake('timeout')
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(backend.terminated)
        self.assertEqual(result['cleanup_killed_pids'], [1234, 1235, 1236])
        self.assertEqual(result['cleanup_last_accounting']['active_processes'], 0)
        self.assertTrue(result['cleanup_verified'])

    def test_rss_includes_observer_and_stops_dispatch(self):
        _, result = self.run_fake('rss')
        self.assertEqual(result['status'], 'rss_limit')
        self.assertTrue(result['stop_dispatch'])

    def test_job_failure_never_creates_child(self):
        backend, result = self.run_fake('job_fail')
        self.assertIsNone(result['pid'])
        self.assertFalse(backend.creation_attempted)
        self.assertEqual(result['status'], 'runner_error')

    def test_creation_failure_does_not_fabricate_dispatch(self):
        _, result = self.run_fake('create_fail')
        self.assertTrue(result['creation_attempted'])
        self.assertFalse(result['created'])
        self.assertIsNone(result['pid'])
        self.assertIsNone(result['exit_code'])

    def test_assignment_failure_preserves_created_pid_and_cleans_handle(self):
        backend, result = self.run_fake('assign_fail')
        self.assertEqual(result['pid'], 1234)
        self.assertTrue(result['created'])
        self.assertFalse(result['resumed'])
        self.assertFalse(result['assigned_before_resume'])
        self.assertFalse(result['target_entry_entered'])
        self.assertTrue(backend.terminated)
        self.assertTrue(result['cleanup_verified'])
        self.assertTrue(result['stop_dispatch'])

    def test_resume_failure_never_claims_entry_was_impossible(self):
        _, result = self.run_fake('resume_fail')
        self.assertEqual(result['pid'], 1234)
        self.assertIn('unknown', result['target_entry_entered'])
        self.assertEqual(result['status'], 'runner_error')

    def test_observer_failure_is_not_passing_even_when_cleanup_succeeds(self):
        _, result = self.run_fake('observe_fail')
        self.assertEqual(result['status'], 'runner_error')
        self.assertIsNone(result['observed_peak_rss_bytes'])
        self.assertTrue(result['cleanup_verified'])
        self.assertTrue(result['stop_dispatch'])

    def test_cleanup_query_failure_preserves_unknown(self):
        _, result = self.run_fake('cleanup_query_fail')
        self.assertEqual(result['status'], 'runner_error')
        self.assertFalse(result['cleanup_verified'])
        self.assertIsNone(result['surviving_pids'])
        self.assertTrue(result['stop_dispatch'])

    def test_terminate_success_does_not_prove_quiescence(self):
        backend, result = self.run_fake('cleanup_stuck')
        self.assertTrue(backend.terminated)
        self.assertEqual(result['status'], 'runner_error')
        self.assertEqual(result['cleanup_last_accounting']['active_processes'], 3)
        self.assertIsNone(result['surviving_pids'])

    def test_wait_failure_stops_dispatch_even_after_attempted_cleanup(self):
        _, result = self.run_fake('poll_fail')
        self.assertEqual(result['status'], 'runner_error')
        self.assertIsNone(result['surviving_pids'])

    def test_handle_close_failure_overrides_success(self):
        _, result = self.run_fake('close_fail')
        self.assertEqual(result['status'], 'runner_error')
        self.assertTrue(result['stop_dispatch'])
        self.assertIn('close_error', result)

    def test_existing_folder_refuses_redispatch(self):
        self.folder.mkdir()
        factory = lambda: self.fail('No backend may be constructed')
        with self.assertRaises(FileExistsError):
            win.monitored(['python.exe'], self.folder, 100.08, 1000, _backend_factory=factory,
                          _clock=self.clock, _sleep=self.clock.sleep)

    def test_expired_deadline_creates_no_native_resource(self):
        factory = lambda: self.fail('No backend may be constructed')
        result = win.monitored(['python.exe'], self.folder, 99, 1000, _backend_factory=factory,
                               _clock=self.clock, _sleep=self.clock.sleep)
        self.assertEqual(result['status'], 'timeout')
        self.assertIsNone(result['pid'])
        self.assertTrue(result['cleanup_verified'])

    def run_backend(self, backend):
        return win.monitored(['python.exe'], self.folder, 100.08, 1000,
            cleanup_timeout=.08, _backend_factory=lambda: backend,
            _clock=self.clock, _sleep=self.clock.sleep)

    def test_sample_returning_after_deadline_cannot_accept_success(self):
        backend = FakeJob()
        sample = backend.sample
        def late():
            self.clock.value = 100.09
            return sample()
        backend.sample = late
        result = self.run_backend(backend)
        self.assertEqual(result['status'], 'timeout')
        self.assertEqual(result['exit_code'], 0)
        self.assertTrue(result['process_exit_observed'])
        self.assertFalse(result['work_within_budget'])
        self.assertTrue(result['stop_dispatch'])

    def test_poll_returning_exit_after_deadline_keeps_fact_but_times_out(self):
        backend = FakeJob()
        poll = backend.poll
        calls = []
        def late():
            calls.append(1)
            if len(calls) == 1:
                self.clock.value = 100.09
            return poll()
        backend.poll = late
        result = self.run_backend(backend)
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(result['cleanup_verified'])
        self.assertFalse(result['within_budget'])
        self.assertEqual(result['deadline_status'], 'deadline_unverified')

    def test_cleanup_active_zero_only_after_deadline_is_not_timely_success(self):
        backend = FakeJob()
        accounting = backend.accounting
        calls = []
        def late():
            calls.append(1)
            if len(calls) == 2:
                self.clock.value = 100.3
            return accounting()
        backend.accounting = late
        result = self.run_backend(backend)
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(result['cleanup_verified'])
        self.assertEqual(result['surviving_pids'], [])
        self.assertFalse(result['cleanup_within_budget'])
        self.assertTrue(result['stop_dispatch'])

    def test_close_crossing_cleanup_deadline_is_not_timely_success(self):
        backend = FakeJob()
        close = backend.close
        def late():
            close(); self.clock.value = 100.3
        backend.close = late
        result = self.run_backend(backend)
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(result['cleanup_verified'])
        self.assertFalse(result['within_budget'])

    def test_persisted_reservation_crossing_deadline_is_not_native_attempt(self):
        backend = FakeJob()
        save = win._save
        def slow_save(path, receipt):
            save(path, receipt)
            if receipt['creation_reserved'] and not receipt['creation_reservation_persisted']:
                self.clock.value = 100.2
        with patch.object(win, '_save', side_effect=slow_save):
            result = self.run_backend(backend)
        self.assertTrue(result['creation_reserved'])
        self.assertTrue(result['creation_reservation_persisted'])
        self.assertFalse(result['creation_attempted'])
        self.assertFalse(result['created'])
        self.assertFalse(result['resume_attempted'])
        self.assertFalse(result['target_entry_entered'])

    def test_failed_reservation_persistence_is_not_native_attempt(self):
        backend = FakeJob()
        save = win._save
        failed = []
        def bad_save(path, receipt):
            if receipt['creation_reserved'] and not failed:
                failed.append(1)
                raise OSError('synthetic persistence failure')
            save(path, receipt)
        with patch.object(win, '_save', side_effect=bad_save):
            result = self.run_backend(backend)
        self.assertTrue(result['creation_reserved'])
        self.assertFalse(result['creation_reservation_persisted'])
        self.assertFalse(result['creation_attempted'])
        self.assertFalse(result['created'])

    @unittest.skipIf(os.name == 'nt', 'Host import guard only; not a native Windows test')
    def test_native_backend_rejects_non_windows_without_loading_dll(self):
        with self.assertRaisesRegex(OSError, 'Windows only'):
            win.NativeJob()


class ABITests(unittest.TestCase):
    def test_fixed_width_types_and_x64_structure_layout(self):
        self.assertEqual(ct.sizeof(win.DWORD), 4)
        self.assertEqual(ct.sizeof(win.BOOL), 4)
        self.assertEqual(ct.sizeof(win.Accounting), 48)
        if ct.sizeof(ct.c_void_p) == 8:
            expected = [(win.BasicLimit, 64), (win.ExtendedLimit, 144), (win.StartupInfo, 104),
                        (win.StartupInfoEx, 112), (win.ProcessInfo, 24), (win.ProcessMemory, 80)]
            for structure, size in expected:
                self.assertEqual(ct.sizeof(structure), size, structure.__name__)
        self.assertEqual(win.CREATE_FLAGS & 4, 4)  # Suspended, not running then assigned.
        self.assertFalse(win.CREATE_FLAGS & 0x01000000)  # No BREAKAWAY_FROM_JOB.

    def test_unassigned_process_termination_does_not_depend_on_job_membership(self):
        native = object.__new__(win.NativeJob)
        native.job, native.process, native.assigned = 11, 22, False
        native.exited = lambda handle: False
        calls = []
        native.call = lambda *args: calls.append(args)
        native.terminate()
        self.assertEqual(calls, [('TerminateJobObject', 11, win.FORCED_EXIT), ('TerminateProcess', 22, win.FORCED_EXIT)])

    def test_failed_job_termination_still_attempts_unassigned_process(self):
        native = object.__new__(win.NativeJob)
        native.job, native.process, native.assigned = 11, 22, False
        native.exited = lambda handle: False
        calls = []

        def fail_job(*args):
            calls.append(args)
            if args[0] == 'TerminateJobObject':
                raise OSError('synthetic Job error')

        native.call = fail_job
        with self.assertRaises(RuntimeError):
            native.terminate()
        self.assertEqual(len(calls), 2)

    def test_access_denied_on_live_held_process_is_not_swallowed(self):
        native = object.__new__(win.NativeJob)
        native.job, native.process, native.assigned, native.events = None, 22, False, []
        native.exited = lambda handle: False
        native.call = lambda *args: (_ for _ in ()).throw(OSError(5, 'synthetic access denied'))
        with self.assertRaisesRegex(RuntimeError, 'access denied'):
            native.terminate()

    def test_access_denied_race_requires_same_handle_exit_readback(self):
        native = object.__new__(win.NativeJob)
        native.job, native.process, native.assigned, native.events = None, 22, False, []
        states, handles = iter((False, True)), []
        def exited(handle):
            handles.append(handle)
            return next(states)
        native.exited = exited
        native.call = lambda *args: (_ for _ in ()).throw(OSError(5, 'synthetic exit race'))
        native.terminate()
        self.assertEqual(handles, [22, 22])
        self.assertTrue(native.events[0]['held_handle_signaled'])

    def test_failed_exit_observation_is_not_swallowed_as_termination_race(self):
        native = object.__new__(win.NativeJob)
        native.job, native.process, native.assigned, native.events = None, 22, False, []
        polls, calls = [], []
        def exited(handle):
            polls.append(handle)
            if len(polls) == 1:
                raise OSError(5, 'synthetic wait observation failure')
            return True
        native.exited = exited
        native.call = lambda *args: calls.append(args)
        with self.assertRaisesRegex(RuntimeError, 'wait observation failure'):
            native.terminate()
        self.assertEqual(polls, [22])
        self.assertEqual(calls, [('TerminateProcess', 22, win.FORCED_EXIT)])


class KernelSubstitute:
    """Exercises ctypes argument construction without calling a Windows DLL."""
    def __init__(self, assign_fail=False):
        self.error, self.duplicate = 0, 100
        self.calls = []
        self.assign_fail = assign_fail

    def __getattr__(self, name):
        def invoke(*args):
            self.error = 0
            self.calls.append((name, args))
            if name == 'GetCurrentProcess':
                return -1
            if name == 'CreateJobObjectW':
                return 10
            if name == 'GetHandleInformation':
                args[1]._obj.value = int(args[0] >= 100)
            elif name == 'QueryInformationJobObject' and args[1] == 9:
                args[2]._obj.basic.flags = win.KILL_ON_JOB_CLOSE
            elif name == 'DuplicateHandle':
                self.duplicate += 1
                args[3]._obj.value = self.duplicate
            elif name == 'InitializeProcThreadAttributeList' and args[0] is None:
                args[3]._obj.value = 128
                self.error = 122
                return 0
            elif name == 'CreateProcessW':
                info = args[-1]._obj
                info.process, info.thread, info.pid, info.tid = 20, 21, 500, 501
            elif name == 'AssignProcessToJobObject' and self.assign_fail:
                self.error = 5
                return 0
            elif name == 'IsProcessInJob':
                args[-1]._obj.value = 1
            elif name == 'WaitForSingleObject':
                return 258
            return 1
        return invoke


class NativeCreationSubstituteTests(unittest.TestCase):
    def native(self, kernel):
        native = object.__new__(win.NativeJob)
        native.msvcrt = SimpleNamespace(get_osfhandle=lambda fd: fd)
        native.k = kernel
        native.job = native.process = native.thread = native.pid = None
        native.handles, native.events = [], []
        native.creation_attempted = native.assigned = native.resumed = native.resume_attempted = False
        return native

    def test_native_argument_path_assigns_before_only_resume_and_whitelists_stdio(self):
        kernel = KernelSubstitute()
        native = self.native(kernel)
        with patch.object(ct, 'get_last_error', lambda: kernel.error, create=True), tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            native.prepare()
            native.create(['C:\\python.exe', 'space argument'], Path.cwd(), {'TEST': 'synthetic'}, out, err, lambda: None)
            self.assertEqual(native.pid, 500)
            self.assertTrue(native.assigned)
            self.assertFalse(native.resumed)
            native.resume()
            native.close()
        names = [x[0] for x in kernel.calls]
        self.assertLess(names.index('CreateJobObjectW'), names.index('CreateProcessW'))
        self.assertLess(names.index('CreateProcessW'), names.index('AssignProcessToJobObject'))
        self.assertLess(names.index('AssignProcessToJobObject'), names.index('ResumeThread'))
        self.assertEqual(names.count('ResumeThread'), 1)
        creation = next(args for name, args in kernel.calls if name == 'CreateProcessW')
        self.assertEqual(creation[5], win.CREATE_FLAGS)
        attributes = [args for name, args in kernel.calls if name == 'UpdateProcThreadAttribute']
        self.assertEqual(len(attributes), 1)
        self.assertEqual(attributes[0][2], win.HANDLE_LIST)
        self.assertEqual(attributes[0][4], ct.sizeof(win.HANDLE) * 3)

    def test_native_assign_failure_retains_pid_and_handles_without_resuming(self):
        kernel = KernelSubstitute(assign_fail=True)
        native = self.native(kernel)
        with patch.object(ct, 'get_last_error', lambda: kernel.error, create=True), tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            native.prepare()
            with self.assertRaises(OSError):
                native.create(['C:\\python.exe'], Path.cwd(), {}, out, err, lambda: None)
            self.assertEqual((native.pid, native.process, native.thread), (500, 20, 21))
            self.assertFalse(native.assigned)
            native.terminate()
            native.close()
        names = [x[0] for x in kernel.calls]
        self.assertNotIn('ResumeThread', names)
        self.assertIn('TerminateProcess', names)

    def test_assign_failure_and_failed_wait_still_attempts_owned_child_termination(self):
        class Kernel(KernelSubstitute):
            def __getattr__(self, name):
                base = super().__getattr__(name)
                def invoke(*args):
                    result = base(*args)
                    if name == 'WaitForSingleObject':
                        self.error = 5
                        return 0xFFFFFFFF
                    return result
                return invoke
        kernel = Kernel(assign_fail=True)
        native = self.native(kernel)
        clock = Clock()
        with patch.object(ct, 'get_last_error', lambda: kernel.error, create=True), tempfile.TemporaryDirectory() as directory:
            receipt = win.monitored(['python.exe'], Path(directory)/'run', 100.3, 10**8,
                cleanup_timeout=.1, _backend_factory=lambda: native, _clock=clock, _sleep=clock.sleep)
        names = [name for name, args in kernel.calls]
        self.assertLess(names.index('CreateProcessW'), names.index('AssignProcessToJobObject'))
        self.assertIn('TerminateProcess', names)
        self.assertNotIn('ResumeThread', names)
        self.assertEqual(receipt['status'], 'runner_error')
        self.assertFalse(receipt['cleanup_verified'])
        self.assertIsNone(receipt['surviving_pids'])
        self.assertTrue(receipt['stop_dispatch'])
        self.assertIn('cleanup_error', receipt)


if __name__ == '__main__':
    unittest.main()
