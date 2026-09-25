"""The frozen E2 public config omits max_iter; private replay requires it."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / 'scripts/q2_packet_native_pilot.py'
E2 = Path(os.environ['P2_TEST_E2_ROOT']).resolve() if os.environ.get('P2_TEST_E2_ROOT') else None
CONFIG = ROOT / 'data/raw/a/official/data/config.txt'


class ConfigNormalizationTest(unittest.TestCase):
    @unittest.skipUnless(E2, 'set P2_TEST_E2_ROOT to the frozen 603b E2 export')
    def test_frozen_public_config_and_private_default(self):
        self.assertTrue(E2.is_dir(), 'fixed 603b E2 export missing')
        self.assertEqual(hashlib.sha256((E2 / 'research/a/e2_search/_official_b.py').read_bytes()).hexdigest(),
                         'cdad4cbf0b3f4ca1aef8bfe8f8dcdc969a625ac64bd6cf4a1ab51a3bcfd3d78a')
        self.assertEqual(hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
                         'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9')
        sys.path.insert(0, str(E2))
        try:
            from research.a.e2_search import read_config
            public = read_config(str(CONFIG), problem=2)  # no graph or evaluator
        finally:
            sys.path.remove(str(E2))
        spec = importlib.util.spec_from_file_location('q2_packet_native_pilot', RUNNER)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        self.assertEqual(set(public), {'bandwidth', 'capacity', 'cross_core_copy_delay'})
        private = runner.normalize_p2_config(public)
        self.assertEqual(private['max_iter'], 1_000_000)
        self.assertEqual(set(private), {'bandwidth', 'capacity', 'cross_core_copy_delay', 'max_iter'})
        self.assertEqual(set(public), {'bandwidth', 'capacity', 'cross_core_copy_delay'})
        with self.assertRaises(ValueError):
            runner.normalize_p2_config(dict(public, unexpected=1))


if __name__ == '__main__':
    unittest.main()
