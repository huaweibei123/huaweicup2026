import unittest

from src.q3_yuanzhifang.head_tail_bound import analyze
from src.q3_yuanzhifang.lower_bounds import bound_graph


class BoundScopeTest(unittest.TestCase):
    def test_multiple_original_writers_require_separate_proof(self):
        graph = {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 1}
                         for u in (1, 2, 3)],
                 'tensors': [{'id': 10, 'pos': 'UB', 'size': 60}],
                 'edges': [{'source': 1, 'target': 10}, {'source': 2, 'target': 10},
                           {'source': 10, 'target': 3}]}
        with self.assertRaisesRegex(ValueError, 'one original producer'):
            analyze(graph, 60)
        with self.assertRaisesRegex(ValueError, 'one original producer'):
            bound_graph(graph, 2, 60)

    def test_unique_original_writer_keeps_existing_bound(self):
        graph = {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 1}
                         for u in (1, 2)],
                 'tensors': [{'id': 10, 'pos': 'UB', 'size': 60}],
                 'edges': [{'source': 1, 'target': 10}, {'source': 10, 'target': 2}]}
        self.assertEqual(analyze(graph, 60, [2])[0]['lower_bound_cycles'], 2)
        self.assertEqual(bound_graph(graph, 2, 60)['lower_bound_cycles'], 2)


if __name__ == '__main__':
    unittest.main()
