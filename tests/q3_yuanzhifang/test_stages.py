import unittest
from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.stages import aligned_plan


def two_chains():
    return {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 10}
                    for u in (1, 2, 3, 4)],
            'tensors': [{'id': 10, 'pos': 'L1', 'size': 1024}],
            'edges': [{'source': 10, 'target': 1}, {'source': 10, 'target': 3},
                      {'source': 1, 'target': 2}, {'source': 3, 'target': 4}]}


class StageTest(unittest.TestCase):
    def test_shared_input_layer_retains_dependencies(self):
        x = SharingIndex(two_chains())
        plan, meta = aligned_plan(x, 1)
        self.assertTrue(meta['guard'])
        inv = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
        self.assertEqual([inv[sg] for sg in plan['core_schedules'][0]], [1, 3, 2, 4])

    def test_misaligned_input_use_declines(self):
        g = two_chains()
        g['edges'][1]['target'] = 4
        plan, meta = aligned_plan(SharingIndex(g), 1)
        self.assertIsNone(plan)
        self.assertFalse(meta['guard'])


if __name__ == '__main__':
    unittest.main()
