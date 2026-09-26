import itertools
import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.tail_fifo_bound import analyze, longest_path


def three_jobs():
    ops, tensors, edges = [], [{"id": 1000, "pos": "L1", "size": 50}], []
    for j in range(3):
        a = 1 + 3*j
        ops.extend(({"id": a, "op": "MUL", "pipe": "PIPE_M", "cycles": 10},
                    {"id": a+1, "op": "ADD", "pipe": "PIPE_V", "cycles": 10},
                    {"id": a+2, "op": "MUL", "pipe": "PIPE_M", "cycles": 10}))
        edges.extend(({"source": a, "target": a+1},
                      {"source": a+1, "target": a+2},
                      {"source": 1000, "target": a+2}))
        tid = 2000+j
        tensors.append({"id": tid, "pos": "L1", "size": 10})
        edges.extend(({"source": a, "target": tid}, {"source": tid, "target": a+2}))
    return {"ops": ops, "tensors": tensors, "edges": edges}


class TailFifoBoundTest(unittest.TestCase):
    def test_fixed_tail_fifo_bound_exceeds_workload_peak_without_transfer_lag(self):
        result = analyze(SharingIndex(three_jobs()), 2, {"L1": 70, "UB": 0})
        self.assertEqual(result["workload_peak_cycles"], 30)
        self.assertEqual(result["lower_bound_cycles"], 40)
        self.assertEqual(result["wave_sizes"], [1])
        self.assertEqual(result["bmax"], 2)
        self.assertEqual(result["cuts"][0::2], [0, 3])
        self.assertEqual(result["edge_counts"]["cross_core_original"], 2)
        self.assertTrue(any("fifo" in e["kinds"] for e in result["path_edges"]))

    def test_integer_zero_lag_feasible_starts_obey_path_bound(self):
        ops = {u: {"pipe": "PIPE_M", "cycles": 2} for u in (1, 2, 3)}
        result = longest_path(ops, {1: {3}, 2: set(), 3: set()}, [[1, 2], [3]])
        self.assertEqual(result["lower_bound_cycles"], 4)
        feasible = []
        for starts in itertools.product(range(6), repeat=3):
            a, b, c = starts
            if b >= a+2 and c >= a+2:
                feasible.append(max(a+2, b+2, c+2))
        self.assertTrue(feasible)
        self.assertEqual(min(feasible), result["lower_bound_cycles"])
        self.assertTrue(all(t >= result["lower_bound_cycles"] for t in feasible))


if __name__ == "__main__":
    unittest.main()
