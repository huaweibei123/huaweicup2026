"""Eight finite structural checks; zero E0 simulation calls."""
import copy
import unittest

from src.q3.construct import Index, UnsupportedStructure, topo


def chains(count=4):
    ops, edges = [], []
    for j in range(count):
        ids = [10 * j + i for i in range(3)]
        for u, pipe, cycles in zip(ids, ["PIPE_M", "PIPE_V", "PIPE_M"], [10, 15, 10]):
            ops.append({"id": u, "op": "COMPUTE", "pipe": pipe, "cycles": cycles})
        edges.extend({"source": u, "target": v} for u, v in zip(ids, ids[1:]))
    return {"ops": ops, "tensors": [], "edges": edges}


class StructuralTests(unittest.TestCase):
    def test_copy_projection_keeps_dependency(self):
        graph = chains(1)
        graph["ops"].append({"id": 3, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 1})
        graph["edges"] = [{"source": 0, "target": 3}, {"source": 3, "target": 1},
                          {"source": 1, "target": 2}]
        idx = Index(graph)
        self.assertEqual(idx.components, [[0, 1, 2]])
        self.assertIn(1, idx.succ[0])

    def test_same_mapping_and_core_across_strategies(self):
        idx = Index(chains(9))
        plans = [idx.build(4, s)[0] for s in ("component", "affine_eighth", "resource_word")]
        ownership = []
        for plan in plans:
            ownership.append({sg: c for c, ss in enumerate(plan["core_schedules"]) for sg in ss})
        self.assertTrue(all(p["node_to_subgraph"] == plans[0]["node_to_subgraph"] for p in plans))
        self.assertTrue(all(x == ownership[0] for x in ownership))

    def test_precedence_in_all_orders_and_small_job_counts(self):
        for jobs in (1, 2, 3, 7):
            idx = Index(chains(jobs))
            for strategy in ("component", "affine_eighth", "resource_word"):
                seqs, _ = idx.sequences(2, strategy)
                rank = {u: (c, i) for c, seq in enumerate(seqs) for i, u in enumerate(seq)}
                self.assertEqual(len(rank), 3 * jobs)
                for u in idx.succ:
                    for v in idx.succ[u]:
                        self.assertEqual(rank[u][0], rank[v][0])
                        self.assertLess(rank[u][1], rank[v][1])

    def test_resource_word_declines_heterogeneous(self):
        graph = chains()
        graph["ops"][4]["cycles"] += 1
        with self.assertRaises(UnsupportedStructure):
            Index(graph).build(2, "resource_word")

    def test_resource_word_declines_nonserial_and_wrong_regime(self):
        graph = chains(1)
        graph["edges"] = [{"source": 0, "target": 2}, {"source": 1, "target": 2}]
        with self.assertRaises(UnsupportedStructure):
            Index(graph).build(1, "resource_word")
        graph = chains(1)
        graph["ops"][1]["cycles"] = 21
        with self.assertRaises(UnsupportedStructure):
            Index(graph).build(1, "resource_word")

    def test_deterministic_and_does_not_mutate_graph(self):
        graph = chains(8)
        before = copy.deepcopy(graph)
        self.assertEqual(Index(graph).build(3, "affine_eighth"),
                         Index(graph).build(3, "affine_eighth"))
        self.assertEqual(graph, before)

    def test_branching_component_affine_is_still_topological(self):
        graph = chains(2)
        graph["edges"].append({"source": 0, "target": 11})
        idx = Index(graph)
        for strategy in ("component", "affine_eighth"):
            seqs, _ = idx.sequences(3, strategy)
            ranks = {u: i for seq in seqs for i, u in enumerate(seq)}
            for u, ss in idx.succ.items():
                for v in ss:
                    self.assertLess(ranks[u], ranks[v])

    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):
            topo([0, 1], {0: {1}, 1: {0}})


if __name__ == "__main__":
    unittest.main()
