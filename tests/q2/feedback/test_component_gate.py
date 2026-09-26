"""Hand-counted structural fixtures; no Step2, Step3, E0, or real case solves."""
import copy
import unittest
from unittest.mock import patch

from src.q2.feedback.component_gate import build, consider_alternative, service_profile
from src.q2.feedback.construct import UnsupportedStructure
from src.q2.feedback.frontier_gap import build as frontier_build
from src.q2.feedback.tensor_packet import TensorIndex
from tests.q2.feedback.test_frontier_gap import word_jobs
from tests.q2.test_physical_frontier import fixture


def chain(size=61):
    graph = {'ops': [
        {'id': 1, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 1},
        {'id': 2, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 1}],
        'tensors': [{'id': 101, 'pos': 'UB', 'size': size}],
        'edges': [{'source': 1, 'target': 101}, {'source': 101, 'target': 2}]}
    a = {'node_to_subgraph': {'1': 0, '2': 1}, 'core_schedules': [[0, 1], []]}
    b = {'node_to_subgraph': {'1': 0, '2': 1}, 'core_schedules': [[0], [1]]}
    return graph, a, b


class ComponentGateTests(unittest.TestCase):
    def test_per_core_input_fanout_and_zero_byte_direct_copies(self):
        graph, plan = fixture()
        p = service_profile(TensorIndex(graph), plan, 60)
        # Two inputs + one terminal output + two tensor links + two direct
        # links: 2+1+4+4 copies, including two zero-byte direct copies.
        self.assertEqual((p['base_copy_count'], p['base_copy_bytes'],
                          p['base_copy_service_cycles']), (11, 43, 11))
        self.assertEqual(p['cross_core_links'], 4)
        self.assertEqual(p['compute_work_by_core'], [1, 2, 1])
        self.assertFalse(p['whole_components'])

    def test_ideal_gate_requires_capacity_and_keeps_equality(self):
        graph, a, b = chain()
        index = TensorIndex(graph)
        yes = consider_alternative(index, a, b, 60, {'L1': 0, 'UB': 61})
        self.assertEqual((yes['ideal_U_A'], yes['ideal_L_B']), (2, 4))
        self.assertTrue(yes['choose_alternative'])
        no = consider_alternative(index, a, b, 60, {'L1': 0, 'UB': 60})
        self.assertFalse(no['choose_alternative'])
        # Two 60-byte copies cost 2, so U_A == L_B cannot trigger.
        graph, a, b = chain(60)
        self.assertFalse(consider_alternative(TensorIndex(graph), a, b, 60,
                                              {'L1': 0, 'UB': 60})['choose_alternative'])

    def test_cross_core_zero_bytes_never_certify_alternative_upper_bound(self):
        graph, a, b = chain(0)
        graph['edges'].append({'source': 1, 'target': 2, 'data_size': 0})
        index = TensorIndex(graph)
        p = service_profile(index, b, 60)
        self.assertEqual((p['base_copy_bytes'], p['base_copy_service_cycles']), (0, 4))
        decision = consider_alternative(index, b, a, 60, {'L1': 0, 'UB': 0})
        self.assertFalse(decision['choose_alternative'])
        self.assertIn('cross-core dependency', decision['reason'])

    def test_unsupported_domain_and_core_mismatch(self):
        graph, a, b = chain()
        for kind in ('alias', 'huge_cycles', 'huge_size', 'huge_direct'):
            altered = copy.deepcopy(graph)
            if kind == 'alias':
                altered['tensors'][0]['logical_tid'] = 101
            elif kind == 'huge_cycles':
                altered['ops'][0]['cycles'] = 2**53
            elif kind == 'huge_size':
                altered['tensors'][0]['size'] = 2**53
            else:
                altered['edges'].append({'source': 1, 'target': 2, 'data_size': 18014398509482041})
            with self.subTest(kind=kind), self.assertRaises(UnsupportedStructure):
                service_profile(TensorIndex(altered), b if kind == 'huge_direct' else a, 60)
        wrong = copy.deepcopy(b)
        wrong['core_schedules'].append([])
        with self.assertRaises(ValueError):
            consider_alternative(TensorIndex(graph), a, wrong, 60, {'L1': 0, 'UB': 61})

    def test_existing_word_is_unchanged_and_not_constructed_twice(self):
        index = TensorIndex(word_jobs())
        cap = {'L1': 100, 'UB': 100}
        expected, _ = frontier_build(index, 3, 60, 500, cap)
        with patch.object(index, 'build_tensor_plan', side_effect=AssertionError('second candidate')):
            actual, meta = build(index, 3, 60, 500, cap)
        self.assertEqual(actual, expected)
        self.assertEqual(meta['outer_plan_count'], 1)
        self.assertEqual(meta['online_E0_calls'], 0)

    def test_selection_and_nontrigger_preserve_exact_candidate_plans(self):
        graph, a, b = chain()
        index = TensorIndex(graph)
        base = {'selected': 'frontier_gap_unresolved', 'capacity_certified': False}
        with patch('src.q2.feedback.component_gate.frontier_build', return_value=(b, base)), \
                patch.object(index, 'build_tensor_plan', return_value=(a, {'selected': 'packet_eft'})):
            selected, meta = build(index, 2, 60, 500, {'L1': 0, 'UB': 61})
            unchanged, rejected = build(index, 2, 60, 500, {'L1': 0, 'UB': 60})
        self.assertEqual(selected, a)
        self.assertEqual(meta['selected'], 'component_gate_choose_tensor')
        self.assertEqual(unchanged, b)
        self.assertFalse(rejected['decision']['choose_alternative'])


if __name__ == '__main__':
    unittest.main()
