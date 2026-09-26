import unittest

from src.q3_yuanzhifang.construct import SharingIndex, derive_multicore_plan
from src.q3_yuanzhifang.pipeline_coalesced import build
from src.q3_yuanzhifang.pipeline_stages import build as pipeline_build
from multicore_cut_evaluate_problem_2 import _prioritize_task_seq


def two_jobs():
    return {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 10}
                    for u in range(1, 9)],
            'tensors': [{'id': 20, 'pos': 'L1', 'size': 60}],
            'edges': [{'source': u, 'target': u+1} for u in (1, 2, 3, 5, 6, 7)] +
                     [{'source': 20, 'target': u} for u in (1, 5)]}


class CoalescedPipelineTest(unittest.TestCase):
    def test_forward_stage_quotient_and_same_core_ownership(self):
        graph = two_jobs()
        plan, meta = build(SharingIndex(graph), 2, 60)
        view = derive_multicore_plan(graph, plan)
        self.assertEqual(plan['node_to_subgraph'],
                         {'1': 0, '2': 0, '5': 0, '6': 0, '3': 1, '4': 1, '7': 1, '8': 1})
        self.assertEqual(plan['core_schedules'], [[0], [1]])
        self.assertEqual(view['subgraph_succs'], {0: {1}, 1: set()})
        self.assertEqual(meta['cuts'], [0, 2, 4])

    def test_outside_homogeneous_guard_retains_original_fallback(self):
        graph = two_jobs()
        graph['ops'][-1]['cycles'] = 11
        expected, _ = pipeline_build(SharingIndex(graph), 2, 60)
        actual, meta = build(SharingIndex(graph), 2, 60)
        self.assertFalse(meta['guard'])
        self.assertEqual(actual, expected)

    def test_official_bucket_semantics_can_expose_independent_prefetch(self):
        # This is one valid Step1 word, not a claim that Step1 always selects it.
        graph = {'ops': [{'id': u} for u in (1, 2, 101, 102)],
                 'tensors': [],
                 'edges': [{'source': 101, 'target': 1}, {'source': 102, 'target': 2},
                           {'source': 1, 'target': 2}]}
        raw = [102, 101, 1, 2]
        split = _prioritize_task_seq(graph, raw, {101: 0, 1: 0, 102: 1, 2: 1}, [0, 1])
        merged = _prioritize_task_seq(graph, raw, {u: 0 for u in raw}, [0])
        self.assertEqual(split, [101, 1, 102, 2])
        self.assertEqual(merged, raw)


if __name__ == '__main__':
    unittest.main()
