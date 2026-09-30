"""Budget/control-path tests. These never call any official evaluator."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from src.q2.monitor import supervise
from src.q2.stage_a import Budget


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="q2-controls-")
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_child(self, code, **kwargs):
        return supervise([getattr(sys, "_base_executable", sys.executable), "-B", "-c", code], cwd=self.folder,
                         folder=self.folder, deadline=time.monotonic() + kwargs.pop("seconds", 5),
                         **kwargs)

    @unittest.skipUnless(os.name == "nt", "Windows monitor validation")
    def test_real_monitor_observes_success(self):
        result = self.run_child("import time; print('ok',flush=True); time.sleep(.3)")
        self.assertEqual((result["status"], result["returncode"]), ("completed", 0))
        self.assertGreater(result["sampled_working_set_peak_bytes"], 0)
        self.assertIn("ok", (self.folder / "stdout.txt").read_text())

    def test_timeout_reaps_child(self):
        result = self.run_child("import time; time.sleep(60)", seconds=.1, sampler=lambda _: 1)
        self.assertEqual(result["status"], "timeout")
        self.assertIsNotNone(result["returncode"])
        self.assertLess(result["wall_seconds"], 3)

    def test_memory_threshold_stops_only_launched_child(self):
        sampler = lambda pid: 1 if pid == os.getpid() else 100
        result = self.run_child("import time; time.sleep(60)", sampler=sampler, memory_limit=50)
        self.assertTrue(result["launched"])
        self.assertEqual(result["status"], "resource_limit")
        self.assertIsNotNone(result["returncode"])

    def test_failed_sampling_reaps_child(self):
        def sampler(pid):
            if pid != os.getpid():
                raise OSError("injected monitor failure")
            return 1
        result = self.run_child("import time; time.sleep(60)", sampler=sampler)
        self.assertTrue(result["launched"])
        self.assertEqual(result["status"], "monitor_error")
        self.assertIsNotNone(result["returncode"])

    def test_prelaunch_memory_failure_launches_nothing(self):
        result = self.run_child("raise RuntimeError('must not run')", sampler=lambda _: 100,
                                memory_limit=50)
        self.assertFalse(result["launched"])
        self.assertEqual(result["status"], "resource_limit")

    def test_reservations_persist_before_launch_and_cannot_exceed_limit(self):
        budget = Budget(self.folder, 2, 10)
        budget.reserve("first")
        budget.reserve("second")
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            budget.reserve("third")
        snapshot = json.loads((self.folder / "budget.json").read_text())
        self.assertEqual(snapshot["reserved_invocations"], 2)
        self.assertEqual([r["label"] for r in snapshot["calls"]], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
