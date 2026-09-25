"""Synthetic template-stage properties; no evaluator calls."""
from fractions import Fraction
from itertools import combinations
import unittest

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx.shared_input_wave import _recognize
from src.q2_nikolastarx.template_stage_pipeline import (
    build, build_job_pipeline, build_job_pipeline_from_index, _cut_template)


def repeated_jobs(jobs=3):
    graph = {'ops': [], 'tensors': [
        {'id': 100, 'pos': 'L1', 'size': 4},
        {'id': 101, 'pos': 'L1', 'size': 5}], 'edges': []}
    for job in range(jobs):
        a, b, c = (10 * job + i for i in (1, 2, 3))
        x, y, z = (200 + 10 * job + i for i in (1, 2, 3))
        graph['ops'].extend([
            {'id': a, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 10},
            {'id': b, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2},
            {'id': c, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 10}])
        graph['tensors'].extend({'id': t, 'pos': 'L1', 'size': 3}
                                for t in (x, y, z))
        graph['edges'].extend([
            {'source': 100, 'target': a}, {'source': a, 'target': x},
            {'source': x, 'target': b}, {'source': 101, 'target': b},
            {'source': b, 'target': y}, {'source': y, 'target': c},
            {'source': c, 'target': z}])
    return graph


class TemplateStagePipelineTests(unittest.TestCase):
    def test_stage_owners_shared_input_and_topology(self):
        graph = repeated_jobs(4)
        config = {'capacity': {'L1': 100, 'UB': 0}}
        plan, diag = build(graph, 2, config)
        self.assertEqual(diag['shared_inputs'], 2)
        self.assertEqual(diag['shared_input_core_count_max'], 1)
        self.assertTrue(diag['zero_spill_diagnostic']['zero_spill_certificate'])
        view = derive_multicore_plan(graph, plan)
        owner = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
        index = DAGIndex(graph)
        by_job, shared, anchor = _recognize(index)
        for sig in by_job[0]:
            self.assertEqual(len({owner[row[sig]] for row in by_job}), 1)
        for tid in shared:
            self.assertEqual(len({owner[row[anchor[tid]]] for row in by_job}), 1)
        reverse = {sg: u for u, sg in view['mapping'].items()}
        for row in plan['core_schedules']:
            positions = {reverse[sg]: i for i, sg in enumerate(row)}
            for u in positions:
                for v in index.succ[u]:
                    if v in positions:
                        self.assertLess(positions[u], positions[v])

    def test_minimax_contiguous_partition_matches_oracle(self):
        index = DAGIndex(repeated_jobs(2))
        ops = index.components[0]
        bounds, score, pipes, prefix, total = _cut_template(index, ops, 2)
        def cost(points):
            return max(Fraction(prefix[p][b] - prefix[p][a], total[p])
                       for a, b in zip(points, points[1:]) for p in pipes if total[p])
        expected = min(cost([0, cut, len(ops)]) for cut in range(1, len(ops)))
        self.assertEqual(score, expected)
        self.assertEqual(cost(bounds), expected)

    def test_tiny_capacity_is_diagnostic_not_rejection(self):
        plan, diag = build(repeated_jobs(), 2, {'capacity': {'L1': 1, 'UB': 0}})
        self.assertEqual(len(plan['core_schedules']), 2)
        self.assertTrue(diag['zero_spill_diagnostic']['supported'])
        self.assertFalse(diag['zero_spill_diagnostic']['zero_spill_certificate'])

    def test_nonhomogeneous_job_is_rejected(self):
        graph = repeated_jobs()
        graph['ops'][-1]['cycles'] += 1
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, {'capacity': {'L1': 100, 'UB': 0}})

    def test_job_major_keeps_stage_owner_and_shared_input_single_core(self):
        graph = repeated_jobs(4)
        config = {'capacity': {'L1': 100, 'UB': 0}}
        stage_plan, stage_diag = build(graph, 2, config)
        job_plan, job_diag = build_job_pipeline_from_index(DAGIndex(graph), 2, config)
        self.assertEqual(job_plan, build_job_pipeline(graph, 2, config)[0])
        self.assertEqual(stage_diag['template_bounds'], job_diag['template_bounds'])
        self.assertEqual(job_diag['priority_order'], 'job_major')
        self.assertTrue(job_diag['zero_spill_diagnostic']['supported'])
        self.assertNotEqual(stage_plan['core_schedules'], job_plan['core_schedules'])
        def owner(plan):
            view = derive_multicore_plan(graph, plan)
            return {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
        self.assertEqual(owner(stage_plan), owner(job_plan))
        index = DAGIndex(graph)
        for tid in (100, 101):
            self.assertEqual(len({owner(job_plan)[u] for u in index.ops
                                  if tid in index.inputs[u]}), 1)

    def test_job_major_capacity_failure_only_diagnostic(self):
        plan, diag = build_job_pipeline(repeated_jobs(4), 2,
                                        {'capacity': {'L1': 1, 'UB': 0}})
        self.assertEqual(len(plan['core_schedules']), 2)
        self.assertTrue(diag['zero_spill_diagnostic']['supported'])
        self.assertFalse(diag['zero_spill_diagnostic']['zero_spill_certificate'])


if __name__ == '__main__':
    unittest.main()
