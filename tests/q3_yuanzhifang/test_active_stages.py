import unittest
from src.q3_yuanzhifang.active_stages import build
from src.q3_yuanzhifang.construct import SharingIndex


def chains(cycles):
    return {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': cycles}
                    for u in (1, 2, 3, 4)],
            'tensors': [{'id': 10, 'pos': 'L1', 'size': 1024}],
            'edges': [{'source': 10, 'target': 1}, {'source': 10, 'target': 3},
                      {'source': 1, 'target': 2}, {'source': 3, 'target': 4}]}


class ActiveStagesTest(unittest.TestCase):
    def test_bandwidth_dominated_keeps_requested_empty_cores(self):
        plan, meta = build(SharingIndex(chains(10)), 4, 1)
        self.assertEqual(meta['active_cores'], 1)
        self.assertEqual(len(plan['core_schedules']), 4)
        self.assertEqual(plan['core_schedules'][1:], [[], [], []])
        self.assertEqual(sorted(sum(plan['core_schedules'], [])), [0, 1, 2, 3])

    def test_compute_dominated_uses_parallel_resources(self):
        _, meta = build(SharingIndex(chains(10000)), 2, 60)
        self.assertEqual(meta['active_cores'], 2)


if __name__ == '__main__':
    unittest.main()
