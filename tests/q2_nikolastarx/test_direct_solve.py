"""Router mechanism/CLI checks on tiny synthetic DAGs; zero E0/E1/E2.

The evaluator entrypoint and process launcher are poisoned while construction
runs, so a zero-valued calls field alone cannot make this check pass.
"""
from contextlib import ExitStack, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import direct_solve as router
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import Index, derive_multicore_plan

CONFIG = {'bandwidth': 60, 'cross_core_copy_delay_cycles': 500,
          'capacity': {'L1': 524288, 'UB': 131072}}


def word_graph(jobs=3, vector_cycles=10):
    ops, edges = [], []
    for j in range(jobs):
        ids = (j * 3 + 1, j * 3 + 2, j * 3 + 3)
        ops.extend({'id': u, 'op': 'COMPUTE', 'pipe': p, 'cycles': d}
                   for u, p, d in zip(ids, ('PIPE_M', 'PIPE_V', 'PIPE_M'),
                                      (10, vector_cycles, 10)))
        edges.extend({'source': u, 'target': v} for u, v in zip(ids, ids[1:]))
    return {'ops': ops, 'tensors': [], 'edges': edges}


def general_graph():
    return {'ops': [{'id': 1, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10},
                    {'id': 2, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 2000},
                    {'id': 3, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 2000},
                    {'id': 4, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10}],
            'tensors': [],
            'edges': [{'source': u, 'target': v} for u, v in ((1, 2), (1, 3), (2, 4), (3, 4))]}


class DirectRouterTests(unittest.TestCase):
    def no_evaluation(self):
        context = ExitStack()
        for name in ('subprocess.Popen',
                     'multicore_cut_evaluate_problem_2.evaluate_scene_b',
                     'multicore_cut_evaluate_problem_2._build_scene_b_tasks'):
            context.enter_context(patch(name, side_effect=AssertionError('evaluation/process forbidden')))
        return context

    def test_guarded_word_never_calls_general_constructor(self):
        graph = word_graph()
        expected, _ = Index(graph).build(2, 'resource_word')
        with self.no_evaluation(), patch.object(DAGIndex, 'build',
                                                side_effect=AssertionError('DAG path forbidden')):
            plan, detail = router.build(graph, 2, CONFIG)
        self.assertEqual(plan, expected)
        self.assertTrue(detail['resource_word_guard'])
        self.assertEqual(detail['selected_strategy'], 'resource_word')
        self.assertEqual(detail['word'], {'a': 10, 'b': 10, 'lookahead': 2})
        derive_multicore_plan(graph, plan)

    def test_general_dag_never_calls_word_constructor(self):
        graph = general_graph()
        expected, _ = DAGIndex(graph).build(2, bandwidth=60, cross_core_delay=500)
        with self.no_evaluation(), patch.object(Index, 'build',
                                                side_effect=AssertionError('word path forbidden')):
            plan, detail = router.build(graph, 2, CONFIG)
        self.assertEqual(plan, expected)
        self.assertFalse(detail['resource_word_guard'])
        self.assertEqual(detail['selected_strategy'], 'dag_eft')
        self.assertIn('guard_reason', detail)
        derive_multicore_plan(graph, plan)

    def test_guard_rejects_too_long_vector_or_heterogeneous_jobs(self):
        long_vector = word_graph(vector_cycles=21)
        heterogeneous = word_graph()
        heterogeneous['ops'][4]['cycles'] = 11
        for graph in (long_vector, heterogeneous):
            with self.subTest(graph=graph), self.no_evaluation():
                plan, detail = router.build(graph, 2, CONFIG)
            self.assertFalse(detail['resource_word_guard'])
            self.assertEqual(detail['selected_strategy'], 'dag_eft')
            derive_multicore_plan(graph, plan)

    def test_both_routes_are_input_order_invariant(self):
        for graph in (word_graph(), general_graph()):
            reversed_graph = copy.deepcopy(graph)
            for field in ('ops', 'tensors', 'edges'):
                reversed_graph[field].reverse()
            with self.subTest(graph=graph), self.no_evaluation():
                self.assertEqual(router.build(graph, 4, CONFIG), router.build(reversed_graph, 4, CONFIG))

    def run_cli(self, graph, *, existing_output=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            graph_path, output, evidence = root / 'input.json', root / 'plan.json', root / 'evidence'
            graph_path.write_text(json.dumps(graph))
            if existing_output:
                output.write_bytes(b'preserve previous bytes\n')
            argv = ['direct_solve', str(graph_path), '--cores', '2', '--output', str(output),
                    '--evidence', str(evidence), '--wall', '240']
            with self.no_evaluation(), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                if existing_output:
                    with self.assertRaises(SystemExit) as error:
                        router.main()
                    self.assertEqual(error.exception.code, 1)
                else:
                    router.main()
            ledger = json.loads((evidence / 'solver.json').read_text())
            return output.read_bytes(), ledger, (evidence / 'structural_router/plan.json').read_bytes()

    def test_cli_both_routes_writes_exact_two_field_plan_and_zero_calls(self):
        for graph, route in ((word_graph(), 'resource_word'), (general_graph(), 'dag_eft')):
            with self.subTest(route=route):
                raw, ledger, candidate = self.run_cli(graph)
                self.assertEqual(raw, candidate)
                self.assertEqual(set(json.loads(raw)), {'node_to_subgraph', 'core_schedules'})
                self.assertEqual(ledger['status'], 'ok')
                self.assertEqual(ledger['calls'], {'E0': 0, 'E1': 0, 'E2': 0})
                self.assertEqual(ledger['plan_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(ledger['attempts'][0]['detail']['selected_strategy'], route)
                derive_multicore_plan(graph, json.loads(raw))

    def test_cli_preserves_existing_output_and_records_failure(self):
        raw, ledger, _ = self.run_cli(general_graph(), existing_output=True)
        self.assertEqual(raw, b'preserve previous bytes\n')
        self.assertEqual(ledger['status'], 'failed')
        self.assertIn('FileExistsError', ledger['error'])
        self.assertEqual(ledger['calls'], {'E0': 0, 'E1': 0, 'E2': 0})


if __name__ == '__main__':
    unittest.main()
