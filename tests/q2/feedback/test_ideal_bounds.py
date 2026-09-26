"""Hand-derived bounds and a COPY-contraction counterexample; no scoring."""
import copy
import unittest

from src.q2.feedback.construct import UnsupportedStructure
from src.q2.feedback.ideal_bounds import candidate_lower_bound
from src.q2.feedback.tensor_packet import TensorIndex
from tests.q2.feedback.test_component_gate import chain


def plan_for(cores):
    nodes = sorted(u for core in cores for u in core)
    mapping = {str(u): i for i, u in enumerate(nodes)}
    return {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in core] for core in cores]}


class IdealBoundsTests(unittest.TestCase):
    def test_tensor_lag_with_parallel_direct_is_max_not_sum(self):
        graph, _, plan = chain(120)
        graph['ops'][0]['cycles'], graph['ops'][1]['cycles'] = 2, 3
        graph['edges'].append({'source': 1, 'target': 2, 'data_size': 0})
        r = candidate_lower_bound(TensorIndex(graph), plan, 60, 500)
        self.assertEqual((r['ddr_service_cycles'], r['per_core_pipe_work_cycles'],
                          r['physical_path_cycles']), (6, 3, 509))
        self.assertEqual(r['critical_path_ops'], [1, 2])
        self.assertEqual(r['critical_path_edges'][0]['kind'], 'tensor')
        self.assertEqual(r['physical_arc_count'], 2)

    def test_two_independent_inputs_are_not_serialized(self):
        graph = {'ops': [{'id': u, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 1}
                         for u in (1, 2, 3)], 'tensors': [],
                 'edges': [{'source': u, 'target': 3, 'data_size': 0} for u in (1, 2)]}
        r = candidate_lower_bound(TensorIndex(graph), plan_for([[1], [2], [3]]), 60, 500)
        self.assertEqual((r['ddr_service_cycles'], r['physical_path_cycles']), (4, 504))

    def test_core_priority_is_not_a_serial_execution_dependency(self):
        graph = {'ops': [{'id': 1, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 10},
                         {'id': 2, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 20}],
                 'tensors': [], 'edges': []}
        r = candidate_lower_bound(TensorIndex(graph), plan_for([[1, 2]]), 60, 500)
        self.assertEqual((r['physical_path_cycles'], r['ideal_lower_bound_cycles']), (20, 20))
        graph['ops'][1]['pipe'] = 'PIPE_M'
        r = candidate_lower_bound(TensorIndex(graph), plan_for([[1, 2]]), 60, 500)
        self.assertEqual((r['physical_path_cycles'], r['ideal_lower_bound_cycles']), (20, 30))

    def test_original_copy_bridge_is_not_a_physical_cross_link(self):
        graph = {'ops': [
            {'id': 1, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 100},
            {'id': 2, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 0},
            {'id': 3, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 0},
            {'id': 4, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 100}],
            'tensors': [{'id': t, 'pos': pos, 'size': 61}
                        for t, pos in [(11, 'UB'), (12, 'DDR'), (13, 'UB')]],
            'edges': [{'source': u, 'target': v} for u, v in
                      [(1, 11), (11, 2), (2, 12), (12, 3), (3, 13), (13, 4)]]}
        index = TensorIndex(graph)
        self.assertIn(4, index.succ[1])
        r = candidate_lower_bound(index, plan_for([[1], [4]]), 60, 500)
        self.assertEqual(r['contracted_pairs_without_physical_arc'], 1)
        self.assertEqual((r['ddr_service_cycles'], r['physical_path_cycles'],
                          r['physical_arc_count'], r['cross_core_links']), (4, 100, 0, 0))

    def test_same_core_tensor_has_no_transfer_delay(self):
        graph, plan, _ = chain(61)
        r = candidate_lower_bound(TensorIndex(graph), plan, 60, 500)
        self.assertEqual((r['physical_path_cycles'], r['ddr_service_cycles']), (2, 0))
        self.assertEqual(r['critical_path_edges'][0]['lag_cycles'], 0)

    def test_fifo_and_physical_path_combine_without_serializing_all_pipes(self):
        graph = {'ops': [
            {'id': 1, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 2},
            {'id': 2, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 3},
            {'id': 3, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 4}],
            'tensors': [], 'edges': [{'source': 2, 'target': 3, 'data_size': 0}]}
        r = candidate_lower_bound(TensorIndex(graph), plan_for([[1, 2], [3]]), 60, 500)
        self.assertEqual((r['physical_path_cycles'], r['fifo_path_cycles']), (509, 511))
        self.assertEqual(r['critical_path_ops'], [1, 2, 3])
        self.assertEqual(r['critical_path_edges'][0]['kind'], 'pipe_fifo')
        graph['edges'] = []
        r = candidate_lower_bound(TensorIndex(graph), plan_for([[1, 3, 2]]), 60, 500)
        self.assertEqual((r['fifo_arc_count'], r['fifo_path_cycles']), (1, 5))

    def test_cross_core_dependencies_can_cycle_with_pipe_fifo(self):
        graph = {'ops': [{'id': u, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 1}
                         for u in (1, 2, 3, 4)], 'tensors': [],
                 'edges': [{'source': 2, 'target': 3, 'data_size': 0},
                           {'source': 4, 'target': 1, 'data_size': 0}]}
        with self.assertRaisesRegex(UnsupportedStructure, 'contain a cycle'):
            candidate_lower_bound(TensorIndex(graph), plan_for([[1, 2], [3, 4]]), 60, 500)

    def test_numeric_alias_and_multi_producer_domains(self):
        graph, _, plan = chain()
        for delay in (-1, True, 0.5, 2**32):
            with self.subTest(delay=delay), self.assertRaises(UnsupportedStructure):
                candidate_lower_bound(TensorIndex(graph), plan, 60, delay)
        for kind in ('alias', 'huge_cycles', 'producer'):
            altered = copy.deepcopy(graph)
            if kind == 'alias':
                altered['tensors'][0]['logical_tid'] = 101
            elif kind == 'huge_cycles':
                altered['ops'][0]['cycles'] = 2**53
            else:
                altered['ops'].append({'id': 3, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 1})
                altered['edges'].append({'source': 3, 'target': 101})
            with self.subTest(kind=kind), self.assertRaises(UnsupportedStructure):
                candidate_lower_bound(TensorIndex(altered), plan, 60, 500)


if __name__ == '__main__':
    unittest.main()
