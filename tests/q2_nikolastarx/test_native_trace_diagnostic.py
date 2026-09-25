"""Synthetic private-E2 shape tests; no official graph preparation or replay."""
import unittest
from types import SimpleNamespace

from src.q2_nikolastarx.native_trace_diagnostic import diagnose


def fake_module(*, bad_start=False, fail=False, duplicate_key=False,
                bad_movement=False, duplicate_original=False):
    source = {'id': 10, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 3}
    out = {'id': 11, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 2}
    inside = {'id': 12, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 2}
    target = {'id': 13, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 4}
    prepared_target = dict(target, id=10) if duplicate_original else target

    def task(core, ops):
        a, b = ops
        graph = {'ops': ops, 'tensors': [], 'edges': [{'source': a['id'], 'target': b['id']}]}
        return {'core_id': core, 'op_by_id': {o['id']: o for o in ops},
                'seq': [a['id'], b['id']],
                'op_preds': {a['id']: set(), b['id']: {a['id']}},
                'pipe_ops': {o['pipe']: [o['id']] for o in ops},
                'step3': {'execution_graph': graph, 'memory_dependencies': []}}
    tasks = {0: task(0, [source, out]), 1: task(1, [inside, prepared_target])}
    links = [{'tensor_id': 99, 'size': 16, 'source_core': 0, 'target_core': 1,
              'source_copy_out_id': 11, 'target_copy_in_id': 12}]

    def build(*args, **kwargs):
        if fail:
            raise RuntimeError('synthetic prepare failed')
        return tasks, links, 17 if bad_movement else 16, {}, None

    runtime = SimpleNamespace(_build_scene_b_tasks=build)
    class Evaluator:
        def __init__(self, graph, problem):
            assert problem == 2
            self._fast_runtime = runtime

        def _native_score(self, plan, config, debug):
            assert debug is True
            self._fast_runtime._build_scene_b_tasks({}, plan, config['bandwidth'], config['capacity'])
            keys = [(0, 10), (0, 11), (1, 12), (1, prepared_target['id'])]
            if duplicate_key:
                keys[-1] = (1, 12)
            starts = [0, 3, 11 if bad_start else 10, 12]
            ends = [3, 5, 13 if bad_start else 12, 16]
            return {'status': 'ok', 'route': 'native', 'makespan': 16,
                    'data_movement_bytes': {}, 'cross_task_traffic': 16,
                    'replay_iterations': 4, 'preparation_seconds': 0.1,
                    'replay_seconds': 0.2, 'compilation_cache_hit': False,
                    'debug': {'op_keys': tuple(keys), 'op_start': starts,
                              'op_end': ends, 'makespan': 16, 'stats': [16]}}
    module = SimpleNamespace(SceneBEvaluator=Evaluator)
    graph = {'ops': [source, target], 'tensors': [{'id': 99, 'size': 16, 'pos': 'UB'}],
             'edges': [{'source': 10, 'target': 99}, {'source': 99, 'target': 13}]}
    return module, runtime, build, graph


CFG = {'bandwidth': 60, 'capacity': {'L1': 1, 'UB': 1},
       'max_iter': 100, 'cross_core_copy_delay': 5}
TAGS = {'algorithm_commit': 'fixed', 'e2_commit': 'fixed'}
PLAN = {'node_to_subgraph': {'10': 0, '13': 1}, 'core_schedules': [[0], [1]]}


class NativeTraceDiagnosticTests(unittest.TestCase):
    def test_one_prepare_native_score_critical_link_and_restore(self):
        module, runtime, build, graph = fake_module()
        out = diagnose(module, graph, PLAN, CFG, TAGS, include_trace=True)
        self.assertEqual(out['diagnostic_status'], 'consistent')
        self.assertEqual(out['counts'], {'native_attempted': 1, 'native_returned': 1,
                                         'prepare_observed': 1})
        self.assertIs(runtime._build_scene_b_tasks, build)
        self.assertEqual(out['score']['makespan'], 16)
        self.assertEqual(out['trace_result']['makespan'], 16)
        self.assertEqual(sum(len(t['ops']) for t in out['trace_result']['per_core_timeline']), 4)
        self.assertEqual(out['critical_links'][0]['source_copy_out_id'], 11)
        self.assertEqual(out['critical_original_ids']['op_ids'], [10, 13])
        self.assertEqual(out['critical_original_ids']['tensor_ids'], [99])
        self.assertEqual(len(out['input_identity']['graph_canonical_sha256']), 64)

    def test_residual_or_coverage_failure_returns_no_diagnostic(self):
        for option in ({'bad_start': True}, {'duplicate_key': True}, {'bad_movement': True}):
            module, runtime, build, graph = fake_module(**option)
            out = diagnose(module, graph, PLAN, CFG, TAGS)
            self.assertEqual(out['diagnostic_status'], 'unavailable')
            self.assertEqual(out['critical_links'], [])
            self.assertEqual(out['counts']['native_returned'], 1)
            self.assertIs(runtime._build_scene_b_tasks, build)

    def test_prepare_failure_restores_without_fallback(self):
        module, runtime, build, graph = fake_module(fail=True)
        out = diagnose(module, graph, PLAN, CFG, TAGS)
        self.assertEqual(out['diagnostic_status'], 'unavailable')
        self.assertEqual(out['counts'], {'native_attempted': 1, 'native_returned': 0,
                                         'prepare_observed': 0})
        self.assertEqual(out['error']['type'], 'RuntimeError')
        self.assertIs(runtime._build_scene_b_tasks, build)

    def test_original_id_duplicate_wrong_owner_or_kind_fails_closed(self):
        module, runtime, build, graph = fake_module(duplicate_original=True)
        out = diagnose(module, graph, PLAN, CFG, TAGS)
        self.assertEqual(out['diagnostic_status'], 'unavailable')
        self.assertIn('repeats', out['error']['message'])
        self.assertIs(runtime._build_scene_b_tasks, build)

        module, _, _, graph = fake_module()
        swapped = {'node_to_subgraph': {'10': 0, '13': 1}, 'core_schedules': [[1], [0]]}
        out = diagnose(module, graph, swapped, CFG, TAGS)
        self.assertEqual(out['diagnostic_status'], 'unavailable')
        self.assertIn('owner/kind', out['error']['message'])

        module, _, _, graph = fake_module()
        graph['ops'][1] = dict(graph['ops'][1], pipe='PIPE_M')
        out = diagnose(module, graph, PLAN, CFG, TAGS)
        self.assertEqual(out['diagnostic_status'], 'unavailable')
        self.assertIn('owner/kind', out['error']['message'])

        module, _, _, graph = fake_module()
        incomplete = {'node_to_subgraph': {'10': 0}, 'core_schedules': [[0], []]}
        out = diagnose(module, graph, incomplete, CFG, TAGS)
        self.assertEqual(out['diagnostic_status'], 'unavailable')
        self.assertEqual(out['critical_original_ids']['op_ids'], [])


if __name__ == '__main__':
    unittest.main()
