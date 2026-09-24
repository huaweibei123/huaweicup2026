"""Check the discrete relaxation against exhaustive small-domain minima."""
import unittest
from src.q2_nikolastarx.active_core_wave import choose_cores


class CoreChoiceTests(unittest.TestCase):
    def test_crossing_and_plateaus_against_enumeration(self):
        for n in range(1, 20):
            for k in range(1, min(n, 6) + 1):
                for minimum in {1, k}:
                    for work in (0, 1, 17):
                        for shared in (0, 3, 109):
                            for private in (0, 71):
                                for cp in (0, 9, 150):
                                    q, info = choose_cores(n, k, work, shared, private, 7, cp, minimum)
                                    def score(a):
                                        return max(((n+a-1)//a)*work, (a*shared+private+6)//7, cp)
                                    expected = min(range(minimum, k+1), key=lambda a: (score(a), a))
                                    self.assertEqual((q, info['model_objective_cycles']), (expected, score(expected)))

    def test_compute_and_traffic_balance(self):
        self.assertEqual(choose_cores(11, 5, 6764, 930400, 22528, 60)[0], 2)
        self.assertEqual(choose_cores(31, 4, 26156, 930400, 253952, 60)[0], 4)
        self.assertEqual(choose_cores(142, 5, 26156, 930400, 1163264, 60)[0], 5)


if __name__ == '__main__':
    unittest.main()
