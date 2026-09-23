"""Avoid an unproved cache/duplicate equivalence at the search boundary."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/q1'))
from search import plan_key


class SearchKeys(unittest.TestCase):
    def test_mapping_insertion_order_is_preserved(self):
        a = {'node_to_subgraph': {'1': 0, '2': 0}, 'core_schedules': [[0], []]}
        b = {'node_to_subgraph': {'2': 0, '1': 0}, 'core_schedules': [[0], []]}
        self.assertNotEqual(plan_key(a), plan_key(b))

    def test_core_order_is_preserved(self):
        a = {'node_to_subgraph': {'1': 0, '2': 1}, 'core_schedules': [[0, 1], []]}
        b = {'node_to_subgraph': {'1': 0, '2': 1}, 'core_schedules': [[1, 0], []]}
        self.assertNotEqual(plan_key(a), plan_key(b))

    def test_equal_payloads_are_duplicates(self):
        a = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}
        self.assertEqual(plan_key(a), plan_key({'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}))


if __name__ == '__main__':
    unittest.main()
