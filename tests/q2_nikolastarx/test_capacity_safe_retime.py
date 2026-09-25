"""Synthetic fixed-owner adjacent swaps; no official evaluator calls."""
import unittest
import random

from src.q2_nikolastarx.capacity_safe_retime import retime
from src.q2_nikolastarx.direct import UnsupportedStructure
from src.q2_nikolastarx.zero_spill_intervals import certify


def plan(row, cores=1):
    return {'node_to_subgraph': {'1': 0, '2': 1, '3': 2},
            'core_schedules': [row] if cores == 1 else row}


class CapacitySafeRetimeTests(unittest.TestCase):
    def test_incremental_updates_match_full_certificate_recomputation(self):
        # The reference recalculates all tensor lifetimes after each tentative
        # swap, independently of the optimized two-position bookkeeping.
        for random_seed in range(20):
            rng = random.Random(random_seed)
            n = 9
            graph = {'ops': [{'id': i, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1}
                             for i in range(n)], 'tensors': [], 'edges': []}
            for tid in range(20, 35):
                graph['tensors'].append({'id': tid, 'pos': rng.choice(['L1', 'UB']),
                                          'size': rng.randrange(1, 12)})
                for u in rng.sample(range(n), rng.randrange(1, n)):
                    graph['edges'].append({'source': tid, 'target': u})
            mapping = {str(i): i for i in range(n)}
            seed_row = list(range(n)); rng.shuffle(seed_row)
            target_row = list(range(n)); rng.shuffle(target_row)
            seed = {'node_to_subgraph': mapping, 'core_schedules': [seed_row]}
            target = {'node_to_subgraph': mapping, 'core_schedules': [target_row]}
            peak = certify(graph, seed, {'capacity': {'L1': 10000, 'UB': 10000}})['peaks'][0]
            config = {'capacity': peak}
            actual, _ = retime(graph, seed, target, config)
            row = seed_row[:]
            rank = {u: i for i, u in enumerate(target_row)}
            for scan in (range(n-1), range(n-2, -1, -1)):
                for i in scan:
                    if rank[row[i]] > rank[row[i+1]]:
                        candidate = row[:]
                        candidate[i], candidate[i+1] = candidate[i+1], candidate[i]
                        check = {'node_to_subgraph': mapping, 'core_schedules': [candidate]}
                        if certify(graph, check, config)['zero_spill_certificate']:
                            row = candidate
            self.assertEqual(actual['core_schedules'], [row])
            self.assertTrue(certify(graph, actual, config)['zero_spill_certificate'])

    def test_safe_exchange_follows_target_and_certifies(self):
        graph = {'ops': [{'id': i, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1}
                         for i in (1, 2, 3)],
                 'tensors': [{'id': 10, 'size': 8, 'pos': 'L1'},
                             {'id': 11, 'size': 7, 'pos': 'UB'}],
                 'edges': [{'source': 1, 'target': 10},
                           {'source': 11, 'target': 2}]}
        seed, target = plan([0, 1, 2]), plan([1, 0, 2])
        config = {'capacity': {'L1': 8, 'UB': 7}}
        result, diag = retime(graph, seed, target, config)
        self.assertEqual(result, target)
        self.assertEqual(diag['accepted'], 1)
        self.assertTrue(certify(graph, result, config)['zero_spill_certificate'])
        self.assertEqual(seed['core_schedules'], [[0, 1, 2]])

    def test_capacity_blocks_adjacent_inversion(self):
        graph = {'ops': [{'id': i, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1}
                         for i in (1, 2, 3)],
                 'tensors': [{'id': 10, 'size': 8, 'pos': 'L1'},
                             {'id': 11, 'size': 7, 'pos': 'L1'}],
                 'edges': [{'source': 10, 'target': 1},
                           {'source': 10, 'target': 3},
                           {'source': 2, 'target': 11}]}
        seed, target = plan([1, 0, 2]), plan([0, 1, 2])
        config = {'capacity': {'L1': 10, 'UB': 0}}
        result, diag = retime(graph, seed, target, config)
        self.assertEqual(result, seed)
        self.assertEqual(diag['capacity_rejections'], 2)
        self.assertTrue(certify(graph, result, config)['zero_spill_certificate'])

    def test_dependency_blocks_inversion(self):
        graph = {'ops': [{'id': i, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1}
                         for i in (1, 2, 3)],
                 'tensors': [{'id': 10, 'size': 1, 'pos': 'L1'}],
                 'edges': [{'source': 1, 'target': 10},
                           {'source': 10, 'target': 2}]}
        seed = plan([0, 1, 2])
        # An invalid target is rejected by the same strict structural guard.
        with self.assertRaises(UnsupportedStructure):
            retime(graph, seed, plan([1, 0, 2]), {'capacity': {'L1': 1, 'UB': 0}})

    def test_cross_direct_point_moves_with_op(self):
        graph = {'ops': [{'id': i, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1}
                         for i in (1, 2, 3)],
                 'tensors': [{'id': 10, 'size': 6, 'pos': 'UB'}],
                 'edges': [{'source': 1, 'target': 3, 'data_size': 5},
                           {'source': 2, 'target': 10}]}
        seed = plan([[1, 0], [2]], 2)
        target = plan([[0, 1], [2]], 2)
        config = {'capacity': {'L1': 0, 'UB': 6}}
        result, diag = retime(graph, seed, target, config)
        self.assertEqual(result, target)
        self.assertEqual(diag['accepted'], 1)
        self.assertTrue(certify(graph, result, config)['zero_spill_certificate'])


if __name__ == '__main__':
    unittest.main()
