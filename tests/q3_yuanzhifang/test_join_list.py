import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.dag_list import build as myopic_build
from src.q3_yuanzhifang.join_list import build


def diamond(long_work):
    return {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': w}
                    for u, w in [(1, 1), (2, long_work), (3, 100), (4, 1)]],
            'tensors': [],
            'edges': [{'source': u, 'target': v} for u, v in [(1, 2), (1, 3), (2, 4), (3, 4)]]}


class JoinTest(unittest.TestCase):
    def test_short_branch_prices_return_trip_before_splitting(self):
        x = SharingIndex(diamond(1000))
        _, old = myopic_build(x, 2, 60, 500)
        plan, meta = build(x, 2, 60, 500)
        self.assertEqual(old['modeled_compute_finish'], 1106)
        self.assertEqual(meta['modeled_compute_finish'], 1102)
        self.assertEqual(meta['paired_joins'], 1)
        self.assertEqual(sum(bool(s) for s in plan['core_schedules']), 1)

    def test_early_small_branch_can_hide_copy_behind_long_branch(self):
        plan, meta = build(SharingIndex(diamond(10000)), 2, 60, 500)
        self.assertEqual(meta['modeled_compute_finish'], 10002)
        self.assertEqual(sum(bool(s) for s in plan['core_schedules']), 2)


if __name__ == '__main__':
    unittest.main()
