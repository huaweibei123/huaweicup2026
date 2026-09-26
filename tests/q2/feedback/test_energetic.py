import random
import unittest

from src.q2.feedback.energetic import pipe_bound


def exhaustive(jobs, cores):
    return max((r + q + (sum(w for a, b, w in jobs if a >= r and b >= q) + cores - 1)//cores
                for r in {x[0] for x in jobs} for q in {x[1] for x in jobs}
                if any(a >= r and b >= q for a, b, _ in jobs)), default=0)


class EnergeticTests(unittest.TestCase):
    def test_matches_every_nonempty_threshold_subset(self):
        rng = random.Random(20260925)
        for n in range(1, 15):
            for _ in range(8):
                jobs = [(rng.randrange(20), rng.randrange(20), rng.randrange(1, 31)) for _ in range(n)]
                for k in (1, 2, 3, 5):
                    self.assertEqual(pipe_bound(jobs, k)['lower_bound_cycles'], exhaustive(jobs, k))

    def test_empty_high_tail_threshold_does_not_create_a_false_bound(self):
        # (r=100,q=100) has no jobs and must not produce 200.
        jobs = [(100, 0, 1), (0, 100, 1)]
        self.assertEqual(pipe_bound(jobs, 1)['lower_bound_cycles'], 101)

    def test_strictly_strengthens_total_pipe_work(self):
        result = pipe_bound([(20, 30, 10)] * 8, 4)
        self.assertEqual(result, {'lower_bound_cycles': 70, 'release': 20, 'tail': 30, 'work': 80, 'jobs': 8})

    def test_empty_pipe(self):
        self.assertEqual(pipe_bound([], 2)['lower_bound_cycles'], 0)


if __name__ == '__main__':
    unittest.main()
