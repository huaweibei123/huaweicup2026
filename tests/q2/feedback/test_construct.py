"""Structural checks only; no claim of official execution validation."""
import json
import unittest

from src.q2.feedback.construct import Index, ROOT, UnsupportedStructure


class ConstructTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((ROOT / "data/raw/a/official/data/case_008.json").read_bytes())
        cls.index = Index(cls.graph)

    def test_all_strategies_preserve_mapping_and_core_ownership(self):
        plans = [self.index.build(4, s)[0] for s in
                 ("component", "affine_eighth", "resource_word", "pipe_window", "pipe_window_fill")]
        first = plans[0]
        for plan in plans:
            self.assertEqual(list(first["node_to_subgraph"].items()), list(plan["node_to_subgraph"].items()))
            self.assertEqual([set(x) for x in first["core_schedules"]], [set(x) for x in plan["core_schedules"]])

    def test_dependency_order_all_windows_and_cores(self):
        for cores in (1, 2, 3, 4, 5):
            for window in (1, 2, 3, 8):
                plan, _ = self.index.build(cores, "pipe_window", window)
                mapping = plan["node_to_subgraph"]
                for schedule in plan["core_schedules"]:
                    rank = {sg: i for i, sg in enumerate(schedule)}
                    for u in self.index.ops:
                        if mapping[str(u)] in rank:
                            for v in self.index.succ[u]:
                                self.assertLess(rank[mapping[str(u)]], rank[mapping[str(v)]])

    def test_single_window_is_component_order(self):
        a, _ = self.index.build(4, "component")
        b, _ = self.index.build(4, "pipe_window", 1)
        self.assertEqual(a, b)
        c, _ = self.index.build(4, "pipe_window_fill", 1)
        self.assertEqual(a, c)

    def test_fill_policy_preserves_edges_for_every_pipe(self):
        for cores in (1, 2, 3, 4, 5):
            plan, _ = self.index.build(cores, "pipe_window_fill")
            mapping = plan["node_to_subgraph"]
            rank = {sg: (c, i) for c, seq in enumerate(plan["core_schedules"]) for i, sg in enumerate(seq)}
            for u in self.index.ops:
                for v in self.index.succ[u]:
                    self.assertEqual(rank[mapping[str(u)]][0], rank[mapping[str(v)]][0])
                    self.assertLess(rank[mapping[str(u)]][1], rank[mapping[str(v)]][1])

    def test_known_word_family_is_detected_not_assumed(self):
        self.assertEqual(self.index.word_descriptor(), (1158, 2196, 3))
        bad = json.loads(json.dumps(self.graph))
        target = next(o for o in bad["ops"] if o["id"] == self.index.components[0][0])
        target["cycles"] += 1
        with self.assertRaises(UnsupportedStructure):
            Index(bad).word_descriptor()

    def test_branching_component_still_preserves_actual_edges(self):
        # These public graphs have distinct structures and exercise the general
        # topological-chain lowering without the homogeneous-word guard.
        for case in ("044", "080"):
            graph = json.loads((ROOT / f"data/raw/a/official/data/case_{case}.json").read_bytes())
            index = Index(graph)
            plan, _ = index.build(4, "pipe_window")
            m = plan["node_to_subgraph"]
            rank = {sg: (c, i) for c, seq in enumerate(plan["core_schedules"]) for i, sg in enumerate(seq)}
            for u in index.ops:
                for v in index.succ[u]:
                    cu, ru = rank[m[str(u)]]
                    cv, rv = rank[m[str(v)]]
                    self.assertEqual(cu, cv)
                    self.assertLess(ru, rv)


if __name__ == "__main__":
    unittest.main()
