"""Original-DAG legality, persistent calendar, and exact acceptance checks."""
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan
from src.q3.gap_calendar import empty, earliest, reserve
from src.q3.gap_dag import construct
from src.q3 import expanded_solve as solver
from evaluation_validation import EvaluationValidationError


def graph():
    return {"ops": [{"id": u, "op": "COMPUTE", "pipe": p, "cycles": d}
                    for u, p, d in [(0, "PIPE_V", 10), (1, "PIPE_M", 90),
                                    (2, "PIPE_V", 70), (3, "PIPE_V", 20),
                                    (4, "PIPE_M", 90), (5, "PIPE_V", 5)]],
            "tensors": [], "edges": [{"source": u, "target": v}
                                      for u, v in [(0, 1), (0, 2), (1, 3),
                                                   (2, 3), (3, 4), (2, 5)]]}


class GapTests(unittest.TestCase):
    def test_calendar_matches_discrete_free_slots_and_preserves_prior_tree(self):
        root = empty()
        occupied = set()
        for release, duration in [(0, 9), (20, 7), (4, 4), (13, 3), (4, 2), (28, 1)]:
            old = root
            start = release
            while any(x in occupied for x in range(start, start + duration)):
                start += 1
            self.assertEqual(earliest(root, release, duration), start)
            root = reserve(root, start, duration)
            self.assertEqual(earliest(old, release, duration), start)
            occupied.update(range(start, start + duration))
            for r in range(35):
                want = r
                while any(x in occupied for x in range(want, want + 3)):
                    want += 1
                self.assertEqual(earliest(root, r, 3), want)

    def test_original_ops_and_topology_preserved(self):
        g = graph()
        before = deepcopy(g)
        index = Index(g)
        for k in range(1, 6):
            plan, meta = construct(index, k, 60, 500)
            self.assertEqual((plan, meta), construct(index, k, 60, 500))
            self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
            self.assertEqual(sorted(s for word in plan["core_schedules"] for s in word),
                             list(range(len(index.ops))))
            derive_multicore_plan(g, plan)
            self.assertEqual(meta["official_e0_calls"], 0)
        self.assertEqual(g, before)

    def test_guard_rejects_tree_and_invalid_pipe(self):
        g = graph()
        g["edges"] = [{"source": u, "target": u + 1} for u in range(5)]
        with self.assertRaises(UnsupportedStructure):
            construct(Index(g), 2, 60, 500)
        with self.assertRaises(ValueError):
            construct(Index(graph()), True, 60, 500)

    def test_accept_only_actual_official_improvement(self):
        index = Index(graph())
        for candidate_M, accepted in [(99, True), (100, False), (101, False)]:
            evaluate = Mock(side_effect=[{"makespan": 100}, {"makespan": candidate_M}])
            with patch.object(solver, "analyze", return_value={"with_cross_core_delay": {"lower_bound_cycles": 0}}):
                winner, calls, records, selection = solver.general_candidates(index, 2, evaluate, Mock())
            self.assertEqual(calls, 2)
            self.assertEqual(winner[1]["makespan"], 99 if accepted else 100)
            self.assertEqual(len(records), 2)

    def test_pruning_and_proposal_validation_failure_preserve_anchor(self):
        index = Index(graph())
        for lower, failure, expected_calls in [(100, None, 1), (0, EvaluationValidationError("capacity"), 2)]:
            evaluate = Mock(side_effect=[{"makespan": 100}, failure])
            with patch.object(solver, "analyze", return_value={"with_cross_core_delay": {"lower_bound_cycles": lower}}):
                winner, calls, records, _ = solver.general_candidates(index, 2, evaluate, Mock())
            self.assertEqual(winner[1]["makespan"], 100)
            self.assertEqual(calls, expected_calls)
            self.assertEqual(records[-1]["status"], "bound_pruned" if lower else "rejected")

    def test_programming_failure_is_not_silent_fallback(self):
        with patch.object(solver, "construct", side_effect=RuntimeError("constructor defect")):
            with self.assertRaisesRegex(RuntimeError, "constructor defect"):
                solver.general_candidates(Index(graph()), 2, Mock(), Mock())


if __name__ == "__main__":
    unittest.main()
