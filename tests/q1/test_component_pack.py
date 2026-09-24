"""Graph-level regression checks, with no E0/E1/E2 calls."""
import copy
import unittest
from src.q1.component_pack import construct


def graph(nodes, links):
    ops = [{"id": n, "op": "MATMUL" if p == "M" else "RELU",
            "pipe": "PIPE_" + p, "cycles": w} for n, p, w in nodes]
    tensors, edges = [], []
    for i, (a, b) in enumerate(links, 1000):
        tensors.append({"id": i, "size": 64, "pos": "UB"})
        edges.extend([{"source": a, "target": i}, {"source": i, "target": b}])
    return {"ops": ops, "tensors": tensors, "edges": edges}


class ComponentPackTests(unittest.TestCase):
    def test_parallel_chains_stay_intact_and_use_cores(self):
        g = graph([(i, "V", 10) for i in range(1, 9)], [(1, 2), (3, 4), (5, 6), (7, 8)])
        original = copy.deepcopy(g)
        plan, d = construct(g, 4)
        self.assertEqual(d["components"], 4)
        self.assertEqual(d["core_compute_ops"], [2, 2, 2, 2])
        for a, b in [(1, 2), (3, 4), (5, 6), (7, 8)]:
            self.assertEqual(plan["node_to_subgraph"][a], plan["node_to_subgraph"][b])
        self.assertEqual(g, original)

    def test_internal_copy_bridge_must_join_components(self):
        g = graph([(1, "V", 10), (2, "M", 10), (3, "V", 10)], [(1, 2), (2, 3)])
        g["ops"][1]["op"] = "COPY_IN"
        plan, d = construct(g, 5)
        self.assertEqual(d["components"], 1)
        self.assertEqual(plan["node_to_subgraph"], {1: 0, 3: 0})
        self.assertEqual(plan["core_schedules"], [[0], [], [], [], []])

    def test_complementary_pipes_balance_before_ties(self):
        g = graph([(4, "M", 10), (2, "M", 10), (9, "V", 10), (1, "V", 10)], [])
        p, d = construct(g, 2)
        self.assertEqual(d["compute_pipe_work_by_core"],
                         [{"PIPE_M": 10, "PIPE_V": 10}] * 2)
        self.assertEqual(list(p["node_to_subgraph"]), [4, 2, 9, 1])
        self.assertEqual(construct(g, 2), (p, d))

    def test_single_core_is_one_task_and_invalid_domains_fail(self):
        g = graph([(1, "M", 4), (2, "V", 0)], [])
        p, d = construct(g, 1)
        self.assertEqual(p["core_schedules"], [[0]])
        self.assertEqual(d["tasks"], 1)
        for k in (0, 6, True):
            with self.assertRaises(ValueError):
                construct(g, k)
        with self.assertRaises(ValueError):
            construct(graph([(1, "M", -1)], []), 1)


if __name__ == "__main__":
    unittest.main()
