"""Failure containment and nontrivial plan-edit contracts for the refinement."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/q1'))
from profile_refine import atomic_plan, run_guarded
from profile_candidates import is_cover, split_plan, merge_plan
from test_structure import graph
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


class RefineContracts(unittest.TestCase):
    def test_failed_promotion_preserves_old_confirmed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / 'confirmed_plan.json'
            checkpoint.write_bytes(b'old confirmed')
            with mock.patch('profile_refine.os.replace', side_effect=OSError('injected failure')):
                with self.assertRaises(OSError):
                    atomic_plan(checkpoint, b'new candidate')
            self.assertEqual(checkpoint.read_bytes(), b'old confirmed')
            atomic_plan(checkpoint, b'new confirmed')
            self.assertEqual(checkpoint.read_bytes(), b'new confirmed')

    def test_plan_edits_preserve_mapping_order_and_full_dependency_legality(self):
        g = graph(4, [(0, 1), (1, 2), (2, 3)])
        p = {'node_to_subgraph': {'3': 7, '1': 7, '0': 7, '2': 7}, 'core_schedules': [[7], []]}
        split = split_plan(p, 7, {2, 3})
        self.assertEqual(list(split['node_to_subgraph']), ['3', '1', '0', '2'])
        validate_task_order(derive_multicore_plan(g, split))
        merged = merge_plan(split, 7, 8)
        self.assertEqual(merged, p)
        self.assertEqual(list(merged['node_to_subgraph']), list(p['node_to_subgraph']))

    def test_core_chain_alternative_path_blocks_merge(self):
        self.assertFalse(is_cover({0: {1, 2}, 1: {2}, 2: set()}, 0, 2))
        self.assertTrue(is_cover({0: {1}, 1: {2}, 2: set()}, 0, 1))

    def test_supervisor_timeout_keeps_existing_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            checkpoint = folder / 'confirmed_plan.json'
            checkpoint.write_text('known good bytes')
            row = run_guarded([sys.executable, '-c', 'import time; time.sleep(30)'], folder, wall_seconds=0.2)
            self.assertEqual(row['status'], 'wall_budget_exceeded')
            self.assertIsNotNone(row['returncode'])
            self.assertEqual(checkpoint.read_text(), 'known good bytes')

    def test_supervisor_rss_stop_and_process_error_are_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = run_guarded([sys.executable, '-c', 'import time; time.sleep(30)'], Path(tmp), rss_bytes=1)
            self.assertEqual(row['status'], 'rss_budget_exceeded')
            self.assertGreater(row['sampled_group_peak_rss_bytes'], 1)
        with tempfile.TemporaryDirectory() as tmp:
            row = run_guarded([sys.executable, '-c', 'raise SystemExit(7)'], Path(tmp))
            self.assertEqual(row['status'], 'process_error')
            self.assertEqual(row['returncode'], 7)


if __name__ == '__main__':
    unittest.main()
