"""Synthetic gate controller tests only: no subprocess, Windows DLL or evaluator."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import windows_gate as gate
from tests.q2_nikolastarx import test_windows_process as process_fixtures


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.dispatched = []

    def factory(self, case, deadline):
        backend = SimpleNamespace(case=case, pid=12345, creation_attempted=True,
                                  witness={'verified': True, 'accounting': {'active_processes': 0, 'total_processes': 3}})
        def close():
            backend.witness = {'verified': True, 'reason': 'synthetic cleanup, not Windows evidence'}
        backend.close = close
        return backend

    def monitor(self, argv, folder, deadline, rss_limit, **kwargs):
        backend = kwargs['_backend_factory']()
        self.dispatched.append(backend.case)
        folder.mkdir()
        row = {'status': 'ok', 'exit_code': 0, 'cleanup_verified': True, 'stop_dispatch': False,
               'creation_attempted': True, 'created': True, 'resumed': True, 'assigned_before_resume': True,
               'surviving_pids': [], 'target_entry_entered': 'unknown', 'observer_inclusive_peak_rss_bytes': 1,
               'wall_seconds': .01}
        if backend.case == 'normal':
            (folder/'stdout.txt').write_bytes('正常 stdout\n'.encode())
            (folder/'stderr.txt').write_bytes(b'stderr\n')
        elif backend.case == 'nonzero':
            row.update(status='failed', exit_code=7)
        elif backend.case == 'timeout_grandchild':
            row.update(status='timeout', exit_code=-1, last_sample={'pids': [12345, 23456, 34567]})
            (folder.parent/'middle-pid.txt').write_text('23456')
            (folder.parent/'grandchild-pid.txt').write_text('34567')
        elif backend.case == 'rss_limit':
            row.update(status='rss_limit', stop_dispatch=True, observer_inclusive_peak_rss_bytes=128*1024**2)
        elif backend.case == 'assign_failure':
            row.update(status='runner_error', stop_dispatch=True, resumed=False, assigned_before_resume=False,
                       target_entry_entered=False, error='deliberately injected assignment failure')
        elif backend.case == 'observation_failure':
            row.update(status='runner_error', stop_dispatch=True, error='deliberately injected memory observation failure')
        else:
            row.update(status='runner_error', stop_dispatch=True, cleanup_verified=False, surviving_pids=None,
                       cleanup_error='deliberately injected cleanup accounting failure')
        gate.wp._save(folder/'process.json', row)
        return row

    def execute(self, monitor=None):
        with patch.object(gate, 'os', SimpleNamespace(name='nt', environ={'SYNTHETIC_ONLY': '1'})):
            return gate.run(self.root/'run', {'runner_commit': 'a'*40, 'test_only': True},
                            _factory=self.factory, _monitor=monitor or self.monitor)

    def test_every_fixture_compiles_without_execution(self):
        for case in gate.CASES:
            with self.subTest(case=case):
                compile(gate.fixture(case, self.root/'path with 空格'), '<synthetic-fixture>', 'exec')
        self.assertEqual(self.dispatched, [])

    def test_plan_never_constructs_backend(self):
        with patch.object(gate, 'frozen', return_value={'mock': 'not a source proof'}), \
             patch.object(gate.wp, 'NativeJob', side_effect=AssertionError('native forbidden')):
            result = gate.plan('b'*40)
        self.assertEqual(result['dispatched'], 0)
        self.assertEqual(result['solver_calls'], 0)
        self.assertEqual(result['maximum_direct_CreateProcess_requests'], 7)

    def test_non_windows_refused_before_directory_or_process(self):
        with patch.object(gate, 'os', SimpleNamespace(name='posix')):
            with self.assertRaisesRegex(RuntimeError, '64-bit Windows'):
                gate.run(self.root/'never-created', {}, _factory=self.factory, _monitor=self.monitor)
        self.assertFalse((self.root/'never-created').exists())

    def test_all_expected_fake_controls_preserve_unknown_receipt(self):
        report = self.execute()
        self.assertEqual(report['status'], 'pass')
        self.assertEqual(report['direct_creation_attempts'], 7)
        self.assertEqual(report['direct_created_processes'], 7)
        self.assertEqual(self.dispatched, list(gate.CASES))
        result = gate.json.loads((self.root/'run/cleanup_unknown/result.json').read_text())
        self.assertIsNone(result['receipt']['surviving_pids'])
        self.assertFalse(result['receipt']['cleanup_verified'])
        self.assertTrue(result['independent_cleanup_witness']['verified'])
        manifest = gate.json.loads((self.root/'run/manifest.json').read_text())
        self.assertIn('cleanup_unknown/process/process.json', manifest)
        self.assertIn('gate.json', manifest)
        for path, identity in manifest.items():
            raw = (self.root/'run'/path).read_bytes()
            self.assertEqual(len(raw), identity['bytes'])
            self.assertEqual(gate.hashlib.sha256(raw).hexdigest(), identity['sha256'])

    def test_first_unexpected_failure_stops_without_retry(self):
        def monitor(*args, **kwargs):
            row = self.monitor(*args, **kwargs)
            row['exit_code'] = 18
            return row
        report = self.execute(monitor)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['stop_reason'], 'first_unexpected_failure')
        self.assertEqual(self.dispatched, ['normal'])

    def test_controller_exception_preserves_created_identity_and_no_next_case(self):
        def fail(argv, folder, deadline, rss_limit, **kwargs):
            backend = kwargs['_backend_factory']()
            backend.witness = {'verified': False}
            raise RuntimeError('synthetic controller exception after PID acquisition')
        report = self.execute(fail)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['direct_created_processes'], 1)
        self.assertEqual(len(report['results']), 1)
        result = gate.json.loads((self.root/'run/normal/result.json').read_text())
        self.assertIn('controller exception', result['controller_error'])
        self.assertTrue(result['independent_cleanup_witness']['verified'])
        self.assertIsNone(result['receipt'])

    def test_unrelated_errors_never_count_as_expected_injection(self):
        folder = self.root/'case'; (folder/'process').mkdir(parents=True)
        row = {'status': 'runner_error', 'resumed': True, 'cleanup_verified': True,
               'stop_dispatch': True, 'error': 'a real unrelated memory observation error'}
        witness = {'verified': True}
        self.assertFalse(gate.expected('observation_failure', row, folder, witness))
        row['error'] = 'deliberately injected memory observation failure'
        self.assertTrue(gate.expected('observation_failure', row, folder, witness))
        for key in ('close_error', 'cleanup_error'):
            bad = deepcopy(row); bad[key] = 'unexpected real native error'
            self.assertFalse(gate.expected('observation_failure', bad, folder, witness))

    def test_existing_gate_directory_never_resumes(self):
        self.execute()
        self.dispatched.clear()
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual(self.dispatched, [])


class NativeGateCloseTests(unittest.TestCase):
    """Run the real GateJob.close and NativeJob termination methods on fake APIs."""
    def test_assign_failure_monitor_cleanup_is_not_followed_by_second_termination(self):
        class Kernel(process_fixtures.KernelSubstitute):
            signaled = False
            limits = (0, 0, 0)
            def __getattr__(self, name):
                base = super().__getattr__(name)
                def invoke(*args):
                    result = base(*args)
                    if name == 'SetInformationJobObject':
                        v = args[2]._obj
                        self.limits = v.basic.flags, v.basic.active_limit, v.job_memory
                    elif name == 'QueryInformationJobObject' and args[1] == 9:
                        v = args[2]._obj
                        v.basic.flags, v.basic.active_limit, v.job_memory = self.limits
                    elif name == 'QueryInformationJobObject' and args[1] == 1:
                        args[2]._obj.active = 0  # Suspended direct child never entered Job.
                    elif name == 'WaitForSingleObject':
                        return 0 if self.signaled else 258
                    elif name == 'TerminateProcess':
                        if self.signaled:
                            self.error = 5
                            return 0
                        self.signaled = True
                    elif name == 'GetExitCodeProcess':
                        args[1]._obj.value = gate.wp.FORCED_EXIT
                    return result
                return invoke
        kernel = Kernel()
        template = process_fixtures.NativeCreationSubstituteTests().native(kernel)
        backend = object.__new__(gate.GateJob)
        backend.__dict__.update(template.__dict__)
        backend.case, backend.outer_deadline = 'assign_failure', 100.5
        backend.cleanup_fault_armed, backend.witness = False, {'verified': False}
        clock = process_fixtures.Clock()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(gate.ct, 'get_last_error', lambda: kernel.error, create=True), \
             patch.object(gate, 'time', SimpleNamespace(perf_counter=clock, sleep=clock.sleep)):
            receipt = gate.wp.monitored(['python.exe'], Path(directory)/'process', 100.3, 10**8,
                cleanup_timeout=.1, _backend_factory=lambda: backend, _clock=clock, _sleep=clock.sleep)
        names = [name for name, args in kernel.calls]
        self.assertEqual(names.count('TerminateProcess'), 1)
        self.assertNotIn('ResumeThread', names)
        self.assertNotIn('close_error', receipt)
        self.assertTrue(receipt['cleanup_verified'])
        self.assertTrue(backend.witness['verified'])
        self.assertTrue(backend.witness['within_budget'])

    def test_gate_witness_late_active_zero_keeps_fact_but_does_not_pass(self):
        backend = object.__new__(gate.GateJob)
        backend.job, backend.pid, backend.process, backend.assigned = 10, 20, 30, True
        backend.outer_deadline, backend.handles, backend.witness = 100.1, [], {'verified': False}
        clock = process_fixtures.Clock()
        def accounting(_self):
            clock.value = 100.2
            return {'active_processes': 0, 'total_processes': 1}
        with patch.object(gate.wp.NativeJob, 'accounting', accounting), \
             patch.object(gate.wp.NativeJob, 'poll', return_value=0), \
             patch.object(gate, 'time', SimpleNamespace(perf_counter=clock, sleep=clock.sleep)):
            with self.assertRaises(TimeoutError):
                backend.close()
        self.assertTrue(backend.witness['verified'])
        self.assertFalse(backend.witness['within_budget'])
        self.assertFalse(gate.expected('normal', {}, Path('unused'), backend.witness))


if __name__ == '__main__':
    unittest.main()
