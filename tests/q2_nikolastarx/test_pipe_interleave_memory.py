"""Synthetic fixed-owner/Pipe FIFO interleaving invariants; no E0/E2."""
import unittest

from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan, topo
from src.q2_nikolastarx.pipe_interleave_memory import retime
from src.q2_nikolastarx.zero_spill_intervals import certify

CONFIG = {'capacity': {'L1': 15, 'UB': 15}, 'bandwidth': 60}


def check_invariants(test, graph, before, after, diag):
    old = derive_multicore_plan(graph, before)
    new = derive_multicore_plan(graph, after)
    test.assertEqual(old['mapping'], new['mapping'])
    test.assertEqual(old['core_by_subgraph'], new['core_by_subgraph'])
    index = DAGIndex(graph)
    inverse = {sg: u for u, sg in old['mapping'].items()}
    succ = {u: set(index.succ[u]) for u in index.ops}
    for old_row, new_row in zip(before['core_schedules'], after['core_schedules']):
        for pipe in {op['pipe'] for op in index.ops.values()}:
            test.assertEqual([inverse[sg] for sg in old_row
                              if index.ops[inverse[sg]]['pipe'] == pipe],
                             [inverse[sg] for sg in new_row
                              if index.ops[inverse[sg]]['pipe'] == pipe])
        for a, b in zip(new_row, new_row[1:]):
            succ[inverse[a]].add(inverse[b])
    test.assertEqual(set(topo(index.ops, succ)), set(index.ops))
    test.assertEqual(set(diag['global_topological_order']), set(index.ops))
    test.assertEqual(mandatory_copy_work(graph, before, 60)['transfer_bytes'],
                     mandatory_copy_work(graph, after, 60)['transfer_bytes'])


class PipeInterleaveMemoryTests(unittest.TestCase):
    def test_high_fanout_opening_and_last_touch_cache(self):
        graph = {'ops': [], 'tensors': [{'id': 100, 'pos': 'L1', 'size': 8}],
                 'edges': []}
        for u in range(1, 41):
            graph['ops'].append({'id': u, 'op': 'WORK',
                                 'pipe': 'PIPE_M' if u % 2 else 'PIPE_V',
                                 'cycles': 1})
            graph['tensors'].append({'id': 100 + u, 'pos': 'L1', 'size': 1})
            graph['edges'].extend(({'source': 100, 'target': u},
                                   {'source': u, 'target': 100 + u}))
        seed = {'node_to_subgraph': {str(u): u - 1 for u in range(1, 41)},
                'core_schedules': [list(range(40))]}
        result, diag = retime(graph, seed, CONFIG)
        check_invariants(self, graph, seed, result, diag)
        self.assertEqual(diag['new_peaks'], certify(graph, result, CONFIG)['peaks'])
        self.assertEqual(diag['new_peaks'][0]['L1'], 9)

    def test_cross_pipe_order_reduces_closed_touch_peak(self):
        graph = {'ops': [
            {'id': 1, 'op': 'WORK', 'pipe': 'PIPE_M', 'cycles': 1},
            {'id': 2, 'op': 'WORK', 'pipe': 'PIPE_V', 'cycles': 1},
            {'id': 3, 'op': 'WORK', 'pipe': 'PIPE_M', 'cycles': 1}],
            'tensors': [{'id': 10, 'pos': 'L1', 'size': 10},
                        {'id': 11, 'pos': 'L1', 'size': 1},
                        {'id': 12, 'pos': 'L1', 'size': 10},
                        {'id': 13, 'pos': 'L1', 'size': 1}],
            'edges': [{'source': 10, 'target': 1}, {'source': 1, 'target': 11},
                      {'source': 2, 'target': 12}, {'source': 10, 'target': 3},
                      {'source': 11, 'target': 3}, {'source': 3, 'target': 13}]}
        seed = {'node_to_subgraph': {'1': 0, '2': 1, '3': 2},
                'core_schedules': [[0, 1, 2]]}
        plan, diag = retime(graph, seed, CONFIG)
        check_invariants(self, graph, seed, plan, diag)
        self.assertLess(diag['new_peaks'][0]['L1'], diag['original_peaks'][0]['L1'])

    def test_cross_core_dependency_and_zero_direct_point(self):
        graph = {'ops': [
            {'id': 1, 'op': 'WORK', 'pipe': 'PIPE_M', 'cycles': 1},
            {'id': 2, 'op': 'WORK', 'pipe': 'PIPE_V', 'cycles': 1},
            {'id': 3, 'op': 'WORK', 'pipe': 'PIPE_M', 'cycles': 1},
            {'id': 4, 'op': 'WORK', 'pipe': 'PIPE_V', 'cycles': 1}],
            'tensors': [],
            'edges': [{'source': 1, 'target': 3, 'data_size': 0},
                      {'source': 3, 'target': 4, 'data_size': 4}]}
        seed = {'node_to_subgraph': {str(u): u - 1 for u in range(1, 5)},
                'core_schedules': [[0, 1], [2, 3]]}
        plan, diag = retime(graph, seed, CONFIG)
        check_invariants(self, graph, seed, plan, diag)

    def test_outside_certificate_guard_rejected(self):
        graph = {'ops': [{'id': 1, 'op': 'WORK', 'pipe': 'PIPE_M', 'cycles': 1}],
                 'tensors': [{'id': 10, 'pos': 'L1', 'size': 1,
                              'logical_tid': 10}],
                 'edges': [{'source': 10, 'target': 1}]}
        seed = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}
        with self.assertRaises(UnsupportedStructure):
            retime(graph, seed, CONFIG)


if __name__ == '__main__':
    unittest.main()
