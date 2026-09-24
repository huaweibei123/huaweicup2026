"""Bounds on hand-verifiable work, plus unsupported-domain abstention."""
import unittest
from src.q2_nikolastarx.bounds import assigned_pipe_lower_bound


class BoundsTests(unittest.TestCase):
    def test_same_pipe_serial_work_and_distinct_pipe_overlap(self):
        graph = {'ops': [
            {'id': 1, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 7},
            {'id': 2, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 5},
            {'id': 3, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10},
            {'id': 4, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 999}]}
        one = {'node_to_subgraph': {'1': 0, '2': 1, '3': 2},
               'core_schedules': [[0, 1, 2], []]}
        split = {'node_to_subgraph': one['node_to_subgraph'],
                 'core_schedules': [[0, 2], [1]]}
        self.assertEqual(assigned_pipe_lower_bound(graph, one), 12)
        self.assertEqual(assigned_pipe_lower_bound(graph, split), 10)

    def test_float_cycles_and_incomplete_owner_abstain(self):
        graph = {'ops': [{'id': 1, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 0.3}]}
        plan = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}
        self.assertIsNone(assigned_pipe_lower_bound(graph, plan))
        graph['ops'][0]['cycles'] = 3
        plan['core_schedules'] = [[]]
        self.assertIsNone(assigned_pipe_lower_bound(graph, plan))


if __name__ == '__main__':
    unittest.main()
