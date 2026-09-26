"""Controller failure-path checks; no algorithm or official evaluator is run."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.benchmarks import p123_run as controller


class FailurePaths(unittest.TestCase):
    def setUp(self):
        controller.STOP.clear()

    def tearDown(self):
        controller.STOP.clear()

    def test_cleanup_failure_is_persisted_and_blocks_new_launches(self):
        process = Mock(pid=987654, returncode=None)
        process.wait.side_effect = subprocess.TimeoutExpired("fake", 1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(controller.subprocess, "Popen", return_value=process) as launch, \
                 patch.object(controller.subprocess, "run", side_effect=RuntimeError("mock cleanup failure")), \
                 patch.object(controller.os, "killpg", side_effect=RuntimeError("mock cleanup failure"), create=True):
                with self.assertRaises(controller.FatalRunStop):
                    controller.run_process(["fake"], root, root / "first", 1, {"OUTPUT": root})
                evidence = controller.read(root / "first/process.json")
                self.assertEqual(evidence["status"], "fatal_cleanup")
                self.assertTrue(evidence["cleanup_unconfirmed"])
                self.assertIn("finished_at", evidence)
                marker = controller.read(controller.fatal_stop_path(root))
                self.assertEqual(marker["status"], "fatal_cleanup")
                self.assertEqual(marker["pid"], process.pid)
                controller.STOP.clear()  # Simulate a newly started controller process.
                with self.assertRaises(controller.FatalRunStop):
                    controller.run_process(["fake"], root, root / "second", 1, {"OUTPUT": root})
                self.assertEqual(launch.call_count, 1)
                self.assertFalse((root / "second").exists())

    def test_final_plan_hash_failure_cannot_leave_success_or_ratio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "cells/P2/002/k2"

            def fake_process(*args):
                if args[2].name == "e0_process":
                    controller.save(folder / "e0/summary.json", {
                        "makespan_cycles": 10, "data_movement_bytes": {}})
                return {"status": "ok", "wall_seconds": 0}

            with patch.object(controller, "run_process", side_effect=fake_process), \
                 patch.object(controller, "sha", side_effect=OSError("mock missing final plan")):
                receipt = controller.cell("P2", "002", 2, root, {"P2": root},
                                          {"status": "ok", "makespan_cycles": 20})
            self.assertEqual(receipt["row"]["status"], "error")
            self.assertIsNone(receipt["row"]["makespan_cycles"])
            self.assertIsNone(receipt["row"]["multicore_speedup"])
            self.assertIn("missing final plan", receipt["row"]["error"])
            self.assertEqual(controller.read(folder / "cell.json"), receipt)

    def test_queued_jobs_do_not_execute_after_fatal_stop(self):
        calls = []

        def job(value):
            controller.check_running()
            calls.append(value)
            controller.STOP.set()
            raise controller.FatalRunStop("mock fatal cleanup")

        with self.assertRaises(controller.FatalRunStop):
            list(controller.completed_jobs(job, [(1,), (2,), (3,)], 1))
        self.assertEqual(calls, [1])

    def test_output_lock_rejects_second_process_then_releases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = """
import sys
from pathlib import Path
from src.benchmarks.p123_run import output_directory_lock
with output_directory_lock(Path(sys.argv[1])):
    print("locked", flush=True)
    sys.stdin.readline()
"""
            holder = subprocess.Popen(
                [sys.executable, "-B", "-c", script, str(root)],
                cwd=controller.ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                ready = holder.stdout.readline().strip()
                if ready != "locked":
                    holder.kill()
                    _, error = holder.communicate(timeout=10)
                    self.fail(f"lock holder did not start: {ready!r} {error}")
                with self.assertRaises(controller.OutputDirectoryBusy):
                    with controller.output_directory_lock(root):
                        self.fail("second controller acquired an occupied output lock")
                holder.stdin.write("release\n")
                holder.stdin.flush()
                _, error = holder.communicate(timeout=10)
                self.assertEqual(holder.returncode, 0, error)
            finally:
                if holder.poll() is None:
                    holder.kill()
                    holder.wait(timeout=10)
            with controller.output_directory_lock(root):
                pass

    def test_running_invocation_blocks_future_controller(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invocation = root / "invocations/active.json"
            controller.save(invocation, {"status": "running"})
            with self.assertRaises(controller.OutputDirectoryBusy):
                controller.ensure_output_startable(root)
            controller.save(invocation, {"status": "stopped"})
            controller.ensure_output_startable(root)

    def test_missing_original_protocol_rejects_existing_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "cells/P1/001/k2").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "no original protocol"):
                controller.pin_protocol(root, {"source_sha256": {"p123_run.py": "old"}}, "future fix")
            self.assertFalse((root / "protocol.json").exists())


if __name__ == "__main__":
    unittest.main()
