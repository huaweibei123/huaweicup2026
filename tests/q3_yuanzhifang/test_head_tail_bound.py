import unittest

from src.q3_yuanzhifang.head_tail_bound import analyze, energy_bound


class HeadTailTest(unittest.TestCase):
    def test_all_threshold_pairs_independent_oracle(self):
        points = [(0, 4, 7), (0, 2, 3), (2, 1, 13), (9, 0, 2), (5, 7, 8)]
        for k in range(1, 6):
            expected = max(a+b+(sum(selected)+k-1)//k
                           for a in {h for h, _, _ in points}
                           for b in {t for _, t, _ in points}
                           for selected in [[w for h, t, w in points if h >= a and t >= b]]
                           if selected)
            actual = energy_bound(points, k)
            self.assertEqual(actual['bound'], expected)
            self.assertGreater(actual['operations'], 0)

    def test_binary_tree_tail_closes_plain_workload_gap(self):
        graph = {'ops': [{'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 1}
                         for i in range(1, 16)], 'tensors': [],
                 'edges': [{'source': i, 'target': i//2} for i in range(2, 16)]}
        row = analyze(graph, 60, [4])[0]
        # Plain ceil(15/4)=4 is too weak; leaves need two slots then three ancestors.
        self.assertEqual(row['lower_bound_cycles'], 5)
        witness = row['by_pipe']['PIPE_V']
        # Several threshold sets attain 5; a particular tie is not the theorem.
        self.assertEqual(witness['head'] + witness['tail'] +
                         (witness['work']+3)//4, 5)


if __name__ == '__main__':
    unittest.main()
