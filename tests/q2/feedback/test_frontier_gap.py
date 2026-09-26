"""Structural regressions for capacity-gated routing; no official E0 calls."""
import unittest
from unittest.mock import patch

from src.q2.feedback.frontier_gap import build, repair_whole_cores
from src.q2.feedback.gap_packet import build as gap_build
from src.q2.feedback.physical_frontier import certificate
from src.q2.feedback.tensor_packet import TensorIndex
from tests.q2.feedback.test_gap_packet import diamond
from tests.q2.feedback.test_lifecycle_window import groups


def word_jobs():
    graph = {'ops': [], 'tensors': [], 'edges': []}
    for j in range(6):
        a, b, c = 3*j+1, 3*j+2, 3*j+3
        graph['ops'].extend({'id': u, 'op': 'COMPUTE', 'pipe': p, 'cycles': d}
                            for u, p, d in [(a, 'PIPE_M', 10), (b, 'PIPE_V', 12), (c, 'PIPE_M', 10)])
        x, y = 1000+2*j, 1001+2*j
        graph['tensors'].extend({'id': t, 'pos': 'UB', 'size': 12} for t in (x, y))
        graph['edges'].extend({'source': u, 'target': v} for u, v in
                              [(a, x), (x, b), (b, y), (y, c), (a, c)])
    return graph


class FrontierGapTests(unittest.TestCase):
    def test_certified_word_avoids_general_calendar(self):
        index = TensorIndex(word_jobs())
        expected, _ = index.build(3, 'resource_word')
        with patch('src.q2.feedback.frontier_gap.gap_build', side_effect=AssertionError('calendar called')):
            actual, meta = build(index, 3, 60, 500, {'L1': 100, 'UB': 100})
        self.assertEqual(actual, expected)
        self.assertEqual(meta['selected'], 'frontier_resource_word')
        self.assertTrue(meta['capacity_certified'])

    def test_shared_lifetimes_repair_only_after_full_certificate(self):
        index = TensorIndex(groups([(1,), (2,)], copies=3))
        cap = {'L1': 60, 'UB': 0}
        baseline, _ = gap_build(index, 1, 60, 500, cap)
        # Interleave both shared-input cohorts before their last consumer.
        mapping = baseline['node_to_subgraph']
        baseline['core_schedules'] = [[mapping[str(u)] for u in
                                       (1, 11, 3, 13, 5, 15, 2, 12, 4, 14, 6, 16)]]
        initial = certificate(index, baseline, cap)
        self.assertFalse(initial['certified'])
        plan, details = repair_whole_cores(index, baseline, cap, initial)
        cert = certificate(index, plan, cap)
        self.assertNotEqual(plan, baseline)
        self.assertEqual(plan['node_to_subgraph'], baseline['node_to_subgraph'])
        self.assertTrue(details[0]['changed'])
        self.assertTrue(cert['certified'])
        self.assertEqual(cert['cores'][0]['peak_bytes']['L1'], 40)

    def test_triangle_shared_inputs_are_not_freed_between_groups(self):
        index = TensorIndex(groups([(1, 2), (2, 3), (1, 3)]))
        cap = {'L1': 100, 'UB': 0}
        expected, _ = gap_build(index, 1, 60, 500, cap)
        actual, meta = build(index, 1, 60, 500, cap)
        self.assertEqual(actual, expected)
        self.assertFalse(meta['capacity_certified'])
        self.assertEqual(meta['repair'][0]['reason'], 'full sequence still exceeds capacity')

    def test_certified_generic_and_alias_plans_remain_exact(self):
        graph = diamond()
        cap = {'L1': 100, 'UB': 100}
        for alias in (False, True):
            if alias:
                graph['tensors'].append({'id': 1000, 'pos': 'L1', 'size': 1, 'logical_tid': 1000})
            index = TensorIndex(graph)
            expected, _ = gap_build(index, 2, 60, 500, cap)
            actual, meta = build(index, 2, 60, 500, cap)
            self.assertEqual(actual, expected)
            self.assertEqual(meta['online_E0_calls'], 0)
            self.assertEqual(meta['capacity_certified'], not alias)

    def test_word_route_checks_fixed_parameters(self):
        index = TensorIndex(word_jobs())
        for bandwidth, delay in [(True, 500), (float('nan'), 500), (60, -1)]:
            with self.assertRaises(ValueError):
                build(index, 2, bandwidth, delay, {'L1': 100, 'UB': 100})


if __name__ == '__main__':
    unittest.main()
