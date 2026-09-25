"""Synthetic stop/readback gates; never calls Colab or starts a VM."""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/q2_rank_prep_colab_dispatch.py"
SPEC = importlib.util.spec_from_file_location("q2_rank_prep_colab_dispatch", SCRIPT)
dispatch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dispatch)


class FakeWatchdog:
    def __init__(self):
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


class StopProofTest(unittest.TestCase):
    def check_case(self, receipt, expected_completed):
        watchdog = FakeWatchdog()
        status = dispatch.final_status(True, receipt)
        dispatch.release_watchdog_if_proven(watchdog, receipt)
        self.assertEqual(status == "completed", expected_completed)
        self.assertEqual(watchdog.terminated, expected_completed)
        self.assertEqual(receipt["watchdog_termination_skipped"], not expected_completed)

    def test_only_successful_stop_and_absent_readback_release_watchdog(self):
        self.check_case({"stop_exit_code": 0, "sessions_readback_exit_code": 0,
                         "named_session_still_active": False}, True)

    def test_failed_stop_retains_watchdog(self):
        self.check_case({"stop_exit_code": 1, "sessions_readback_exit_code": 0,
                         "named_session_still_active": False}, False)

    def test_failed_or_missing_readback_retains_watchdog(self):
        self.check_case({"stop_exit_code": 0, "sessions_readback_exit_code": 1}, False)
        self.check_case({"stop_exit_code": 0, "sessions_readback_error": "timeout"}, False)
        self.check_case({"stop_exit_code": 0, "sessions_readback_exit_code": 0}, False)

    def test_session_still_listed_or_stop_error_retains_watchdog(self):
        self.check_case({"stop_exit_code": 0, "sessions_readback_exit_code": 0,
                         "named_session_still_active": True}, False)
        self.check_case({"stop_exit_code": 0, "sessions_readback_exit_code": 0,
                         "named_session_still_active": False,
                         "stop_error": "uncertain"}, False)

    def test_failed_workload_cannot_be_completed_even_with_proven_stop(self):
        receipt = {"stop_exit_code": 0, "sessions_readback_exit_code": 0,
                   "named_session_still_active": False}
        self.assertEqual(dispatch.final_status(False, receipt), "failed_or_unknown")


if __name__ == "__main__":
    unittest.main()
