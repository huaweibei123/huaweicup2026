import unittest
from fractions import Fraction

from src.q1.capacity_split_cores import construct, author
from tests.q1.test_capacity_return import chains


class SplitCoreTests(unittest.TestCase):
    def test_valid_capacity_bounded_plan(self):
        graph = chains(19)
        plan, info = construct(graph, 5, {'L1': 1024, 'UB': 160})
        self.assertEqual(len(plan['core_schedules']), 5)
        self.assertEqual(info['whole_cores'] + info['cut_cores'], 5)
        self.assertEqual(info['whole_chains'] + info['cut_chains'], 19)
        self.assertEqual(set(map(int, plan['node_to_subgraph'])), set(range(57)))
        author.validate_plan_structure(graph, plan)
        self.assertLessEqual(info['whole_packet'] * info['whole_bytes']['UB'], 160)
        self.assertLessEqual(info['cut_packet'] * info['mixed_bytes']['UB'], 160)
        # Batching may amortize gates but cannot divide serial chain work.
        self.assertEqual(Fraction(info['model']['whole_rate']),
                         Fraction(40) + Fraction(100, info['whole_packet']))

    def test_deterministic_and_metadata_independent(self):
        graph = chains(23)
        first = construct(graph, 4)
        self.assertEqual(first, construct(graph, 4))
        graph['case_id'] = 'not-a-routing-key'
        self.assertEqual(first, construct(graph, 4))

    def test_rejects_insufficient_capacity_and_one_core(self):
        graph = chains(3)
        with self.assertRaises(ValueError):
            construct(graph, 1)
        with self.assertRaises(author.Unsupported):
            construct(graph, 2, {'L1': 1024, 'UB': 31})


if __name__ == '__main__':
    unittest.main()
