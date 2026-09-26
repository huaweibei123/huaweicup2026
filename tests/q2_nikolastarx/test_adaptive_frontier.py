"""Routing boundaries and legal plans; no evaluation or stored case lookup."""
from unittest import TestCase
from unittest.mock import patch
from src.q2_nikolastarx import adaptive_frontier, adaptive_budget, component_envelope
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import derive_multicore_plan
from tests.q2_nikolastarx.test_component_envelope import jobs, config


class FrontierTests(TestCase):
    def test_budget_route_does_not_infer_split_benefit_from_work_alone(self):
        graph = jobs(6)
        graph['ops'][0]['cycles'] = 10000
        index = DAGIndex(graph)
        old, _ = component_envelope.build_from_index(index, 2, config())
        plan, detail = adaptive_budget.component_route(index, 2, config())
        self.assertEqual(plan, old)
        self.assertTrue(detail['component_pressure']['component_exceeds_balanced_pipe_work'])
        self.assertIn('component_split_deferred', detail['component_pressure'])

    def test_balanced_components_keep_existing_plan(self):
        graph = jobs(6)
        index = DAGIndex(graph)
        old, _ = component_envelope.build_from_index(index, 2, config())
        new, detail = adaptive_frontier.component_route(index, 2, config())
        self.assertEqual(old, new)
        self.assertFalse(detail['component_pressure']['component_exceeds_balanced_pipe_work'])

    def test_indivisible_fork_component_triggers_dag_and_keeps_every_op(self):
        graph = jobs(6)
        graph['ops'].append({'id': 50, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 1})
        graph['tensors'].append({'id': 2000, 'pos': 'UB', 'size': 2})
        graph['edges'].extend({'source': 1002+2*j, 'target': 50} for j in range(4))
        graph['edges'].append({'source': 50, 'target': 2000})
        index = DAGIndex(graph)
        self.assertEqual(len(index.components), 3)
        with patch('multicore_cut_evaluate_problem_2.evaluate_scene_b',
                   side_effect=AssertionError('no scoring')):
            plan, detail = adaptive_frontier.component_route(index, 2, config())
        self.assertEqual(detail['selected_strategy'], 'dominant_component_dag')
        self.assertEqual(set(map(int, plan['node_to_subgraph'])), set(index.ops))
        derive_multicore_plan(graph, plan)
        self.assertEqual(len({s for row in plan['core_schedules'] for s in row}),len(index.ops))

    def test_single_core_never_requests_indivisibility_repair(self):
        graph = jobs(3)
        graph['ops'][0]['cycles'] = 10000
        index = DAGIndex(graph)
        pressure = adaptive_frontier.component_pressure(index, 1, config()['capacity'])
        self.assertFalse(pressure['component_exceeds_balanced_pipe_work'])
