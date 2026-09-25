"""Small synthetic prepared/trace contracts; no official preparation or evaluator."""
from copy import deepcopy
import json
import unittest

from src.q2_nikolastarx.prepared_trace_contract import audit, capture


def fixture():
    left = [{'id': 1, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 3},
            {'id': 2, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 2}]
    right = [{'id': 1, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 2},
             {'id': 2, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 4}]
    def task(core, ops, memory):
        graph = {'ops': ops, 'tensors': [], 'edges': [{'source': 1, 'target': 2}]}
        return {'core_id': core, 'op_by_id': {o['id']: o for o in ops},
                'seq': [1, 2], 'op_preds': {1: set(), 2: {1}},
                'pipe_ops': {o['pipe']: [o['id']] for o in ops},
                'step3': {'execution_graph': graph,
                          'memory_dependencies': memory}}
    tasks = {0: task(0, left, [{'source': 1, 'target': 2, 'kind': 'reuse',
                                'positions': [0], 'reused_bytes': 16,
                                'previous_tensor_ids': [8]}]),
             1: task(1, right, [])}
    links = [{'tensor_id': 8, 'size': 16, 'source_core': 0, 'target_core': 1,
              'source_copy_out_id': 2, 'target_copy_in_id': 1}]
    def item(core, op, kind, pipe, start, end):
        return {'task_id': core, 'op_id': op, 'op': kind, 'pipe': pipe,
                'start': start, 'end': end, 'duration': end - start}
    result = {'scene': 'B', 'num_cores': 2, 'makespan': 16,
              'bandwidth_bytes_per_cycle': 60,
              'cross_core_copy_delay_cycles': 5, 'task_dependencies': links,
              'step3_by_core': {0: {'memory_dependency_count': 1,
                                    'pipe_op_counts': {'PIPE_M': 1, 'PIPE_MTE3': 1}},
                                1: {'memory_dependency_count': 0,
                                    'pipe_op_counts': {'PIPE_MTE2': 1, 'PIPE_V': 1}}},
              'per_core_timeline': [
                  {'core_id': 0, 'ops': [item(0, 1, 'COMPUTE', 'PIPE_M', 0, 3),
                                         item(0, 2, 'COPY_OUT', 'PIPE_MTE3', 3, 5)]},
                  {'core_id': 1, 'ops': [item(1, 1, 'COPY_IN', 'PIPE_MTE2', 10, 12),
                                         item(1, 2, 'COMPUTE', 'PIPE_V', 12, 16)]}]}
    return tasks, links, result


class PreparedTraceContractTests(unittest.TestCase):
    def test_exact_gates_duplicate_numeric_ids_and_json_contract(self):
        tasks, links, result = fixture()
        contract = capture(tasks, links)
        json.dumps(contract, allow_nan=False)
        self.assertEqual(len(contract['operations']), 4)
        self.assertTrue(next(o for o in contract['operations'] if o['core'] == 0 and o['id'] == 1)['is_compute'])
        checked = audit(contract, result)
        self.assertTrue(checked['consistent'])
        self.assertEqual(checked['residuals'], [])
        self.assertEqual(checked['critical_cross_links'][0]['exposed_delay_cycles'], 5)
        self.assertEqual(checked['critical_cross_links'][0]['delay_range'], [0, 5])
        self.assertEqual(checked['critical_cross_links'][0]['tensor_id'], 8)
        self.assertEqual(checked['critical_cross_links'][0]['size'], 16)
        self.assertEqual(checked['critical_cross_links'][0]['source_copy_out_id'], 2)
        self.assertEqual(checked['critical_cross_links'][0]['target_copy_in_id'], 1)
        self.assertEqual(checked['critical_cross_links'][0]['source_core'], 0)
        self.assertEqual(checked['critical_cross_links'][0]['target_core'], 1)
        self.assertEqual(contract['prepared_by_core'][0]['memory_dependencies'][0]['previous_tensor_ids'], [8])
        self.assertEqual(len(checked['critical_operations']), 4)

    def test_missing_memory_edge_and_predecessor_disagreement_fail_capture(self):
        tasks, links, _ = fixture()
        tasks[0]['step3']['execution_graph']['edges'].clear()
        with self.assertRaisesRegex(ValueError, 'predecessors disagree'):
            capture(tasks, links)
        tasks, links, _ = fixture()
        tasks[0]['step3']['memory_dependencies'][0]['target'] = 1
        with self.assertRaisesRegex(ValueError, 'memory dependency missing'):
            capture(tasks, links)
        tasks, links, _ = fixture()
        tasks[0]['step3']['memory_dependencies'].clear()
        tasks[0]['step3']['execution_graph']['edges'][0]['dependency'] = 'MEMORY_REUSE'
        with self.assertRaisesRegex(ValueError, 'tagged execution memory edge'):
            capture(tasks, links)

    def test_pipe_omission_duplicate_and_cross_kind_fail_capture(self):
        tasks, links, _ = fixture()
        tasks[0]['pipe_ops']['PIPE_MTE3'] = []
        with self.assertRaisesRegex(ValueError, 'partition'):
            capture(tasks, links)
        tasks, links, _ = fixture()
        tasks[0]['step3']['execution_graph']['ops'].append(dict(tasks[0]['step3']['execution_graph']['ops'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            capture(tasks, links)
        tasks, links, _ = fixture()
        links[0]['source_copy_out_id'] = 1
        with self.assertRaisesRegex(ValueError, 'COPY_OUT'):
            capture(tasks, links)

    def test_residual_blocks_critical_claim(self):
        tasks, links, result = fixture()
        contract = capture(tasks, links)
        result['per_core_timeline'][1]['ops'][0]['start'] = 11
        result['per_core_timeline'][1]['ops'][0]['end'] = 13
        result['per_core_timeline'][1]['ops'][1]['start'] = 13
        result['per_core_timeline'][1]['ops'][1]['end'] = 17
        result['makespan'] = 17
        checked = audit(contract, result)
        self.assertFalse(checked['consistent'])
        self.assertEqual(checked['residuals'][0]['residual'], 1)
        self.assertEqual(checked['critical_cross_links'], [])

    def test_missing_or_duplicate_trace_op_and_wrong_duration_fail_closed(self):
        tasks, links, result = fixture()
        contract = capture(tasks, links)
        missing = deepcopy(result)
        missing['per_core_timeline'][0]['ops'].pop()
        self.assertFalse(audit(contract, missing)['consistent'])
        duplicate = deepcopy(result)
        duplicate['per_core_timeline'][0]['ops'].append(duplicate['per_core_timeline'][0]['ops'][0])
        self.assertFalse(audit(contract, duplicate)['consistent'])
        wrong = deepcopy(result)
        wrong['per_core_timeline'][0]['ops'][0]['duration'] = 4
        self.assertFalse(audit(contract, wrong)['consistent'])

    def test_wrong_cross_link_and_fifo_order_fail_closed(self):
        tasks, links, result = fixture()
        contract = capture(tasks, links)
        wrong = deepcopy(result)
        wrong['task_dependencies'][0]['source_copy_out_id'] = 1
        self.assertFalse(audit(contract, wrong)['consistent'])
        tasks, links, result = fixture()
        tasks[0]['step3']['execution_graph']['ops'][1]['pipe'] = 'PIPE_M'
        tasks[0]['op_by_id'][2]['pipe'] = 'PIPE_M'
        tasks[0]['pipe_ops'] = {'PIPE_M': [2, 1]}
        contract = capture(tasks, links)
        self.assertFalse(audit(contract, result)['consistent'])  # trace Pipe differs

    def test_makespan_and_kind_mismatch_fail_closed(self):
        tasks, links, result = fixture()
        contract = capture(tasks, links)
        wrong = deepcopy(result)
        wrong['makespan'] = 15
        self.assertFalse(audit(contract, wrong)['consistent'])
        wrong = deepcopy(result)
        wrong['per_core_timeline'][1]['ops'][1]['op'] = 'COPY_OUT'
        self.assertFalse(audit(contract, wrong)['consistent'])
        wrong = deepcopy(result)
        wrong['step3_by_core'][0]['memory_dependency_count'] = 0
        self.assertFalse(audit(contract, wrong)['consistent'])
        wrong = deepcopy(result)
        wrong['per_core_timeline'][0]['ops'][0].update(end=4, duration=4)
        self.assertFalse(audit(contract, wrong)['consistent'])

    def test_competing_local_gate_exposes_only_part_of_delay(self):
        tasks, links, result = fixture()
        op = {'id': 3, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 8}
        tasks[1]['step3']['execution_graph']['ops'].append(op)
        tasks[1]['step3']['execution_graph']['edges'].append({'source': 3, 'target': 1})
        tasks[1]['op_by_id'][3] = op
        tasks[1]['op_preds'][1] = {3}
        tasks[1]['op_preds'][3] = set()
        tasks[1]['seq'] = [3, 1, 2]
        tasks[1]['pipe_ops']['PIPE_M'] = [3]
        result['step3_by_core'][1]['pipe_op_counts']['PIPE_M'] = 1
        result['per_core_timeline'][1]['ops'].insert(0, {
            'task_id': 1, 'op_id': 3, 'op': 'COMPUTE', 'pipe': 'PIPE_M',
            'start': 0, 'end': 8, 'duration': 8})
        checked = audit(capture(tasks, links), result)
        self.assertTrue(checked['consistent'])
        self.assertEqual(checked['critical_cross_links'][0]['exposed_delay_cycles'], 2)
        self.assertNotIn([1, 3], checked['critical_operations'])

    def test_empty_core_and_all_empty_trace_are_legal(self):
        tasks, links, result = fixture()
        empty = {'core_id': 2, 'op_by_id': {}, 'seq': [], 'op_preds': {},
                 'pipe_ops': {}, 'step3': {'execution_graph': {'ops': [], 'tensors': [], 'edges': []},
                                          'memory_dependencies': []}}
        tasks[2] = empty
        result['num_cores'] = 3
        result['step3_by_core'][2] = {'memory_dependency_count': 0, 'pipe_op_counts': {}}
        result['per_core_timeline'].append({'core_id': 2, 'ops': []})
        self.assertTrue(audit(capture(tasks, links), result)['consistent'])
        only_empty = {0: dict(empty, core_id=0)}
        zero = {'scene': 'B', 'num_cores': 1, 'makespan': 0,
                'bandwidth_bytes_per_cycle': 60, 'cross_core_copy_delay_cycles': 5,
                'step3_by_core': {0: {'memory_dependency_count': 0, 'pipe_op_counts': {}}},
                'task_dependencies': [], 'per_core_timeline': [{'core_id': 0, 'ops': []}]}
        checked = audit(capture(only_empty, []), zero)
        self.assertTrue(checked['consistent'])
        self.assertEqual(checked['critical_cross_links'], [])


if __name__ == '__main__':
    unittest.main()
