"""Synthetic scheduler checks; never constructs a plan or calls an evaluator."""
import json
import tempfile
import threading
import time
from pathlib import Path
from unittest import TestCase, main, mock

from src.q2_nikolastarx import hypergap_full500 as runner


class WorkerCapTests(TestCase):
    def test_manifest_worker_caps_and_compact_summary(self):
        for workers in (1, 2):
            with self.subTest(workers=workers):
                manifest = (runner.ROOT / 'results/a/q2-nikolastarx/hypergap-full500-20260925'
                            / f'manifest-workers{workers}.json')
                doc = json.loads(manifest.read_bytes())
                self.assertEqual(doc['limits']['workers'], workers)
                self.assertEqual({k: v for k, v in doc['limits'].items() if k != 'workers'},
                                 {k: v for k, v in runner.LIMITS.items() if k != 'workers'})
                rows = [{'case': f'{i:03d}', 'cores': 1} for i in range(1, 6)]
                active = peak = 0
                lock = threading.Lock()

                def fake_cell(row, *_args):
                    nonlocal active, peak
                    with lock:
                        active += 1
                        peak = max(peak, active)
                    time.sleep(0.02)
                    with lock:
                        active -= 1
                    return {'case': row['case'], 'cores': 1, 'status': 'accepted',
                            'calls': {key: 0 for key in ('E2_api_attempted', 'native_returns',
                                     'E0_fallback_confirmed', 'E0_fallback_possible',
                                     'E0_independent_started')}}

                with tempfile.TemporaryDirectory() as temp, \
                     mock.patch.object(runner, 'cell', fake_cell), \
                     mock.patch.object(runner.platform, 'system', return_value='Darwin'), \
                     mock.patch.object(runner.platform, 'machine', return_value='arm64'):
                    summary = runner.run(doc, {'rows': rows}, {}, manifest, Path('/unused'),
                                         Path('/unused'), Path('/unused'), Path(temp)/'run',
                                         'synthetic', time.perf_counter())
                self.assertEqual(peak, workers)
                self.assertEqual(summary['calls']['solver_started'], 5)
                self.assertEqual(summary['accepted_cells'], 5)
                self.assertFalse(summary['in_flight'])
                self.assertTrue(all('solver_ledger' not in row and 'result' not in row
                                    for row in summary['rows']))


if __name__ == '__main__':
    main()
