"""Small structural witnesses; no evaluators."""
import unittest
from src.q1.component_pack import construct as component
from src.q1.tree_frontier import construct
from tests.q1.test_component_pack import graph


class FrontierTests(unittest.TestCase):
    def test_balanced_reduction_is_independent_workers_then_tail(self):
        g = graph([(i, "M", 100) for i in range(1, 9)] +
                  [(i, "V", 1) for i in range(9, 16)],
                  [(1, 9), (2, 9), (3, 10), (4, 10), (5, 11), (6, 11),
                   (7, 12), (8, 12), (9, 13), (10, 13), (11, 14), (12, 14),
                   (13, 15), (14, 15)])
        p, d = construct(g, 4)
        self.assertEqual(d["selected"], "tree-frontier")
        self.assertEqual(d["frontier_packet_count"], 4)
        self.assertEqual(d["tail_ops"], 3)
        self.assertEqual(d["core_frontier_ops"], [3] * 4)
        self.assertEqual(len({p["node_to_subgraph"][i] for i in (9, 10, 11, 12)}), 4)
        self.assertEqual({p["node_to_subgraph"][i] for i in (13, 14, 15)}, {4})
        fine, detail = construct(g, 4, packet_factor=4)
        self.assertEqual(detail["frontier_packet_count"], 8)
        self.assertEqual(detail["tail_ops"], 7)
        self.assertEqual(detail["core_frontier_ops"], [2] * 4)
        self.assertEqual({fine["node_to_subgraph"][i] for i in range(9, 16)}, {4})

    def test_diamond_is_not_mistaken_for_disjoint_subtrees(self):
        g = graph([(i, "M", 1) for i in range(1, 5)], [(1, 2), (1, 3), (2, 4), (3, 4)])
        p, d = construct(g, 4)
        self.assertEqual(d["selected"], "component-pack")
        self.assertEqual(p, component(g, 4)[0])

    def test_chain_and_one_core_fall_back(self):
        g = graph([(i, "V", 1) for i in range(1, 10)], [(i, i+1) for i in range(1, 9)])
        for k in (1, 4):
            p, d = construct(g, k)
            self.assertEqual(d["selected"], "component-pack")
            self.assertEqual(p, component(g, k)[0])
        for f in (0, True, 65):
            with self.assertRaises(ValueError):
                construct(g, 4, packet_factor=f)


if __name__ == "__main__":
    unittest.main()
