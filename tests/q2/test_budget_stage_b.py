"""Zero-E0 tests for the stage B process tree and persistent reservation boundary."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from src.q2.budget_search import Calls, allowance, command_run
from src.q2.construct import ROOT
from src.q2.job_control import run_job
from src.q2.monitor import working_set

PYTHON = getattr(sys, '_base_executable', sys.executable)


@unittest.skipUnless(os.name == 'nt', 'Windows job implementation')
class BudgetStageB(unittest.TestCase):
    def run_dummy(self, body, seconds=3, **kwargs):
        with tempfile.TemporaryDirectory() as temp:
            started = time.monotonic()
            command = [PYTHON,'-X','utf8','-B','-c',
                       'import sys,time,subprocess,os; assert sys.stdin.readline().strip()=="GO"; '+body]
            return run_job(command,cwd=ROOT,folder=Path(temp),started=started,
                           deadline=started+seconds,**kwargs)

    def test_success_includes_output_tail(self):
        result=self.run_dummy('print("generated"); time.sleep(0.4); print("hashed")')
        self.assertEqual(result['status'],'completed')
        self.assertGreaterEqual(result['wall_through_job_cleanup'],0.4)
        self.assertEqual(result['remaining_job_pids'],[])

    def test_deadline_kills_worker_and_grandchild(self):
        result=self.run_dummy('p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); time.sleep(60)',seconds=1.5)
        self.assertEqual(result['status'],'timeout')
        self.assertGreaterEqual(result['max_job_processes'],2)
        self.assertEqual(result['remaining_job_pids'],[])
        self.assertLess(result['wall_through_job_cleanup'],4)

    def test_memory_threshold_reaps_tree(self):
        reads=[0]
        def sampler(pid):
            reads[0]+=1
            return 10**10 if reads[0]>6 else working_set(pid)
        result=self.run_dummy('p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); time.sleep(60)',sampler=sampler)
        self.assertEqual(result['status'],'resource_limit')
        self.assertEqual(result['remaining_job_pids'],[])
        self.assertGreaterEqual(result['waited_process_handles'],2)
        self.assertEqual(result['waited_process_handles'],result['closed_wait_handles'])
        self.assertTrue(result['closed_popen_process_handle'])

    def test_repeated_forced_stop_releases_inherited_log_handles(self):
        # Regression for intermittent WinError32 during immediate directory cleanup.
        for repeat in range(12):
            with self.subTest(repeat=repeat):
                reads=[0]
                def sampler(pid):
                    reads[0]+=1
                    return 10**10 if reads[0]>6 else working_set(pid)
                result=self.run_dummy('p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); time.sleep(60)',sampler=sampler)
                self.assertEqual(result['status'],'resource_limit')
                self.assertEqual(result['remaining_job_pids'],[])
                self.assertGreaterEqual(result['waited_process_handles'],2)
                self.assertEqual(result['waited_process_handles'],result['closed_wait_handles'])

    def test_wait_failure_is_monitor_error_and_closes_handles(self):
        with patch('src.q2.job_control.Job.wait_process',side_effect=OSError('injected wait failure')):
            result=self.run_dummy('time.sleep(0.3)')
        self.assertEqual(result['status'],'monitor_error')
        self.assertIn('injected wait failure',result['cleanup_error'])
        self.assertGreaterEqual(result['closed_wait_handles'],1)
        self.assertTrue(result['closed_popen_process_handle'])
        self.assertLess(result['cleanup_seconds'],10)

    def test_sampling_failure_is_not_evaluator_invalid(self):
        reads=[0]
        def sampler(pid):
            reads[0]+=1
            if reads[0]>3:
                raise ValueError('injected monitor failure')
            return working_set(pid)
        result=self.run_dummy('time.sleep(60)',sampler=sampler)
        self.assertEqual(result['status'],'monitor_error')
        self.assertEqual(result['remaining_job_pids'],[])

    def test_no_launch_after_deadline(self):
        result=self.run_dummy('raise Exception("must not launch")',seconds=-1)
        self.assertEqual(result['status'],'timeout')
        self.assertFalse(result['launched'])

    def test_assignment_failure_reaps_gated_child(self):
        with patch('src.q2.job_control.Job.assign', side_effect=OSError('injected assignment failure')):
            result=self.run_dummy('raise Exception("GO must never be sent")')
        self.assertEqual(result['status'],'monitor_error')
        self.assertIsNotNone(result['returncode'])
        self.assertLess(result['wall_through_job_cleanup'],3)

    def test_crashed_worker_cannot_leave_child_running(self):
        result=self.run_dummy('p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); raise SystemExit(3)')
        self.assertEqual(result['status'],'worker_error')
        self.assertEqual(result['remaining_job_pids'],[])
        self.assertLess(result['wall_through_job_cleanup'],2)

    def test_final_slot_persisted_and_no_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            calls=Calls(folder)
            for n in range(31):
                calls.reserve('initial' if n==0 else 'explore',['dummy'],n)
            with self.assertRaises(RuntimeError):
                calls.reserve('explore',['dummy'],31)
            calls.reserve('final',['dummy'],31)
            with self.assertRaises(RuntimeError):
                calls.reserve('final',['dummy'],32)
            with self.assertRaises(FileExistsError):
                Calls(folder)
            data=json.loads((folder/'calls.json').read_text(encoding='utf-8'))
            self.assertEqual(data['charged'],32)
            self.assertEqual(data['calls'][-1]['slot'],32)

    def test_reserves_for_final_and_cleanup(self):
        self.assertEqual(allowance(120),0)
        self.assertEqual(allowance(121),1)
        self.assertEqual(allowance(600),120)
        self.assertEqual(allowance(120,True),105)
        self.assertEqual(allowance(15,True),0)

    def test_call_timeout_and_launch_callback(self):
        pids=[]
        with tempfile.TemporaryDirectory() as temp:
            result=command_run([PYTHON,'-B','-c','import time; time.sleep(60)'],
                               Path(temp),0.1,pids.append)
        self.assertEqual(result['status'],'timeout')
        self.assertEqual(pids,[result['pid']])
        self.assertLess(result['wall_seconds'],2)


if __name__ == '__main__':
    unittest.main()
