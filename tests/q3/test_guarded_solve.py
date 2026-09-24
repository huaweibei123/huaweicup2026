"""Selection safety and budget accounting with injected scores, not official runs."""
import unittest
from unittest.mock import patch

from src.q3.construct import Index
from src.q3.guarded_solve import evaluate_candidates
from src.q3.pipe_bound import UnsupportedBound
from tests.q3.test_reduction_tree import graph


class GuardedTests(unittest.TestCase):
    def run_policy(self, scores, lower):
        seq = iter(scores)
        saved = []
        def evaluate(plan):
            x = next(seq)
            if isinstance(x, Exception):
                raise x
            return {"makespan": x}
        bound = {"with_cross_core_delay": {"lower_bound_cycles": lower}}
        with patch("src.q3.guarded_solve.analyze", return_value=bound), \
             patch("src.q3.guarded_solve.release", return_value=({"candidate": 1}, {"strategy": "release_place_forest"})):
            out = evaluate_candidates(Index(graph()), 2, evaluate, lambda name, *args: saved.append(name))
        return out, saved

    def test_large_or_equal_lower_bound_saves_one_call(self):
        for lower in (100, 101):
            (winner, calls, rec, _), saved = self.run_policy([100], lower)
            self.assertEqual(calls, 1)
            self.assertEqual(winner[1]["makespan"], 100)
            self.assertEqual(rec[-1]["status"], "bound_pruned")
            self.assertEqual(saved, ["seed"])

    def test_small_lower_bound_never_accepts_without_e0(self):
        for value, expected in ((90, 90), (100, 100), (130, 100)):
            (winner, calls, rec, _), saved = self.run_policy([100, value], 80)
            self.assertEqual(calls, 2)
            self.assertEqual(winner[1]["makespan"], expected)
            self.assertEqual(rec[-1]["makespan"], value)
            self.assertEqual(saved, ["seed", "release"])

    def test_official_rejection_keeps_anchor_and_charges_attempt(self):
        from evaluation_validation import EvaluationValidationError
        (winner, calls, rec, _), _ = self.run_policy([100, EvaluationValidationError("capacity")], 80)
        self.assertEqual(calls, 2)
        self.assertEqual(winner[1]["makespan"], 100)
        self.assertEqual(rec[-1]["status"], "rejected")

    def test_unproved_bound_does_not_eliminate_candidate(self):
        scores = iter([100, 90])
        with patch("src.q3.guarded_solve.analyze", side_effect=UnsupportedBound("copy bridge")), \
             patch("src.q3.guarded_solve.release", return_value=({"candidate": 1}, {"strategy": "release_place_forest"})):
            winner, calls, rec, _ = evaluate_candidates(Index(graph()), 2,
                lambda plan: {"makespan": next(scores)}, lambda *args: None)
        self.assertEqual(calls, 2)
        self.assertEqual(winner[1]["makespan"], 90)
        self.assertIn("bound_unavailable", rec[-1])

    def test_uncut_forest_preserves_overlap_policy(self):
        g = {"ops": [], "tensors": [], "edges": []}
        for j in range(20):
            for u in range(3):
                g["ops"].append({"id": 3*j+u, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": 1})
            g["edges"].extend({"source": 3*j+u, "target": 3*j+2} for u in (0, 1))
        scores = []
        out = evaluate_candidates(Index(g), 4, lambda p:scores.append(p) or {"makespan": 100}, lambda *a:None)
        self.assertEqual(len(scores), 1)
        self.assertEqual(out[2][-1]["status"], "unsupported")
        self.assertIn("uncut", out[2][-1]["reason"])


if __name__ == "__main__":
    unittest.main()
