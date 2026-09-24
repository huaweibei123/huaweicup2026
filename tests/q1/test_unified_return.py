"""Synthetic integration checks; do not execute any scoring backend."""
import unittest
from unittest.mock import Mock

from src.q1 import unified
from tests.q1.test_capacity_return import chains


class ReturnIntegrationTests(unittest.TestCase):
    def test_real_constructor_reaches_guard_with_legal_plan(self):
        graph = chains(5)
        candidates, info = unified.generate_candidates(graph, 2)
        self.assertEqual(info['construction_failures'], [])
        self.assertEqual(info['features']['return_route'], 'strict-private-chain-check')
        new = next(x for x in candidates if x['name'] == 'capacity-return')
        self.assertEqual(new['details']['packet'], 3)
        self.assertLessEqual(len(candidates), 5)
        for candidate in candidates:
            self.assertEqual(set(candidate['plan']), {'node_to_subgraph', 'core_schedules'})
        def score(m):
            return dict(status='ok', makespan=m, data_movement_bytes={'scheduled_copy_bytes': 0})
        costs = [score(100 if c['name'] != 'capacity-return' else 120) for c in candidates]
        selected, _, _ = unified.choose(candidates, Mock(side_effect=costs))
        self.assertNotEqual(selected['name'], 'capacity-return')
        costs = [score(100 if c['name'] != 'capacity-return' else 80) for c in candidates]
        selected, _, _ = unified.choose(candidates, Mock(side_effect=costs))
        self.assertEqual(selected['name'], 'capacity-return')

    def test_one_core_does_not_add_return_cut_or_score(self):
        candidates, _ = unified.generate_candidates(chains(5), 1)
        self.assertEqual([x['name'] for x in candidates], ['bounded'])
        _, records, reason = unified.choose(candidates, None)
        self.assertEqual(records, [])
        self.assertEqual(reason, 'single-distinct-plan')


if __name__ == '__main__':
    unittest.main()
