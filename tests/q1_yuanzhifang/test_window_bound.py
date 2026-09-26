from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
from window_bound import lower_bound, resource_window_bound


class WindowTests(unittest.TestCase):
    def test_fast_query_matches_direct_nonempty_rectangle_enumeration(self):
        rng = random.Random(1024051)
        for n in range(1, 25):
            jobs = [(i, rng.randrange(50), rng.randrange(1, 100), rng.randrange(50)) for i in range(n)]
            for k in range(1, 6):
                expected = 0
                for a in {j[1] for j in jobs}:
                    for b in {j[3] for j in jobs}:
                        work = [d for _, r, d, q in jobs if r >= a and q >= b]
                        if work:
                            expected = max(expected, a + b + (sum(work) + k - 1) // k)
                self.assertEqual(resource_window_bound(jobs, k)["lower_bound_cycles"], expected)

    def test_empty_window_and_post_completion_tail(self):
        # Feasible at T=101: first job [10,12], second [0,1] then tail=100.
        # The empty rectangle r>=10,q>=100 must not fabricate a bound 110.
        self.assertEqual(resource_window_bound([(0, 10, 2, 0), (1, 0, 1, 100)], 2)["lower_bound_cycles"], 101)
        self.assertEqual(resource_window_bound([(0, 0, 5, 0)], 5)["lower_bound_cycles"], 1)
        self.assertEqual(resource_window_bound([], 2)["lower_bound_cycles"], 0)

    def test_window_detects_concentrated_work_beyond_load_and_cp(self):
        ops = [{"id": 0, "op": "START", "pipe": "PIPE_A", "cycles": 100}]
        ops += [{"id": i, "op": "WORK", "pipe": "PIPE_V", "cycles": 50} for i in range(1, 5)]
        ops += [{"id": 5, "op": "END", "pipe": "PIPE_B", "cycles": 100}]
        edges = [{"source": a, "target": b} for i in range(1, 5) for a, b in ((0, i), (i, 5))]
        bound = lower_bound({"ops": ops, "edges": edges, "tensors": []}, 2)
        self.assertEqual(bound["lower_bound_cycles"], 300)  # CP=250, total V/k=100.
        self.assertEqual(bound["pipe_windows"]["PIPE_V"]["witness"]["work_cycles"], 200)

    def test_distinct_pipes_and_copy_bridges_are_not_summed_as_one_path(self):
        graph = {"ops": [
            {"id": 0, "op": "COMPUTE", "pipe": "PIPE_A", "cycles": 10},
            {"id": 1, "op": "COPY_OUT", "pipe": "PIPE_OUT", "cycles": 1000},
            {"id": 2, "op": "COPY_IN", "pipe": "PIPE_IN", "cycles": 1000},
            {"id": 3, "op": "COMPUTE", "pipe": "PIPE_B", "cycles": 20}],
            "edges": [{"source": a, "target": a + 1} for a in range(3)], "tensors": []}
        # Pure resource windows do not include each job's nonpreemptive CP.
        self.assertEqual(lower_bound(graph, 1)["lower_bound_cycles"], 20)
        self.assertEqual(lower_bound(graph, 2)["lower_bound_cycles"], 10)

    def test_invalid_bounds_rejected(self):
        for job in [(0, -1, 1, 0), (0, 0, 0, 0), (0, 0, 1, -1), (0, 0, 1.0, 0)]:
            with self.assertRaises(ValueError):
                resource_window_bound([job], 2)
        for k in (0, True, 2.0):
            with self.assertRaises(ValueError):
                resource_window_bound([(0, 0, 1, 0)], k)


if __name__ == "__main__":
    unittest.main()
