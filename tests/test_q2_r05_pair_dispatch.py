"""Synthetic cleanup paths; never calls the Colab CLI."""
import importlib.util
from pathlib import Path
import tempfile
from unittest import TestCase

P = Path(__file__).resolve().parents[1] / 'scripts/q2_r05_pair_dispatch.py'
S = importlib.util.spec_from_file_location('pair_dispatch', P)
d = importlib.util.module_from_spec(S)
S.loader.exec_module(d)


class Watchdog:
    def __init__(self):
        self.terminated = False
    def terminate(self):
        self.terminated = True
    def wait(self, timeout=None):
        return 0
    def poll(self):
        return None if not self.terminated else 0


class CleanupTests(TestCase):
    def test_stop_failure_retains_watchdog_and_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            def command(argv, log):
                log.write_text('[colab] No active sessions found on server.')
                return 1 if argv[3] == 'stop' else 0
            watchdog = Watchdog()
            row = d.finish({'workload_completed': True}, command, watchdog, 'fake', out)
            self.assertEqual(row['status'], 'failed_or_unknown')
            self.assertTrue(row['watchdog_retained'])
            self.assertFalse(watchdog.terminated)

    def test_readback_error_retains_watchdog_and_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            def command(argv, log):
                if argv[3] == 'sessions':
                    raise OSError('synthetic readback failure')
                return 0
            watchdog = Watchdog()
            row = d.finish({'workload_completed': True}, command, watchdog, 'fake', out)
            self.assertEqual(row['status'], 'failed_or_unknown')
            self.assertIn('sessions_after_error', row)
            self.assertFalse(watchdog.terminated)

    def test_known_empty_only(self):
        self.assertTrue(d.empty_sessions('[colab] No active sessions found on server.\n'))
        self.assertTrue(d.empty_sessions('[]'))
        self.assertFalse(d.empty_sessions(''))
        self.assertFalse(d.empty_sessions('[colab] warning: sessions unavailable'))
        wrapper = d.cell_wrapper(b'print("controller")\n')
        self.assertIn(b'P2_R05_PAIR_MODE', wrapper)
        self.assertIn(b'P2_R05_PAIR_SHA256', wrapper)
        self.assertIn(d.CAPSULE_SHA.encode(), wrapper)

    def test_bad_batch_still_stops_and_reads_back(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / 'result.zip').write_bytes(b'broken zip')
            seen = []
            def command(argv, log):
                seen.append(argv[3])
                if argv[3] == 'sessions':
                    log.write_text('[colab] No active sessions found on server.')
                return 0
            watchdog = Watchdog()
            row = d.collect_and_finish({'exec_rc': 0}, command, watchdog, 'fake', out)
            self.assertEqual(seen, ['download', 'stop', 'sessions'])
            self.assertIn('batch_error', row)
            self.assertEqual(row['status'], 'failed_or_unknown')

    def test_success_stop_proven_releases_watchdog(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            def command(argv, log):
                if argv[3] == 'sessions':
                    log.write_text('[colab] No active sessions found on server.')
                return 0
            watchdog = Watchdog()
            row = d.finish({'workload_completed': True}, command, watchdog, 'fake', out)
            self.assertEqual(row['status'], 'completed')
            self.assertFalse(row['watchdog_retained'])
            self.assertTrue(watchdog.terminated)


if __name__ == '__main__':
    from unittest import main
    main()
