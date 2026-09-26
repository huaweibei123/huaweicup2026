import unittest
from src.q3_yuanzhifang.construct import SharingIndex


def graph():
    # Four independent one-op jobs; jobs 0/2 and 1/3 share inputs.
    return {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 10}
                    for u in (1, 2, 3, 4)],
            'tensors': [{'id': t, 'pos': 'UB', 'size': 1024} for t in (10, 11)],
            'edges': [{'source': 10, 'target': 1}, {'source': 11, 'target': 2},
                      {'source': 10, 'target': 3}, {'source': 11, 'target': 4}]}


class ConstructorTest(unittest.TestCase):
    def test_packing_load_and_coverage(self):
        index = SharingIndex(graph())
        groups, fallback = index.shared_assignment(2)
        self.assertFalse(fallback)
        self.assertEqual(sorted(sum(groups, [])), list(range(4)))
        self.assertEqual([len(g) for g in groups], [2, 2])
        self.assertEqual(index.ingress_bytes(groups), 2048)

    def test_plan_covers_all_ops_once(self):
        index = SharingIndex(graph())
        for variant in ('baseline', 'shared_order', 'shared_place'):
            plan, _ = index.build_variant(2, variant)
            self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
            self.assertEqual(sorted(sum(plan['core_schedules'], [])), list(range(4)))


if __name__ == '__main__':
    unittest.main()
