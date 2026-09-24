"""Official-comparison policy checks with injected evaluation; zero E0."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.q3 import calendar_solve as solver
from evaluation_validation import EvaluationValidationError


ANCHOR = {"node_to_subgraph": {"7": 0, "14": 1}, "core_schedules": [[0, 1], []]}
PROPOSAL = {"node_to_subgraph": {"7": 0, "14": 1}, "core_schedules": [[0], [1]]}


def anchor_policy(index, cores, evaluate, save):
    result = evaluate(ANCHOR)
    return ((ANCHOR, result, "attention_rows_ffn"), 1,
            [{"name": "seed", "status": "ok", "makespan": result["makespan"]}],
            {"router": {"route": "attention", "attention_cross_delay_cycles": 500,
                        "evaluation_calls": 1}})


class CalendarPolicyTests(unittest.TestCase):
    def run_policy(self, result, *, proposal=PROPOSAL, lower=0):
        evaluator = Mock(side_effect=[{"makespan": 100}, result])
        with patch.object(solver.expanded_solve, "evaluate_candidates", side_effect=anchor_policy), \
             patch.object(solver, "construct", return_value=(proposal, {"strategy": "attention_rows_ffn_gap"})), \
             patch.object(solver, "analyze", return_value={"with_cross_core_delay": {"lower_bound_cycles": lower}}):
            output = solver.evaluate_candidates(SimpleNamespace(graph={}), 2, evaluator, Mock(return_value={}))
        self.assertEqual(output[1], evaluator.call_count)
        return output

    def test_true_official_improvement_only(self):
        for value in (99, 100, 101):
            winner, calls, records, selection = self.run_policy({"makespan": value})
            self.assertEqual(winner[0], PROPOSAL if value < 100 else ANCHOR)
            self.assertEqual(winner[1]["makespan"], min(value, 100))
            self.assertEqual(calls, 2)
            self.assertEqual(selection["router"]["evaluation_calls"], 2)
            self.assertEqual(records[-1]["makespan"], value)

    def test_duplicate_or_bound_skip_second_evaluation(self):
        for proposal, lower, status in ((ANCHOR, 0, "duplicate"), (PROPOSAL, 100, "bound_pruned")):
            winner, calls, records, _ = self.run_policy(RuntimeError("must not evaluate"), proposal=proposal, lower=lower)
            self.assertEqual(winner[0], ANCHOR)
            self.assertEqual(calls, 1)
            self.assertEqual(records[-1]["status"], status)

    def test_invalid_proposal_preserves_anchor_but_bugs_propagate(self):
        winner, calls, records, _ = self.run_policy(EvaluationValidationError("capacity"))
        self.assertEqual(winner[0], ANCHOR)
        self.assertEqual(calls, 2)
        self.assertEqual(records[-1]["status"], "rejected")
        with self.assertRaisesRegex(RuntimeError, "unexpected defect"):
            self.run_policy(RuntimeError("unexpected defect"))

    def test_other_routes_return_unchanged_without_another_proposal(self):
        original = ((ANCHOR, {"makespan": 100}, "stage"), 2, [], {"router": {"route": "general_gap"}})
        with patch.object(solver.expanded_solve, "evaluate_candidates", return_value=original), \
             patch.object(solver, "construct") as construct:
            self.assertEqual(solver.evaluate_candidates(None, 5, Mock(), Mock()), original)
        construct.assert_not_called()

    def test_single_core_identity_avoids_even_constructing_duplicate(self):
        evaluator = Mock(return_value={"makespan": 100})
        with patch.object(solver.expanded_solve, "evaluate_candidates", side_effect=anchor_policy), \
             patch.object(solver, "construct") as construct:
            winner, calls, _, selection = solver.evaluate_candidates(None, 1, evaluator, Mock())
        construct.assert_not_called()
        self.assertEqual(winner[0], ANCHOR)
        self.assertEqual(calls, 1)
        self.assertEqual(evaluator.call_count, 1)
        self.assertEqual(selection["attention_gap_skip"], "single_core_assignment_invariant")
