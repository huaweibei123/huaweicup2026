"""Independent small flow-shop recurrence and exhaustive partition oracle."""
from itertools import combinations
import unittest
from unittest.mock import patch

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure
from src.q2_nikolastarx.template_finite_job_pipeline import build
from tests.q2_nikolastarx.test_template_stage_pipeline import repeated_jobs


def brute(graph, cores, delay):
    index = DAGIndex(graph)
    ops = index.components[0]
    jobs = len(index.components)
    choices = []
    for k in range(1, min(cores, len(ops)) + 1):
        for interior in combinations(range(1, len(ops)), k - 1):
            cuts = (0,) + interior + (len(ops),)
            duration = []
            for a, b in zip(cuts, cuts[1:]):
                by_pipe = {}
                for u in ops[a:b]:
                    p = index.ops[u]['pipe']
                    by_pipe[p] = by_pipe.get(p, 0) + index.duration(u)
                duration.append(max(by_pipe.values()))
            # Independent ideal tandem recurrence: each stage is one server.
            completion = [[0] * jobs for _ in range(k)]
            for r in range(k):
                for j in range(jobs):
                    prior_job = completion[r][j - 1] if j else 0
                    prior_stage = completion[r - 1][j] + delay if r else 0
                    completion[r][j] = max(prior_job, prior_stage) + duration[r]
            formula = sum(duration) + (jobs - 1) * max(duration) + (k - 1) * delay
            assert completion[-1][-1] == formula
            choices.append((formula, k, cuts))
    return min(choices)


class FiniteJobPipelineTests(unittest.TestCase):
    def test_equal_sum_label_preserves_global_lexicographic_cut(self):
        # Four serial one-pipe stages [1,1,2,3], two jobs. An older prune
        # returned (0,2,3,4), although (0,1,3,4) has the same F=10.
        graph = {'ops': [], 'tensors': [
            {'id': 100, 'pos': 'L1', 'size': 1},
            {'id': 101, 'pos': 'L1', 'size': 1}], 'edges': []}
        for job in range(2):
            previous = None
            for q, cycles in enumerate((1, 1, 2, 3)):
                op, out = 10 * job + q + 1, 200 + 10 * job + q
                graph['ops'].append({'id': op, 'op': 'WORK',
                                     'pipe': 'PIPE_M', 'cycles': cycles})
                graph['tensors'].append({'id': out, 'pos': 'L1', 'size': 1})
                inputs = ([100] if q == 0 else [101] if q == 1 else [])
                if previous is not None:
                    inputs.append(previous)
                graph['edges'].extend({'source': tid, 'target': op}
                                      for tid in inputs)
                graph['edges'].append({'source': op, 'target': out})
                previous = out
        _, diag = build(graph, 4, {'capacity': {'L1': 100, 'UB': 0},
                                   'cross_core_copy_delay_cycles': 0})
        self.assertEqual((diag['scalar_flowshop_objective_cycles'],
                          diag['active_cores'], tuple(diag['template_bounds'])),
                         brute(graph, 4, 0))
        self.assertEqual(diag['template_bounds'], [0, 1, 3, 4])

    def test_exact_small_partition_oracle_with_unequal_pipe_cycles(self):
        graph = repeated_jobs(3)
        for op in graph['ops']:
            op['cycles'] = {'MATMUL': 30, 'RELU': 1}[op['op']]
        config = {'capacity': {'L1': 100, 'UB': 0},
                  'cross_core_copy_delay_cycles': 0}
        _, diag = build(graph, 3, config)
        expected = brute(graph, 3, 0)
        self.assertEqual((diag['scalar_flowshop_objective_cycles'],
                          diag['active_cores'], tuple(diag['template_bounds'])), expected)
        self.assertTrue(diag['zero_spill_diagnostic']['zero_spill_certificate'])

    def test_fixed_boundary_delay_can_make_fewer_cores_optimal(self):
        graph = repeated_jobs(3)
        config = {'capacity': {'L1': 100, 'UB': 0},
                  'cross_core_copy_delay_cycles': 30}
        _, diag = build(graph, 3, config)
        self.assertEqual(diag['active_cores'], 1)
        self.assertEqual((diag['scalar_flowshop_objective_cycles'],
                          diag['active_cores'], tuple(diag['template_bounds'])),
                         brute(graph, 3, 30))

    def test_capacity_and_transition_guards_fail_closed(self):
        graph = repeated_jobs(3)
        config = {'capacity': {'L1': 1, 'UB': 0},
                  'cross_core_copy_delay_cycles': 0}
        with self.assertRaises(UnsupportedStructure):
            build(graph, 3, config)
        config['capacity']['L1'] = 100
        with patch('src.q2_nikolastarx.template_finite_job_pipeline.MAX_TRANSITIONS', 0):
            with self.assertRaises(UnsupportedStructure):
                build(graph, 3, config)


if __name__ == '__main__':
    unittest.main()
