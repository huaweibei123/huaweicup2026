"""Independent exhaustive cut oracle for the scalar tree DP, not an E0 test."""
import itertools
import json
import random
import unittest

from src.q2.feedback.construct import Index, ROOT, UnsupportedStructure
from src.q2.feedback.tree import connected_partition


def parts_for(order, parent, weights, cuts):
    groups = {}
    for u in order:
        root = u
        while root in parent and (root, parent[root]) not in cuts:
            root = parent[root]
        groups[root] = groups.get(root, 0) + weights[u]
    return sorted(groups.values())


class TreeTests(unittest.TestCase):
    def test_matches_exhaustive_connected_cut_optimum(self):
        rng = random.Random(20260924)
        for n in range(2, 10):
            for repeat in range(5):
                order = list(range(n))
                parent = {u: rng.randrange(u + 1, n) for u in order[:-1]}
                children = {u: [] for u in order}
                for u, v in parent.items():
                    children[v].append(u)
                weights = {u: rng.randint(1, 40) for u in order}
                for k in range(1, min(n, 5) + 1):
                    cap, cuts, _ = connected_partition(order, children, weights, k)
                    optimum = min(max(parts_for(order, parent, weights, set(c)))
                                  for c in itertools.combinations(parent.items(), k - 1))
                    self.assertEqual(cap, optimum, (n, repeat, k))
                    loads = parts_for(order, parent, weights, cuts)
                    self.assertEqual(len(loads), k)
                    self.assertEqual(max(loads), optimum)

    def test_official_tree_plan_covers_and_preserves_dependencies(self):
        graph = json.loads((ROOT / "data/raw/a/official/data/case_002.json").read_bytes())
        index = Index(graph)
        for k in (1, 2, 3, 4, 5):
            plan, meta = index.build(k, "tree_dp")
            self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
            self.assertEqual(len(meta["cut_edges"]), k - 1)
            self.assertEqual(max(meta["part_work"]), meta["scalar_partition_optimum"])
            mapping = plan["node_to_subgraph"]
            rank = {sg: (c, i) for c, seq in enumerate(plan["core_schedules"]) for i, sg in enumerate(seq)}
            self.assertEqual(len(rank), len(index.ops))
            for u in index.order:
                for v in index.succ[u]:
                    cu, ru = rank[mapping[str(u)]]
                    cv, rv = rank[mapping[str(v)]]
                    if cu == cv:
                        self.assertLess(ru, rv)

    def test_rejects_non_tree_without_fallback_scoring(self):
        graph = json.loads((ROOT / "data/raw/a/official/data/case_044.json").read_bytes())
        with self.assertRaises(UnsupportedStructure):
            Index(graph).build(4, "tree_dp")


if __name__ == "__main__":
    unittest.main()
