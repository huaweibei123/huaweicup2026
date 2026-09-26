import unittest
from src.q3_yuanzhifang.lower_bounds import bound_graph


class BoundTest(unittest.TestCase):
    def test_unavoidable_input_compute_output_path(self):
        graph = {'ops': [{'id': 1, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 10}],
                 'tensors': [{'id': 2, 'pos': 'L1', 'size': 120},
                             {'id': 3, 'pos': 'L1', 'size': 60}],
                 'edges': [{'source': 2, 'target': 1}, {'source': 1, 'target': 3}]}
        bound = bound_graph(graph, 5, 60)
        self.assertEqual(bound['lower_bound_cycles'], 13)
        self.assertEqual(bound['mandatory_ddr_service_bound'], 3)
        # Arbitrary original logical IDs could alias Cache keys: disable IO claim.
        graph['tensors'][0]['logical_tid'] = 3
        aliased = bound_graph(graph, 5, 60)
        self.assertIsNone(aliased['mandatory_ddr_service_bound'])
        self.assertEqual(aliased['lower_bound_cycles'], 10)

    def test_independent_same_pipe_work_is_shared_across_k(self):
        graph = {'ops': [{'id': i, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 11}
                         for i in range(5)], 'tensors': [], 'edges': []}
        bound = bound_graph(graph, 2, 60)
        self.assertEqual(bound['compute_work_bound'], 28)
        self.assertEqual(bound['compute_critical_path_bound'], 11)


if __name__ == '__main__':
    unittest.main()
