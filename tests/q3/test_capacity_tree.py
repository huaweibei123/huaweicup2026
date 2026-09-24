"""Check the production proxy algorithm against an independent cut-set oracle."""
import random
import unittest

from src.q3.construct import Index, UnsupportedStructure
from src.q3.capacity_tree import construct, threshold_cut
from src.q3.fragment_tree import construct as fragment
from src.q3.tree_solve import prepare


def make_graph(parents, weights):
    return {"ops": [{"id": i, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": w}
                    for i, w in enumerate(weights)], "tensors": [],
            "edges": [{"source": i, "target": p} for i, p in enumerate(parents)]}


def brute(parents, weights, k):
    best = sum(weights)
    for mask in range(1 << len(parents)):
        if mask.bit_count() >= k:
            continue
        owners = list(range(len(weights)))
        for u in reversed(range(len(parents))):
            if not (mask >> u) & 1:
                owners[u] = owners[parents[u]]
        totals = {}
        for u, w in enumerate(weights):
            totals[owners[u]] = totals.get(owners[u], 0) + w
        best = min(best, max(totals.values()))
    return best


class CapacityTreeTests(unittest.TestCase):
    def test_exact_threshold_against_all_cuts(self):
        rng = random.Random(240924)
        for n in (4, 5, 6, 7):
            for _ in range(8):
                parents = [rng.randrange(i + 1, n) for i in range(n - 1)]
                if len(set(parents)) == n - 1:
                    continue  # A serial chain is outside the constructor guard.
                weights = [rng.randrange(1, 12) for _ in range(n)]
                index = Index(make_graph(parents, weights))
                for k in range(1, min(n, 5) + 1):
                    plan, meta = construct(index, k)
                    self.assertEqual(meta["proxy_optimum_cycles"], brute(parents, weights, k))
                    self.assertEqual(sorted(x for s in plan["core_schedules"] for x in s), list(range(n)))

    def test_zero_threshold_and_indivisible_vertex(self):
        self.assertEqual(threshold_cut([0, 1], {0: [], 1: [0]}, {0: 0, 1: 0}, 0), [])
        self.assertIsNone(threshold_cut([0, 1], {0: [], 1: [0]}, {0: 2, 1: 1}, 1))

    def test_fragment_forest_bound_and_global_order(self):
        graph = make_graph([2, 2, 5, 4, 5], [13, 9, 2, 7, 3, 1])
        graph["ops"].extend([{"id": 6, "op": "COMPUTE", "pipe": "PIPE_M", "cycles": 18},
                             {"id": 7, "op": "COMPUTE", "pipe": "PIPE_M", "cycles": 4}])
        graph["edges"].append({"source": 6, "target": 7})
        index = Index(graph)
        for k in (1, 3, 5, 10):
            plan, meta = fragment(index, k)
            mapping = plan["node_to_subgraph"]
            all_nodes = [u for s in plan["core_schedules"] for u in s]
            self.assertEqual(sorted(all_nodes), list(range(8)))
            self.assertLessEqual(max(meta["core_work_cycles"]), meta["compute_load_upper_bound_cycles"])
            self.assertEqual(sum(meta["core_work_cycles"]), 57)
            # Check the union of original compute edges and emitted core orders.
            succ = {mapping[str(u)]: {mapping[str(v)] for v in index.succ[u]} for u in index.ops}
            for seq in plan["core_schedules"]:
                for a, b in zip(seq, seq[1:]):
                    succ[a].add(b)
            from src.q3.construct import topo
            self.assertEqual(len(topo(all_nodes, succ)), 8)

    def test_fanout_refusal_and_actual_fallback(self):
        g = make_graph([2, 2], [3, 4, 1])
        g["edges"].append({"source": 0, "target": 1})
        with self.assertRaises(UnsupportedStructure):
            fragment(Index(g), 2)
        plan, meta, selection = prepare(Index(g), 2, "fragment")
        self.assertEqual(meta["strategy"], "affine_eighth")
        self.assertIn("tree_declined", selection)
        self.assertEqual(len(plan["core_schedules"]), 2)


if __name__ == "__main__":
    unittest.main()
