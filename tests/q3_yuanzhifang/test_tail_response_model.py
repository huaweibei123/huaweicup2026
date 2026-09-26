import itertools
import unittest

from src.q3_yuanzhifang.tail_fifo_bound import longest_path
from src.q3_yuanzhifang.tail_response_model import analyze


def two_core_word(cycles=(10, 10, 10), pipes=("PIPE_M", "PIPE_V", "PIPE_M")):
    ops = {1+3*j+p: {"cycles": cycles[p], "pipe": pipes[p]}
           for j in range(3) for p in range(3)}
    succ = {u: set() for u in ops}
    for j in range(3):
        a = 1+3*j
        succ[a].add(a+1)
        succ[a+1].add(a+2)
    return ops, succ, [[1, 7, 2, 3], [4, 5, 8, 6, 9]], [7, 8, 9]


class TailResponseModelTest(unittest.TestCase):
    def test_skip_cross_edge_is_dominated_by_serial_tail(self):
        ops = {u: {"cycles": u % 4 + 1,
                   "pipe": "PIPE_M" if u % 2 else "PIPE_V"}
               for u in (1, 2, 3, 4, 5, 6, 100, 101, 102)}
        succ = {u: set() for u in ops}
        succ[1].add(2); succ[3].add(4); succ[5].add(6)
        succ[100].update((101, 102)); succ[101].add(102)
        schedules = [[1, 100, 2], [3, 101, 4], [5, 102, 6]]
        result = analyze(ops, succ, schedules, [100, 101, 102])
        self.assertEqual(result["cuts"], [0, 1, 2, 3])
        self.assertEqual(result["redundant_skip_edge_count"], 1)
        self.assertEqual(result["bound"], longest_path(ops, succ, schedules)["lower_bound_cycles"])

    def test_mixed_pipe_fifo_dependency_can_exceed_work_peak(self):
        ops, succ, schedules, tail = two_core_word()
        result = analyze(ops, succ, schedules, tail)
        self.assertEqual(result["cuts"], [0, 1, 3])
        self.assertGreater(result["bound"], 30)
        self.assertEqual(result["bound"], longest_path(ops, succ, schedules)["lower_bound_cycles"])
        self.assertEqual(result["arrival"][0], 0)
        self.assertEqual(result["arrival"][1],
                         max(result["coeffs"][0]["C"], result["coeffs"][0]["D"]))

    def test_small_positive_cycle_families_match_full_dag_oracle(self):
        for cycles, pipes in itertools.product(itertools.product((1, 2, 4), repeat=3),
                                                (("PIPE_M", "PIPE_V", "PIPE_M"),
                                                 ("PIPE_V", "PIPE_M", "PIPE_V"))):
            ops, succ, schedules, tail = two_core_word(cycles, pipes)
            result = analyze(ops, succ, schedules, tail)
            self.assertEqual(result["bound"], longest_path(ops, succ, schedules)["lower_bound_cycles"])

    def test_guards_reject_missing_or_non_tail_dependencies(self):
        ops, succ, schedules, tail = two_core_word()
        bad = {u: set(v) for u, v in succ.items()}
        bad[7].remove(8)
        with self.assertRaisesRegex(ValueError, "adjacent tail"):
            analyze(ops, bad, schedules, tail)
        bad = {u: set(v) for u, v in succ.items()}
        bad[1].add(4)
        with self.assertRaisesRegex(ValueError, "only forward tail"):
            analyze(ops, bad, schedules, tail)
        bad = {u: set(v) for u, v in succ.items()}
        bad[9].add(7)
        with self.assertRaisesRegex(ValueError, "only forward tail"):
            analyze(ops, bad, schedules, tail)
        with self.assertRaisesRegex(ValueError, "cover every"):
            analyze(ops, succ, [schedules[0][:-1], schedules[1]], tail)
        bad = {u: set(v) for u, v in succ.items()}
        bad[3].add(1)
        with self.assertRaisesRegex(ValueError, "local original dependency"):
            analyze(ops, bad, schedules, tail)
        with self.assertRaisesRegex(ValueError, "consecutive segments"):
            analyze(ops, succ, [[1, 7, 2, 9, 3], [4, 5, 8, 6]], tail)
        bad_ops = {u: dict(op) for u, op in ops.items()}
        bad_ops[1]["cycles"] = 0
        with self.assertRaisesRegex(ValueError, "positive integer"):
            analyze(bad_ops, succ, schedules, tail)


if __name__ == "__main__":
    unittest.main()
