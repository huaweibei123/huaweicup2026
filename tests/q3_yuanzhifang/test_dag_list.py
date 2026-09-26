import unittest
from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.dag_list import build


class DagListTest(unittest.TestCase):
    def graph(self, branch_cycles):
        return {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M',
                         'cycles': branch_cycles if u in (2, 3) else 10}
                        for u in range(1, 5)], 'tensors': [],
                'edges': [{'source': a, 'target': b}
                          for a, b in ((1, 2), (1, 3), (2, 4), (3, 4))]}

    def test_long_parallel_branches_can_pay_communication(self):
        plan, meta = build(SharingIndex(self.graph(10000)), 2, 60, 500)
        self.assertTrue(meta['guard'])
        self.assertTrue(all(plan['core_schedules']))
        inv = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
        owner = {inv[sg]: c for c, seq in enumerate(plan['core_schedules']) for sg in seq}
        self.assertNotEqual(owner[2], owner[3])

    def test_short_branches_remain_local_when_transfer_dominates(self):
        plan, meta = build(SharingIndex(self.graph(10)), 2, 60, 500)
        self.assertEqual(meta['cross_chain_edges'], 0)
        self.assertEqual(sum(bool(seq) for seq in plan['core_schedules']), 1)


if __name__ == '__main__':
    unittest.main()
