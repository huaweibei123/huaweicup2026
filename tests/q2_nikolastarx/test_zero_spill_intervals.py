"""Tiny synthetic Step2 differentials; no P2 builder or evaluator calls."""
import contextlib
import io
import unittest

from src.q2_nikolastarx.direct import derive_multicore_plan  # installs official path
from src.q2_nikolastarx.zero_spill_intervals import certify
from schedule_step2 import Step2SchedulingError, step2_spill_insertion


def step2_zero(graph, sequence, capacity):
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return not step2_spill_insertion(graph, sequence, capacity)['spill_records']
    except Step2SchedulingError:
        return False


class IntervalCertificateTests(unittest.TestCase):
    def test_boundary_input_output_alloc_before_free_l1(self):
        original = {
            'ops': [{'id': 1, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2},
                    {'id': 9, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1}],
            'tensors': [{'id': 20, 'size': 6, 'pos': 'L1'},
                        {'id': 30, 'size': 7, 'pos': 'L1'},
                        {'id': 201, 'size': 7, 'pos': 'DDR'}],
            'edges': [{'source': 20, 'target': 1}, {'source': 1, 'target': 30},
                      {'source': 30, 'target': 9}, {'source': 9, 'target': 201}],
        }
        plan = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}
        local = {
            'ops': [{'id': 100, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 2},
                    original['ops'][0],
                    {'id': 101, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 2}],
            'tensors': original['tensors'] + [{'id': 200, 'size': 6, 'pos': 'DDR'}],
            'edges': [{'source': 200, 'target': 100}, {'source': 100, 'target': 20},
                      {'source': 20, 'target': 1}, {'source': 1, 'target': 30},
                      {'source': 30, 'target': 101}, {'source': 101, 'target': 201}],
        }
        for cap, expected in ((13, True), (12, False)):
            capacity = {'L1': cap, 'UB': 100}
            result = certify(original, plan, {'capacity': capacity})
            self.assertTrue(result['supported'], result['reason'])
            self.assertEqual(result['peaks'], [{'L1': 13, 'UB': 0}])
            self.assertEqual(result['zero_spill_certificate'], expected)
            self.assertEqual(step2_zero(local, [100, 1, 101], capacity), expected)

    def test_cross_direct_adds_ub_points_on_both_cores(self):
        original = {
            'ops': [{'id': 1, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2},
                    {'id': 2, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2}],
            'tensors': [],
            'edges': [{'source': 1, 'target': 2, 'data_size': 5}],
        }
        plan = {'node_to_subgraph': {'1': 0, '2': 1},
                'core_schedules': [[0], [1]]}
        source = {'ops': [original['ops'][0],
                          {'id': 100, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1}],
                  'tensors': [{'id': 50, 'pos': 'UB', 'size': 5},
                              {'id': 51, 'pos': 'DDR', 'size': 5}],
                  'edges': [{'source': 1, 'target': 50}, {'source': 50, 'target': 100},
                            {'source': 100, 'target': 51}]}
        target = {'ops': [{'id': 101, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1},
                          original['ops'][1]],
                  'tensors': source['tensors'],
                  'edges': [{'source': 51, 'target': 101}, {'source': 101, 'target': 50},
                            {'source': 50, 'target': 2}]}
        for cap, expected in ((5, True), (4, False)):
            capacity = {'L1': 0, 'UB': cap}
            result = certify(original, plan, {'capacity': capacity})
            self.assertTrue(result['supported'], result['reason'])
            self.assertEqual(result['peaks'], [{'L1': 0, 'UB': 5}, {'L1': 0, 'UB': 5}])
            self.assertEqual(result['zero_spill_certificate'], expected)
            self.assertEqual(step2_zero(source, [1, 100], capacity)
                             and step2_zero(target, [101, 2], capacity), expected)

    def test_actual_singleton_core_order_changes_peak(self):
        original = {
            'ops': [{'id': u, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1}
                    for u in (1, 2, 3)],
            'tensors': [{'id': 10, 'pos': 'L1', 'size': 8},
                        {'id': 11, 'pos': 'L1', 'size': 7}],
            'edges': [{'source': 10, 'target': 1}, {'source': 10, 'target': 3},
                      {'source': 2, 'target': 11}],
        }
        mapping = {'1': 0, '2': 1, '3': 2}
        local = {
            'ops': original['ops'] + [
                {'id': 100, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1},
                {'id': 101, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1}],
            'tensors': original['tensors'] + [
                {'id': 200, 'pos': 'DDR', 'size': 8},
                {'id': 201, 'pos': 'DDR', 'size': 7}],
            'edges': [{'source': 200, 'target': 100}, {'source': 100, 'target': 10},
                      {'source': 10, 'target': 1}, {'source': 10, 'target': 3},
                      {'source': 2, 'target': 11}, {'source': 11, 'target': 101},
                      {'source': 101, 'target': 201}],
        }
        for row, sequence, peak in (([0, 1, 2], [100, 1, 2, 101, 3], 15),
                                    ([1, 0, 2], [2, 101, 100, 1, 3], 8)):
            plan = {'node_to_subgraph': mapping, 'core_schedules': [row]}
            derive_multicore_plan(original, plan)
            capacity = {'L1': 10, 'UB': 100}
            result = certify(original, plan, {'capacity': capacity})
            self.assertTrue(result['supported'], result['reason'])
            self.assertEqual(result['peaks'][0]['L1'], peak)
            self.assertEqual(result['zero_spill_certificate'], peak <= 10)
            self.assertEqual(step2_zero(local, sequence, capacity), peak <= 10)

    def test_unsupported_alias_and_invalid_local_priority(self):
        graph = {'ops': [{'id': 1, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1},
                         {'id': 2, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1}],
                 'tensors': [{'id': 10, 'pos': 'L1', 'size': 1}],
                 'edges': [{'source': 1, 'target': 10}, {'source': 10, 'target': 2}]}
        plan = {'node_to_subgraph': {'1': 0, '2': 1}, 'core_schedules': [[0, 1]]}
        graph['tensors'][0]['logical_tid'] = 10
        self.assertFalse(certify(graph, plan, {'capacity': {'L1': 1, 'UB': 1}})['supported'])
        del graph['tensors'][0]['logical_tid']
        backwards = {'node_to_subgraph': plan['node_to_subgraph'], 'core_schedules': [[1, 0]]}
        self.assertFalse(certify(graph, backwards, {'capacity': {'L1': 1, 'UB': 1}})['supported'])


if __name__ == '__main__':
    unittest.main()
