"""Applicability and budget checks on synthetic inputs; no evaluator calls."""
from contextlib import ExitStack
import copy
import unittest
from unittest.mock import Mock, patch

from src.q1 import unified
from src.q1.fork_frontier import construct as frontier
from tests.q1.test_capacity_return import chains
from tests.q1.test_component_pack import graph
from tests.q1.test_unified import PlanContract, scored


class GeneralFrontierTests(PlanContract):
    def test_varied_synthetic_widths_and_depths_get_legal_frontier(self):
        for width, depth, cores in [(3, 1, 2), (6, 3, 4), (11, 7, 5)]:
            with self.subTest(width=width, depth=depth):
                nodes = [(i * depth + j, 'V', 17 + i % 3)
                         for i in range(width) for j in range(depth)]
                links = [(i * depth + j, i * depth + j + 1)
                         for i in range(width) for j in range(depth - 1)]
                g = graph(nodes, links)
                original = copy.deepcopy(g)
                with patch.object(unified, 'fork_frontier', wraps=frontier) as f:
                    candidates, info = unified.generate_candidates(g, cores)
                f.assert_called_once_with(g, cores, grain=4)
                self.assertEqual(info['features']['frontier_route'], 'general-multicore')
                self.assertEqual(info['construction_failures'], [])
                self.assertEqual(g, original)
                plan, _ = frontier(g, cores)
                self.assert_plan_contract(plan, g, cores, links)
                digest = unified.hashlib.sha256(unified.plan_bytes(plan)).hexdigest()
                self.assertTrue(any(c['plan_sha256'] == digest for c in candidates))

    def test_six_distinct_candidates_preserve_order_and_failed_extra_score(self):
        g = chains(2)
        for t in g['tensors']:
            if t['id'] in (1000, 1004):
                t['size'] = 300000
        names = ['bounded', 'heavy', 'overload', 'shared_input',
                 'capacity_return', 'fork_frontier']
        with ExitStack() as stack:
            calls = {}
            for task, name in enumerate(names):
                plan = {'node_to_subgraph': {o['id']: task for o in g['ops']},
                        'core_schedules': [[task], []]}
                calls[name] = stack.enter_context(patch.object(
                    unified, name, return_value=(plan, {})))
            candidates, info = unified.generate_candidates(g, 2)
        self.assertEqual(len(candidates), unified.MAX_DISTINCT_CANDIDATES)
        self.assertEqual([c['name'] for c in candidates],
                         ['bounded', 'heavy-or-sink', 'overload', 'shared-input',
                          'capacity-return', 'fork-frontier'])
        for call in calls.values():
            self.assertEqual(call.call_count, 1)
        scorer = Mock(side_effect=[scored(100 - i, 0) for i in range(5)]
                                  + [{'status': 'timeout'}])
        winner, scores, reason = unified.choose(candidates, scorer)
        self.assertEqual(winner['name'], 'capacity-return')
        self.assertEqual(len(scores), 6)
        self.assertEqual(reason, 'first-score-failure')

    def test_existing_failed_frontier_attempt_is_not_repeated(self):
        g = graph([(i, 'V', 10) for i in range(4)], [(0, 1), (0, 2), (1, 3), (2, 3)])
        with patch.object(unified, 'fork_frontier', side_effect=ValueError('synthetic')) as f:
            _, info = unified.generate_candidates(g, 2)
        f.assert_called_once_with(g, 2, grain=4)
        self.assertEqual(info['features']['frontier_route'], 'existing-fork-route')
        self.assertEqual(sum(d['name'] == 'fork-frontier'
                             for d in info['construction_failures']), 1)


if __name__ == '__main__':
    unittest.main()
