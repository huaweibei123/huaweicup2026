"""Small mathematical checks; no official evaluator calls."""
import unittest

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure
from src.q2_nikolastarx.shared_input_wave import _recognize
from src.q2_nikolastarx.template_capacity_pipeline import _segment_bounds, build
from tests.q2_nikolastarx.test_template_stage_pipeline import repeated_jobs


class TemplateCapacityPipelineTests(unittest.TestCase):
    def test_every_segment_bound_matches_independent_interval_oracle(self):
        graph = repeated_jobs(3)
        index = DAGIndex(graph)
        _, shared, _ = _recognize(index)
        ops = index.components[0]
        bounds = _segment_bounds(index, ops, set(shared))
        for a in range(len(ops)):
            for b in range(a + 1, len(ops) + 1):
                private = {'L1': [0] * (b - a), 'UB': [0] * (b - a)}
                shared_bytes = {'L1': 0, 'UB': 0}
                touched = {}
                for q in range(a, b):
                    for tid in set(index.inputs[ops[q]]) | set(index.outputs[ops[q]]):
                        touched.setdefault(tid, []).append(q - a)
                for tid, steps in touched.items():
                    tensor = index.tensors[tid]
                    pool = 'UB' if tensor['pos'] == 'DDR' else tensor['pos']
                    if tid in shared:
                        shared_bytes[pool] += tensor['size']
                    else:
                        for q in range(min(steps), max(steps) + 1):
                            private[pool][q] += tensor['size']
                expected = {p: shared_bytes[p] + max(private[p]) for p in private}
                self.assertEqual(bounds[a][b], expected)

    def test_three_jobs_exact_and_infeasible_fails_closed(self):
        graph = repeated_jobs(3)
        plan, diag = build(graph, 2, {'capacity': {'L1': 100, 'UB': 0}})
        self.assertEqual(len(plan['core_schedules']), 2)
        actual = diag['zero_spill_diagnostic']['peaks']
        self.assertEqual(actual, diag['segment_upper_bounds_bytes'])
        self.assertTrue(diag['zero_spill_diagnostic']['zero_spill_certificate'])
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, {'capacity': {'L1': 1, 'UB': 0}})


if __name__ == '__main__':
    unittest.main()
