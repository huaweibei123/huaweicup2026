"""Tiny P2 physical-token fixtures; no solver or E0 invocation."""
import copy
import unittest

from src.q2.feedback.physical_frontier import certificate
from src.q2.feedback.tensor_packet import TensorIndex
from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks


def fixture():
    ops = [{'id': u, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 1}
           for u in (1, 2, 3, 4)]
    tensors = [{'id': 101, 'pos': 'L1', 'size': 4},
               {'id': 102, 'pos': 'DDR', 'size': 7},
               {'id': 103, 'pos': 'L1', 'size': 5},
               {'id': 104, 'pos': 'UB', 'size': 6}]
    pairs = [(101, 1), (102, 1), (1, 103), (1, 104),
             (103, 2), (103, 3), (103, 4)]
    edges = [{'source': a, 'target': b} for a, b in pairs]
    edges += [{'source': 1, 'target': 2, 'data_size': 0},
              {'source': 1, 'target': 3, 'data_size': 3}]
    graph = {'ops': ops, 'tensors': tensors, 'edges': edges}
    plan = {'node_to_subgraph': {str(u): u - 1 for u in (1, 2, 3, 4)},
            'core_schedules': [[0], [1, 3], [2]]}
    return graph, plan


class PhysicalFrontierTests(unittest.TestCase):
    def test_official_prefix_confirms_certified_fanout_bytes_and_no_spill(self):
        graph, plan = fixture()
        cap = {'L1': 9, 'UB': 16}
        cert = certificate(TensorIndex(graph), plan, cap)
        tasks, _, _, movement, _ = _build_scene_b_tasks(graph, plan, 60, cap)
        actual_count = sum(op['op'] in ('COPY_IN', 'COPY_OUT')
                           for task in tasks.values() for op in task['op_by_id'].values())
        self.assertTrue(cert['certified'])
        self.assertEqual(movement['spill_added_copy_bytes'], 0)
        self.assertEqual((cert['base_copy_bytes'], cert['base_copy_count']),
                         (movement['scheduled_copy_bytes'], actual_count))

    def test_official_prefix_same_core_direct_and_empty_core(self):
        graph, plan = fixture()
        plan['core_schedules'] = [[0, 1, 2, 3], []]
        cap = {'L1': 9, 'UB': 16}
        cert = certificate(TensorIndex(graph), plan, cap)
        tasks, _, _, movement, _ = _build_scene_b_tasks(graph, plan, 60, cap)
        actual_count = sum(op['op'] in ('COPY_IN', 'COPY_OUT')
                           for task in tasks.values() for op in task['op_by_id'].values())
        self.assertTrue(cert['certified'])
        self.assertEqual(movement['spill_added_copy_bytes'], 0)
        self.assertEqual((cert['base_copy_bytes'], cert['base_copy_count']),
                         (movement['scheduled_copy_bytes'], actual_count))
        self.assertFalse(any(t['id'].startswith('direct:') for t in cert['cores'][0]['tokens']))
        self.assertEqual(cert['cores'][1]['tokens'], [])
        self.assertEqual(cert['cores'][1]['peak_bucket'], {'L1': None, 'UB': None})

    def test_cross_tensor_fanout_direct_edges_and_closed_bucket(self):
        graph, plan = fixture()
        result = certificate(TensorIndex(graph), plan, {'L1': 9, 'UB': 16})
        self.assertTrue(result['certified'])
        self.assertEqual(result['base_copy_bytes'], 43)
        self.assertEqual(result['base_copy_count'], 11)
        self.assertEqual([c['peak_bytes'] for c in result['cores']],
                         [{'L1': 9, 'UB': 16}, {'L1': 5, 'UB': 0}, {'L1': 5, 'UB': 3}])
        source = result['cores'][0]
        self.assertEqual(source['peak_bucket'], {'L1': 0, 'UB': 0})
        self.assertEqual({t['id'] for t in source['peak_live_tokens']['UB']},
                         {'tensor:102:c0', 'tensor:104:c0', 'direct:8:c0', 'direct:7:c0'})
        self.assertEqual(sum(t['id'] == 'tensor:103:c0' for t in source['tokens']), 1)
        self.assertEqual(len([t for t in result['cores'][1]['tokens'] if t['id'] == 'tensor:103:c1']), 1)

    def test_one_byte_capacity_failure_reports_same_peak(self):
        graph, plan = fixture()
        result = certificate(TensorIndex(graph), plan, {'L1': 8, 'UB': 16})
        self.assertFalse(result['certified'])
        self.assertFalse(result['cores'][0]['certified'])
        self.assertEqual(result['cores'][0]['peak_bytes']['L1'], 9)
        self.assertEqual(result['cores'][0]['peak_live_tokens']['L1'],
                         [{'id': 'tensor:101:c0', 'size': 4},
                          {'id': 'tensor:103:c0', 'size': 5}])

    def test_alias_non_singleton_and_invalid_plan_rejected(self):
        graph, plan = fixture()
        aliased = copy.deepcopy(graph)
        aliased['tensors'][0]['logical_tid'] = 101
        with self.assertRaises(ValueError):
            certificate(TensorIndex(aliased), plan, {'L1': 9, 'UB': 16})
        merged = copy.deepcopy(plan)
        merged['node_to_subgraph']['4'] = merged['node_to_subgraph']['2']
        merged['core_schedules'][1] = [1]
        with self.assertRaises(ValueError):
            certificate(TensorIndex(graph), merged, {'L1': 9, 'UB': 16})
        invalid = copy.deepcopy(plan)
        del invalid['node_to_subgraph']['3']
        with self.assertRaises(ValueError):
            certificate(TensorIndex(graph), invalid, {'L1': 9, 'UB': 16})


if __name__ == '__main__':
    unittest.main()
