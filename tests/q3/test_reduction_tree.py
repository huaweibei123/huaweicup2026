"""Structural and exact-acceptance checks, with no official simulation."""
import unittest
from unittest.mock import patch

from src.q3.construct import Index, UnsupportedStructure
from src.q3.reduction_tree import construct
from src.q3.safe_solve import evaluate_candidates


def graph():
    # Three unequal leaves and a two-level reduction, adversarial to ID ordering.
    return {"ops": [{"id": u, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": d}
                    for u, d in [(8, 9), (2, 7), (5, 5), (1, 1), (0, 1)]],
            "tensors": [], "edges": [{"source": u, "target": v}
                                       for u, v in [(8, 1), (2, 1), (1, 0), (5, 0)]]}


class ReductionTreeTests(unittest.TestCase):
    def test_coverage_precedence_and_blank_cores(self):
        index = Index(graph())
        for k in (1, 2, 3, 7):
            plan, meta = construct(index, k)
            ss = plan["core_schedules"]
            self.assertEqual(len(ss), k)
            self.assertEqual(sorted(x for seq in ss for x in seq), list(range(5)))
            owner = {x: c for c, seq in enumerate(ss) for x in seq}
            rank = {x: n for seq in ss for n, x in enumerate(seq)}
            mapping = plan["node_to_subgraph"]
            for u, successors in index.succ.items():
                for v in successors:
                    a, b = mapping[str(u)], mapping[str(v)]
                    if owner[a] == owner[b]:
                        self.assertLess(rank[a], rank[b])
            self.assertEqual(sum(meta["block_work_cycles"]), 23)
            self.assertEqual(len(meta["cuts"]), min(k, 5) - 1)

    def test_fanout_is_outside_guard(self):
        g = graph()
        g["edges"].append({"source": 5, "target": 1})
        with self.assertRaises(UnsupportedStructure):
            construct(Index(g), 2)

    def test_exact_gate_strict_improvement_only(self):
        for numbers, expected in [([100, 90], "balanced_reduction_tree"),
                                  ([100, 100], "affine_eighth"),
                                  ([100, 120], "affine_eighth")]:
            saved = []
            it = iter(numbers)
            winner, calls, records, _ = evaluate_candidates(
                Index(graph()), 2, lambda _: {"makespan": next(it)},
                lambda name, p, r: saved.append(name))
            self.assertEqual(winner[2], expected)
            self.assertEqual(calls, 2)
            self.assertEqual(saved, ["seed", "tree"])

    def test_rejected_proposal_keeps_confirmed_seed(self):
        from evaluation_validation import EvaluationValidationError
        with patch("src.q3.safe_solve.tree_construct", return_value=({"p": 1}, {})):
            outputs = iter([{"makespan": 100}, EvaluationValidationError("probe")])
            def evaluate(_):
                value = next(outputs)
                if isinstance(value, Exception):
                    raise value
                return value
            winner, calls, records, _ = evaluate_candidates(Index(graph()), 2, evaluate,
                                                           lambda *args: None)
        self.assertEqual(winner[1]["makespan"], 100)
        self.assertEqual(calls, 2)
        self.assertEqual(records[-1]["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
