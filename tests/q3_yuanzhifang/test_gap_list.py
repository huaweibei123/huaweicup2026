import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.gap_list import build


class GapListTest(unittest.TestCase):
    def test_late_released_branch_keeps_space_for_independent_work(self):
        graph = {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': w}
                         for u, w in [(1, 1), (2, 10000), (3, 100), (4, 1), (5, 50)]],
                 'tensors': [], 'edges': [{'source': u, 'target': v}
                 for u, v in [(1, 2), (1, 3), (2, 4), (3, 4)]]}
        plan, meta = build(SharingIndex(graph), 2, 60, 500)
        short, independent = (plan['node_to_subgraph'][str(u)] for u in (3, 5))
        core = next(seq for seq in plan['core_schedules'] if short in seq)
        self.assertLess(core.index(independent), core.index(short))
        self.assertEqual(meta['operations_inserted_before_tail'], 1)
        self.assertEqual(meta['modeled_compute_finish'], 10002)
        self.assertEqual(meta['paired_joins'], 1)
        self.assertEqual(sorted(s for seq in plan['core_schedules'] for s in seq),
                         sorted(plan['node_to_subgraph'].values()))


if __name__ == '__main__':
    unittest.main()
