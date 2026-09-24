"""Only synthetic evidence and tiny Python subprocesses; zero solver/E0 calls."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from src.q3 import feedback_benchmark as bench
from src.q3.board_export import export_batch
from tests.q3 import test_board_export as fixtures


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.FeedbackTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        self.folder = self.root / "results/a/q3-verification/中文-run"

    def tearDown(self):
        self.fixture.tearDown()

    def verification(self, cases=("002", "062")):
        m = fixtures.manifest(cases=cases)
        m.update(solver_commit=bench.GUARDED_COMMIT, solver_module="src.q3.guarded_solve")
        m["execution"] = {"runner_commit": "b" * 40, "expected_commit": "c" * 40,
                          "output_root": "results/a/q3-verification",
                          "solver_files": dict.fromkeys(bench.GUARDED_FILES, "d" * 64),
                          "memory_limit_bytes": 8 * 1024**3, "memory_poll_seconds": 0.1}
        expected = {}
        for j in m["jobs"]:
            control = self.root / "results" / ("control-" + j["case_id"])
            control.mkdir(parents=True)
            argv = ["python", "-B", "-m", m["solver_module"], f"data/raw/a/official/data/case_{j['case_id']}.json",
                    "--cores", "4", "-o", str(control / f"case_{j['case_id']}_multicore_res.json"),
                    "--evidence", str(control / "evidence")]
            self.fixture.child(argv, 1, control, self.root)
            files = {"plan": control / f"case_{j['case_id']}_multicore_res.json",
                     "result": control / "evidence/result.json.gz", "receipt": control / "evidence/receipt.json"}
            j["expected"] = {key: bench.artifact(value, self.root) for key, value in files.items()}
            expected[bench.job_key(j)] = {key: bench.read(value) for key, value in files.items()}
        return m, expected

    def execute(self, m, expected, child=None, output=None):
        def fake(argv, timeout, folder, root, **limits):
            self.assertEqual(limits["memory_limit_bytes"], 8 * 1024**3)
            return self.fixture.child(argv, timeout, folder, root)
        with patch.object(bench, "verify_manifest_source", return_value=("f" * 64, {})), \
                patch.object(bench, "load_expected", return_value=expected), \
                patch.object(bench, "run_child", side_effect=child or fake) as run:
            batch = bench.execute(m, output or self.folder, root=self.root)
        return batch, run.call_count

    def test_verification_success_and_separate_runner_provenance(self):
        m, expected = self.verification()
        batch, count = self.execute(m, expected)
        self.assertEqual((batch["status"], count, batch["e0_budget_used"]), ("stage_complete", 2, 2))
        for record in batch["records"]:
            self.assertTrue(bench.read(self.root / record["expected_comparison"]["path"])["matched"])
        feed = export_batch(self.folder / "batch.json", self.root)
        self.assertEqual(feed["records"][0]["provenance"]["runner"]["source"]["commit"], "b" * 40)
        self.assertEqual(feed["records"][0]["solver_commit"], bench.GUARDED_COMMIT)

    def test_expected_value_mismatch_stops_before_second_job(self):
        m, expected = self.verification()
        expected[bench.job_key(m["jobs"][0])]["result"]["diagnostic"] = ["different"]
        batch, count = self.execute(m, expected)
        self.assertEqual((count, batch["status"]), (1, "stopped_on_failure"))
        record = batch["records"][0]
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["calls"]["E0"], 1)  # valid receipt proves actual calls
        self.assertEqual(batch["e0_budget_used"], 2)  # failed verification does not refund
        check = bench.read(self.root / record["expected_comparison"]["path"])
        self.assertFalse(check["matched"])
        self.assertIn("$.diagnostic[0]", str(check))
        self.assertFalse((self.folder / "cells" / bench.job_key(m["jobs"][1])).exists())

    def test_float_integer_and_plan_byte_changes_are_not_normalized(self):
        self.assertTrue(bench.typed_differences({"x": 7}, {"x": 7.0}))
        m, expected = self.verification(cases=("002",))
        m["jobs"][0]["expected"]["plan"]["sha256"] = "e" * 64
        batch, _ = self.execute(m, expected)
        self.assertEqual(batch["status"], "stopped_on_failure")

    def test_failed_memory_or_timeout_keeps_reservation_and_stops(self):
        m, expected = self.verification(cases=("063",))
        for reason, state in (("memory_limit_exceeded", "failed"), ("deadline", "timeout"),
                              ("memory_monitor_error", "failed")):
            with self.subTest(reason=reason):
                # Distinct run, no automatic retry of a failed run.
                def failed(*args, **kwargs):
                    return {"status": state, "reason": reason, "exit_code": -9, "wall_seconds": 0.2}
                batch, count = self.execute(m, expected, failed, self.folder / reason)
                self.assertEqual((count, batch["e0_budget_used"]), (1, 2))
                self.assertIsNone(batch["records"][0]["calls"]["E0"])
                self.assertIn(reason, batch["records"][0]["failure"]["reason"])

    def test_output_escape_and_symlink_rejected_before_child(self):
        m, expected = self.verification(cases=("002",))
        with patch.object(bench, "run_child") as child:
            with self.assertRaises(ValueError):
                bench.execute(m, self.root / "other", root=self.root)
            self.folder.parent.mkdir(parents=True)
            outside = self.root / "outside"
            outside.mkdir()
            try:
                self.folder.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("host cannot create directory symlink")
            with self.assertRaises(ValueError):
                bench.execute(m, self.folder, root=self.root)
            child.assert_not_called()

    def test_dependency_contract_allows_unrelated_stage_but_rejects_drift(self):
        m, _ = self.verification(cases=("002",))
        frozen = {}
        for name in bench.GUARDED_FILES | {"uv.lock", "pyproject.toml", "docs/a/source-manifest.json"}:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("frozen " + name).encode())
            frozen[name] = path.read_bytes()
        m["execution"]["solver_files"] = {p: bench.digest(self.root / p) for p in bench.GUARDED_FILES}
        (self.root / "src/q3/tree_solve.py").write_text("unrelated stage import", encoding="utf-8")
        with patch.object(bench, "git_bytes", side_effect=lambda root, sha, path: frozen[path]):
            bench.verify_manifest_source(m, ["002"], self.root)
            (self.root / "src/q3/solve.py").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "dependency differs"):
                bench.verify_manifest_source(m, ["002"], self.root)

    def test_missing_dependency_and_expected_hash_fail_before_dispatch(self):
        m, _ = self.verification(cases=("002",))
        broken = copy.deepcopy(m)
        broken["execution"]["solver_files"].pop("src/q3/solve.py")
        with self.assertRaises(ValueError):
            bench.validate_manifest(broken)
        with patch.object(bench, "git_bytes", return_value=b"{}"), patch.object(bench, "run_child") as child:
            with self.assertRaisesRegex(ValueError, "expected artifact hash"):
                bench.load_expected(m, self.root)
            child.assert_not_called()

    def test_source_change_before_dispatch_is_recorded_without_child(self):
        m, expected = self.verification(cases=("002",))
        with patch.object(bench, "verify_manifest_source", side_effect=[("f" * 64, {}), RuntimeError("drift")]), \
                patch.object(bench, "load_expected", return_value=expected), patch.object(bench, "run_child") as child:
            batch = bench.execute(m, self.folder, root=self.root)
        self.assertEqual(batch["status"], "stopped_before_dispatch")
        self.assertIn("drift", batch["stop_reason"])
        self.assertEqual((batch["e0_budget_used"], batch["records"]), (0, []))
        child.assert_not_called()

    def test_utf8_lf_is_explicit(self):
        target = self.root / "中文.json"
        original = Path.write_text
        def required(path, data, **kw):
            self.assertEqual(kw.get("encoding"), "utf-8")
            self.assertEqual(kw.get("newline"), "\n")
            return original(path, data, **kw)
        with patch.object(Path, "write_text", required):
            bench.write(target, {"题目": "三"})
        self.assertIn("题目".encode(), target.read_bytes())
        self.assertNotIn(b"\r\n", target.read_bytes())

    def test_real_tiny_process_success_and_logs(self):
        self.folder.mkdir(parents=True)
        result = bench.run_child([sys.executable, "-B", "-c", "print('ok')"], 5, self.folder, self.root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual((self.folder / "stdout.txt").read_text().strip(), "ok")
        self.assertGreater(result["wall_seconds"], 0)
        self.assertFalse((self.folder / "unused-pycache").exists())

    def test_real_timeout_removes_delayed_descendant(self):
        self.folder.mkdir(parents=True)
        marker = self.root / "must-not-exist"
        script = ("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"
                  + repr("import time,pathlib;time.sleep(0.8);pathlib.Path(" + repr(str(marker)) + ").write_text('orphan')")
                  + "]);print('started',flush=True);time.sleep(10)")
        result = bench.run_child([sys.executable, "-B", "-c", script], 0.2, self.folder, self.root)
        self.assertEqual(result["status"], "timeout")
        time.sleep(0.9)
        self.assertFalse(marker.exists())
        self.assertIn(b"started", (self.folder / "stdout.txt").read_bytes())

    @unittest.skipIf(os.name == "nt", "POSIX sampler failure injected; native Windows tested separately")
    def test_sampler_failure_cleans_up_instead_of_running_unmonitored(self):
        self.folder.mkdir(parents=True)
        with patch.object(bench, "group_rss", side_effect=OSError("probe unavailable")):
            r = bench.run_child([sys.executable, "-c", "import time;time.sleep(10)"], 5, self.folder,
                                self.root, memory_limit_bytes=1024)
        self.assertEqual(r["status"], "failed")
        self.assertIn("memory_monitor_error", r["reason"])
        self.assertIsNotNone(r["exit_code"])

    def test_real_sampled_memory_tripwire(self):
        self.folder.mkdir(parents=True)
        r = bench.run_child([sys.executable, "-B", "-c", "import time;x=bytearray(16000000);time.sleep(10)"],
                            5, self.folder, self.root, memory_limit_bytes=1024**2)
        self.assertEqual((r["status"], r["reason"]), ("failed", "memory_limit_exceeded"))
        self.assertGreater(r["memory"]["sampled_peak_rss_bytes"], 1024**2)

    def test_windows_dispatch_uses_job_and_gate_not_killpg(self):
        self.folder.mkdir(parents=True)
        process = MagicMock()
        process.stdin = io.BytesIO()
        process.communicate.return_value = (b"ok", b"")
        process.returncode = 0
        job = MagicMock()
        with patch.object(bench.os, "name", "nt"), patch.object(bench, "WindowsJob", return_value=job), \
                patch.object(bench.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, create=True), \
                patch.object(bench.subprocess, "Popen", return_value=process) as popen, \
                patch.object(bench.os, "killpg", create=True) as killpg:
            result = bench.run_child([sys.executable, "-B", "-m", "fixture"], 5, self.folder, self.root)
        self.assertEqual(result["status"], "ok")
        self.assertIn("sys.stdin.buffer.read(1)", popen.call_args.args[0][3])
        job.attach.assert_called_once_with(process)
        job.close.assert_called_once()
        killpg.assert_not_called()

    def test_windows_assignment_failure_never_releases_solver_gate(self):
        self.folder.mkdir(parents=True)
        process = MagicMock()
        process.stdin = MagicMock()
        process.poll.return_value = None
        process.communicate.return_value = (b"", b"")
        job = MagicMock()
        job.attach.side_effect = OSError("nested jobs prohibited by host")
        with patch.object(bench.os, "name", "nt"), patch.object(bench, "WindowsJob", return_value=job), \
                patch.object(bench.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, create=True), \
                patch.object(bench.subprocess, "Popen", return_value=process), \
                patch.object(bench.os, "killpg", create=True) as killpg:
            with self.assertRaisesRegex(OSError, "nested jobs"):
                bench.run_child([sys.executable, "-B", "-m", "fixture"], 5, self.folder, self.root)
        process.stdin.write.assert_not_called()
        process.kill.assert_called_once()
        job.close.assert_called_once()
        killpg.assert_not_called()

    def test_interrupt_cleans_up_and_preserves_partial_logs(self):
        self.folder.mkdir(parents=True)
        process = MagicMock()
        process.communicate.side_effect = [KeyboardInterrupt(), (b"partial", b"error")]
        process.poll.return_value = None
        # Platform-independent cleanup control test; no live child here.
        with patch.object(bench.os, "name", "posix"), patch.object(bench.subprocess, "Popen", return_value=process), \
                patch.object(bench, "kill_tree") as cleanup:
            with self.assertRaises(KeyboardInterrupt):
                bench.run_child([sys.executable, "-c", "fixture"], 5, self.folder, self.root)
        self.assertGreaterEqual(cleanup.call_count, 1)
        process.kill.assert_called_once()
        self.assertEqual((self.folder / "stdout.txt").read_bytes(), b"partial")


if __name__ == "__main__":
    unittest.main()
