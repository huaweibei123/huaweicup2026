import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.release_order import reorder


class ReleaseOrderTest(unittest.TestCase):
    def test_move_independent_other_pipe_ahead_of_remote_wait(self):
        g = {'ops': [{'id': i, 'op': 'MUL', 'pipe': p, 'cycles': w}
                     for i,p,w in [(1,'PIPE_M',1000),(2,'PIPE_V',10),(3,'PIPE_M',10),(4,'PIPE_V',10)]],
             'tensors': [], 'edges': [{'source':1,'target':2},{'source':3,'target':4}]}
        plan = dict(node_to_subgraph={str(i):i for i in range(1,5)}, core_schedules=[[1],[2,3,4]])
        changed, meta = reorder(SharingIndex(g), plan, 500)
        self.assertEqual(changed['core_schedules'], [[1],[3,2,4]])
        self.assertEqual(meta['fixed_computation_delay_bound'], 1520)
        self.assertTrue(meta['computation_fifo_preserved'])

    def test_same_pipe_order_cannot_be_freely_relaxed(self):
        g = {'ops': [{'id': i, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': w}
                     for i,w in [(1,1000),(2,10),(3,10)]],
             'tensors': [], 'edges': [{'source':1,'target':2}]}
        plan = dict(node_to_subgraph={str(i):i for i in range(1,4)}, core_schedules=[[1],[2,3]])
        changed, meta = reorder(SharingIndex(g), plan, 500)
        self.assertEqual(changed, plan)
        self.assertEqual(meta['changed_priority_positions'], 0)


if __name__ == '__main__':
    unittest.main()
