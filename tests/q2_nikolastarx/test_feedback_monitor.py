"""Owned-process cleanup tests only; no solver or official evaluator call."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from src.q2_nikolastarx.evaluate_feedback import monitored, process_snapshot


class MonitorTests(unittest.TestCase):
    def test_timeout_cleans_new_session_descendant(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            pidfile = folder / 'child.json'
            command = [sys.executable, '-c',
                "import json,subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True); "
                "open(sys.argv[1],'w').write(json.dumps(p.pid)); time.sleep(60)", str(pidfile)]
            receipt = monitored(command, folder / 'logs', time.perf_counter() + 0.5, 4 * 1024**3)
            self.assertEqual(receipt['status'], 'timeout')
            child = json.loads(pidfile.read_text())
            self.assertIn(child, receipt['cleanup_killed_pids'])
            # Allow the OS to reap an orphaned child after SIGKILL.
            for _ in range(20):
                if child not in process_snapshot():
                    break
                time.sleep(.01)
            self.assertNotIn(child, process_snapshot())

    def test_rss_threshold_stops_only_owned_process(self):
        with tempfile.TemporaryDirectory() as raw:
            receipt = monitored([sys.executable, '-c', 'import time; time.sleep(60)'],
                                Path(raw), time.perf_counter() + 5, 1)
            self.assertEqual(receipt['status'], 'rss_limit')
            self.assertGreater(receipt['observer_inclusive_peak_rss_bytes'], 1)
            self.assertLess(receipt['wall_seconds'], 5)

    def test_success_and_error_are_preserved(self):
        with tempfile.TemporaryDirectory() as raw:
            for code in (0, 7):
                receipt = monitored([sys.executable, '-c', f'raise SystemExit({code})'],
                                    Path(raw) / str(code), time.perf_counter() + 5, 4 * 1024**3)
                self.assertEqual(receipt['exit_code'], code)
                self.assertEqual(receipt['status'], 'ok' if code == 0 else 'failed')
                self.assertEqual(receipt['cleanup_killed_pids'], [])


if __name__ == '__main__':
    unittest.main()
