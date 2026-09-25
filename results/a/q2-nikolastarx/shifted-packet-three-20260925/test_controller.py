"""Fake CLI only: no VM, official preparation, constructor, or evaluator."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent


def module():
    spec = importlib.util.spec_from_file_location('rcx_controller_test', HERE / 'controller.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class ControllerTests(unittest.TestCase):
    def test_exact_empty_response(self):
        m = module()
        text = '[colab] No active sessions found on server.'
        self.assertTrue(m.empty_sessions('  ' + text + '\n\n'))
        for invalid in ('', text + '\nACTIVE p1', 'error: ' + text, text * 2):
            self.assertFalse(m.empty_sessions(invalid))

    def test_expiry_prevents_cli_dispatch(self):
        m = module()
        def forbidden(*args):
            self.fail('expired lease dispatched CLI')
        m.call = forbidden
        with self.assertRaises(TimeoutError):
            m.live_call(time.monotonic() - 1, 'exec', ['exec'], 10)

    def test_upload_expiry_prevents_following_exec(self):
        m = module()
        calls = []
        m.call = lambda stage, args, timeout: calls.append((stage, timeout))
        m.live_call(time.monotonic() + 1, 'upload', ['upload'], 30)
        with self.assertRaises(TimeoutError):
            m.live_call(time.monotonic() - 1, 'exec', ['exec'], 170)
        self.assertEqual([x[0] for x in calls], ['upload'])
        self.assertLessEqual(calls[0][1], 1)

    def test_drift_precedes_attempt_marker(self):
        for drift in ('controller.py', 'bootstrap.py', 'runner'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory(dir=HERE) as tmp:
                m = module(); m.OUT = Path(tmp)
                for name in ('freeze.json', 'launch-files.json', 'bootstrap.py'):
                    shutil.copyfile(HERE / name, m.OUT / name)
                if drift == 'controller.py':
                    hashes = json.loads((m.OUT / 'launch-files.json').read_bytes())
                    hashes['controller.py'] = '0' * 64
                    (m.OUT / 'launch-files.json').write_text(json.dumps(hashes))
                elif drift == 'bootstrap.py':
                    (m.OUT / 'bootstrap.py').write_text('changed')
                else:
                    m.RUNNER = m.OUT / 'runner.py'
                    m.RUNNER.write_text('changed')
                m.call = lambda *args: self.fail('drift reached CLI')
                with self.assertRaises(ValueError):
                    m.main()
                self.assertFalse((m.OUT / 'controller-attempt.json').exists())

    def test_detached_watchdog_survives_parent_exit(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            folder = Path(tmp)
            fake = folder / 'fake-colab'
            marker = folder / 'fake-stop.json'
            fake.write_text('#!' + sys.executable + '\nimport json,sys\nfrom pathlib import Path\n'
                            + 'Path(' + repr(str(marker)) + ').write_text(json.dumps(sys.argv[1:]))\n')
            fake.chmod(0o700)
            child = folder / 'watchdog-child.py'
            child.write_text('import importlib.util,time\nfrom pathlib import Path\n'
                + 's=importlib.util.spec_from_file_location("watchdog",' + repr(str(HERE / 'controller.py')) + ')\n'
                + 'm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n'
                + 'm.OUT=Path(' + repr(str(folder)) + ');m.CLI=' + repr(str(fake)) + '\n'
                + 'm.watchdog(time.monotonic()+0.2)\n'
                + 'Path(' + repr(str(folder / 'done')) + ').write_text("done")\n')
            parent = ('import os,subprocess,sys\n'
                      + 'subprocess.Popen([sys.executable,"-B",' + repr(str(child))
                      + '],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
                      + 'os._exit(7)\n')
            exited = subprocess.run([sys.executable, '-B', '-c', parent], timeout=2)
            self.assertEqual(exited.returncode, 7)
            deadline = time.monotonic() + 3
            while not (folder / 'done').exists() and time.monotonic() < deadline:
                time.sleep(0.03)
            self.assertTrue((folder / 'done').exists())
            self.assertEqual(json.loads(marker.read_bytes()),
                             ['--auth', 'oauth2', 'stop', '-s', module().NAME])
            self.assertEqual(json.loads((folder / 'lease-stop.json').read_bytes())['returncode'], 0)


if __name__ == '__main__':
    unittest.main()
