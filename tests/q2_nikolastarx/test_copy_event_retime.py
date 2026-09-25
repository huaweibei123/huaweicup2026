"""Small synthetic tests for the optional static COPY-event retimer."""
import unittest

from src.q2_nikolastarx.copy_event_retime import retime
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from evaluation_validation import EvaluationValidationError


def fixture():
    graph = {
        'ops': [
            {'id': 1, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 3},
            {'id': 2, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 2},
            {'id': 3, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2},
            {'id': 4, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 3},
        ],
        'tensors': [
            {'id': 10, 'pos': 'L1', 'size': 10},
            {'id': 11, 'pos': 'L1', 'size': 10},
            {'id': 20, 'pos': 'DDR', 'size': 6},
            {'id': 30, 'pos': 'L1', 'size': 4},
            {'id': 40, 'pos': 'L1', 'size': 4},
        ],
        'edges': [
            {'source': 1, 'target': 10}, {'source': 10, 'target': 2},
            {'source': 10, 'target': 3},
            {'source': 4, 'target': 11}, {'source': 11, 'target': 2},
            {'source': 20, 'target': 1}, {'source': 20, 'target': 2},
            {'source': 3, 'target': 30}, {'source': 2, 'target': 40},
            {'source': 1, 'target': 2, 'data_size': 0},
            {'source': 4, 'target': 3, 'data_size': 0},
        ],
    }
    plan = {'node_to_subgraph': {'1': 0, '4': 1, '2': 2, '3': 3},
            'core_schedules': [[0, 1], [2, 3]]}
    return graph, plan


class CopyEventRetimeTests(unittest.TestCase):
    def test_boundary_shared_cross_direct_queue_and_lag(self):
        graph, plan = fixture()
        output, detail = retime(graph, plan,
                                {'bandwidth': 5, 'cross_core_copy_delay_cycles': 500})
        self.assertEqual(set(output), {'node_to_subgraph', 'core_schedules'})
        self.assertEqual(detail['copy_counts']['boundary_in'], 2)
        self.assertEqual(detail['copy_counts']['boundary_out'], 2)
        self.assertEqual(detail['copy_counts']['cross_tensor_pairs'], 2)
        self.assertEqual(detail['copy_counts']['cross_direct_pairs'], 2)
        self.assertEqual(detail['cross_link_count'], 4)
        self.assertTrue(detail['cross_link_release_checks'])
        starts = {int(k): v for k, v in detail['static_event_starts'].items()}
        ends = {int(k): v for k, v in detail['static_event_ends'].items()}
        for co, ci, targets in detail['cross_links']:
            self.assertGreaterEqual(starts[ci], ends[co] + 500)
            self.assertTrue(all(starts[u] >= ends[ci] for u in targets))
        self.assertGreaterEqual(starts[3], 0)
        # All COPYs on one MTE Pipe are serialized, including boundary and
        # zero-byte direct COPYs; shared tensor fans out through one target IN.
        resources = {int(u): row for u, row in detail['static_event_resources'].items()}
        for core in (0, 1):
            for pipe in ('PIPE_MTE2', 'PIPE_MTE3'):
                ids = [u for u, row in resources.items()
                       if row['core'] == core and row['pipe'] == pipe]
                intervals = sorted((starts[u], ends[u]) for u in ids)
                self.assertTrue(all(x[1] <= y[0] for x, y in zip(intervals, intervals[1:])))
        self.assertEqual(sum(3 in targets for _, _, targets in detail['cross_links']), 2)
        original = derive_multicore_plan(graph, plan)
        changed = derive_multicore_plan(graph, output)
        self.assertEqual(original['core_by_subgraph'], changed['core_by_subgraph'])

    def test_hand_derived_single_transfer_timeline(self):
        graph = {'ops': [
            {'id': 1, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 3},
            {'id': 2, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 2}],
            'tensors': [{'id': 10, 'pos': 'DDR', 'size': 20},
                        {'id': 11, 'pos': 'L1', 'size': 10},
                        {'id': 12, 'pos': 'L1', 'size': 6}],
            'edges': [{'source': 10, 'target': 1}, {'source': 1, 'target': 11},
                      {'source': 11, 'target': 2}, {'source': 2, 'target': 12}]}
        plan = {'node_to_subgraph': {'1': 0, '2': 1}, 'core_schedules': [[0], [1]]}
        _, d = retime(graph, plan, {'bandwidth': 5, 'cross_core_copy_delay_cycles': 500})
        # Input [0,4], M [4,7], OUT [7,9], IN [509,511], V [511,513], output [513,515].
        self.assertEqual(d['static_event_starts']['1'], 4)
        self.assertEqual(d['static_event_starts']['2'], 511)
        self.assertEqual(d['static_event_finish_cycles'], 515)
        self.assertEqual(d['events'], 6)

    def test_duplicate_direct_edges_rejected_by_official_entry(self):
        graph, plan = fixture()
        graph['edges'].append({'source': 1, 'target': 2, 'data_size': 0})
        with self.assertRaisesRegex(EvaluationValidationError, 'duplicate edge'):
            retime(graph, plan, {'bandwidth': 5, 'cross_core_copy_delay_cycles': 500})

    def test_excluded_copy_path_rejected(self):
        graph = {'ops': [
            {'id': 1, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 3},
            {'id': 2, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 2},
            {'id': 3, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1}],
            'tensors': [], 'edges': [{'source': 1, 'target': 3}, {'source': 3, 'target': 2}]}
        plan = {'node_to_subgraph': {'1': 0, '2': 1}, 'core_schedules': [[0, 1]]}
        with self.assertRaisesRegex(UnsupportedStructure, 'contracted edges'):
            retime(graph, plan, {'bandwidth': 5, 'cross_core_copy_delay_cycles': 500})

    def test_logical_alias_rejected(self):
        graph, plan = fixture()
        graph['tensors'][0]['logical_tid'] = 99
        with self.assertRaises(UnsupportedStructure):
            retime(graph, plan, {'bandwidth': 5, 'cross_core_copy_delay_cycles': 500})


if __name__ == '__main__':
    unittest.main()
