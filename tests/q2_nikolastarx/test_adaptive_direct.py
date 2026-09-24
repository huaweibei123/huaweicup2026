"""Pure structure routing tests with evaluator/process calls forbidden."""
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_direct as adaptive
from src.q2_nikolastarx import component_envelope
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import Index, derive_multicore_plan
from tests.q2_nikolastarx.test_direct_solve import word_graph, general_graph, CONFIG
from tests.q2_nikolastarx.test_component_envelope import jobs


class AdaptiveDirectTests(unittest.TestCase):
    def forbidden_evaluation(self):
        context = ExitStack()
        for name in ['subprocess.Popen', 'multicore_cut_evaluate_problem_2.evaluate_scene_b',
                     'multicore_cut_evaluate_problem_2._build_scene_b_tasks']:
            context.enter_context(patch(name, side_effect=AssertionError('No scoring/compilation')))
        return context

    def test_word_route_precedes_component_count_and_never_reindexes(self):
        graph = word_graph(1)
        expected = Index(graph).build(5, 'resource_word')[0]
        with self.forbidden_evaluation(), patch.object(adaptive, 'DAGIndex', wraps=DAGIndex) as index, \
                patch.object(adaptive, 'build_from_index', side_effect=AssertionError('wrong route')):
            plan, detail = adaptive.build(graph, 5, CONFIG)
        self.assertEqual(plan, expected)
        self.assertEqual(detail['adaptive_route'], 'resource_word')
        self.assertEqual(index.call_count, 1)

    def test_component_route_reuses_initial_index_and_matches_standalone(self):
        graph = jobs(6)
        expected = component_envelope.build(graph, 2, CONFIG)[0]
        with self.forbidden_evaluation(), patch.object(adaptive, 'DAGIndex', wraps=DAGIndex) as index, \
                patch.object(component_envelope, 'DAGIndex', side_effect=AssertionError('duplicate index')):
            plan, detail = adaptive.build(graph, 2, CONFIG)
        self.assertEqual(plan, expected)
        self.assertEqual(detail['adaptive_route'], 'component_envelope')
        self.assertEqual(index.call_count, 1)
        self.assertFalse(detail['zero_spill_claim'])

    def test_single_component_general_route_keeps_known_dag_behavior(self):
        graph = general_graph()
        expected = DAGIndex(graph).build(2, bandwidth=60, cross_core_delay=500)[0]
        with self.forbidden_evaluation(), patch.object(adaptive, 'DAGIndex', wraps=DAGIndex) as index, \
                patch.object(adaptive, 'build_from_index', side_effect=AssertionError('wrong route')):
            plan, detail = adaptive.build(graph, 2, CONFIG)
        self.assertEqual(plan, expected)
        self.assertEqual(detail['adaptive_route'], 'dag_eft')
        self.assertEqual(index.call_count, 1)

    def test_components_equal_cores_boundary_and_bad_cores(self):
        graph = jobs(2)
        self.assertEqual(adaptive.build(graph, 2, CONFIG)[1]['adaptive_route'], 'component_envelope')
        self.assertEqual(adaptive.build(graph, 3, CONFIG)[1]['adaptive_route'], 'dag_eft')
        for cores in [True, 0, -1, 1.5]:
            with self.assertRaises(ValueError): adaptive.build(graph, cores, CONFIG)

    def test_cli_all_routes_zero_calls_hash_and_no_overwrite(self):
        for graph, route in [(word_graph(), 'resource_word'), (jobs(), 'component_envelope'),
                             (general_graph(), 'dag_eft')]:
            with self.subTest(route=route), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); graph_path=root/'graph.json'; output=root/'plan.json'
                graph_path.write_text(json.dumps(graph))
                argv=['adaptive_direct',str(graph_path),'--cores','2','--output',str(output),
                      '--evidence',str(root/'evidence')]
                with self.forbidden_evaluation(), patch.object(sys,'argv',argv), redirect_stdout(io.StringIO()):
                    adaptive.main()
                ledger=json.loads((root/'evidence/solver.json').read_text()); raw=output.read_bytes()
                self.assertEqual(ledger['status'],'ok')
                self.assertEqual(ledger['calls'],{'E0':0,'E1':0,'E2':0})
                self.assertEqual(ledger['selected'],'adaptive_direct')
                self.assertEqual(ledger['plan_sha256'],hashlib.sha256(raw).hexdigest())
                self.assertEqual(ledger['attempts'][0]['name'],'adaptive_direct')
                self.assertEqual(ledger['attempts'][0]['detail']['adaptive_route'],route)
                derive_multicore_plan(graph,json.loads(raw))
                argv[-1]=str(root/'second')
                with self.forbidden_evaluation(), patch.object(sys,'argv',argv), redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as error: adaptive.main()
                self.assertEqual(error.exception.code,1)
                self.assertEqual(output.read_bytes(),raw)


if __name__ == '__main__': unittest.main()
