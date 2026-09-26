import random
import unittest

from src.q3_yuanzhifang.gap_calendar import empty, earliest, reserve


class GapCalendarTest(unittest.TestCase):
    def test_reserved_future_work_leaves_earlier_gap_and_versions_independent(self):
        original = empty()
        future = reserve(original, 1000, 100)
        self.assertEqual(earliest(future, 0, 80), 0)
        self.assertEqual(earliest(future, 950, 80), 1100)
        filled = reserve(future, 0, 80)
        self.assertEqual(earliest(filled, 0, 30), 80)
        self.assertEqual(earliest(future, 0, 30), 0)
        self.assertEqual(earliest(original, 1000, 80), 1000)
        with self.assertRaises(ValueError):
            reserve(future, 990, 20)

    def test_earliest_fit_against_independent_integer_time_oracle(self):
        rng = random.Random(39071)
        root, busy = empty(), []

        def invariants(node):
            if node is None:
                return 0, 0
            left_h, left_max = invariants(node.left)
            right_h, right_max = invariants(node.right)
            self.assertLessEqual(abs(left_h - right_h), 1)
            self.assertEqual(node.height, 1 + max(left_h, right_h))
            self.assertEqual(node.maximum, max(node.stop-node.key, left_max, right_max))
            return node.height, node.maximum

        for _ in range(180):
            release, duration = rng.randrange(0, 700), rng.randrange(1, 25)
            expected = release
            while any(expected < end and expected + duration > start for start, end in busy):
                expected += 1
            actual = earliest(root, release, duration)
            self.assertEqual(actual, expected)
            root = reserve(root, actual, duration)
            busy.append((actual, actual + duration))
            invariants(root)


if __name__ == '__main__':
    unittest.main()
