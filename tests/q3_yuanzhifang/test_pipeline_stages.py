import itertools
import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.pipeline_stages import build, partition


class PipelineTest(unittest.TestCase):
    def test_dp_matches_exhaustive_small_partition_oracle(self):
        # Independent finite oracle, not an evaluation-time candidate search.
        weights = [7, 2, 11, 3, 5, 1]
        for stages in range(1, 5):
            expected = min(max(sum(weights[a:b]) for a, b in zip(cuts, cuts[1:]))
                           for inside in itertools.combinations(range(1, len(weights)), stages-1)
                           for cuts in [[0, *inside, len(weights)]])
            cuts, value = partition(weights, stages)
            self.assertEqual(value, expected)
            self.assertEqual(len(cuts), stages+1)

    def test_every_job_moves_forward_through_disjoint_stages(self):
        graph = {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 10}
                         for u in range(1, 9)],
                 'tensors': [{'id': 20, 'pos': 'L1', 'size': 60}],
                 'edges': [{'source': u, 'target': u+1} for u in (1, 2, 3, 5, 6, 7)] +
                          [{'source': 20, 'target': u} for u in (1, 5)]}
        plan, meta = build(SharingIndex(graph), 2, 60)
        inverse = {s: int(u) for u, s in plan['node_to_subgraph'].items()}
        actual = [[inverse[s] for s in seq] for seq in plan['core_schedules']]
        self.assertEqual(actual, [[1, 2, 5, 6], [3, 4, 7, 8]])
        self.assertEqual(meta['ideal_flowshop_cycles'], 60)


if __name__ == '__main__':
    unittest.main()
