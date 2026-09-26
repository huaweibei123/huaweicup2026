"""Bounded structural tests; no E0/E1/E2 invocations or performance claims."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("q1_fang", ROOT / "src/q1_yuanzhifang/construct.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def graph_from_edges(n, edges):
    return {"ops": [{"id": i, "op": "COMPUTE", "pipe": "PIPE_M" if i % 2 else "PIPE_V",
                     "cycles": 3 + i} for i in range(n)],
            "tensors": [{"id": 100 + j, "pos": "UB", "size": 16}
                        for j in range(len(edges))],
            "edges": [part for j, (a, b) in enumerate(edges)
                      for part in [{"source": a, "target": 100 + j},
                                   {"source": 100 + j, "target": b}]]}


class PackingTests(unittest.TestCase):
    def test_all_four_node_forward_dags(self):
        """All 64 DAGs in one fixed topological labelling, both modes, 1-5 cores.

        An independent reachability check validates data edges plus full core
        chains; this does not inherit the implementation's depth calculation.
        """
        possible = [(i, j) for i in range(4) for j in range(i + 1, 4)]
        count = 0
        for bits in range(1 << len(possible)):
            edges = [e for j, e in enumerate(possible) if bits & (1 << j)]
            graph = graph_from_edges(4, edges)
            for variant in ("chain-wave", "component-pack"):
                for cores in range(1, 6):
                    plan, _ = mod.construct(graph, cores, variant)
                    mapping = plan["node_to_subgraph"]
                    self.assertEqual(set(mapping), set(range(4)))
                    scheduled = [g for order in plan["core_schedules"] for g in order]
                    self.assertEqual(len(scheduled), len(set(scheduled)))
                    self.assertEqual(set(scheduled), set(mapping.values()))
                    reach = {(mapping[u], mapping[v]) for u, v in edges if mapping[u] != mapping[v]}
                    reach.update((a, b) for seq in plan["core_schedules"] for a, b in zip(seq, seq[1:]))
                    for v in scheduled:
                        for a in scheduled:
                            for b in scheduled:
                                if (a, v) in reach and (v, b) in reach:
                                    reach.add((a, b))
                    self.assertFalse(any((v, v) in reach for v in scheduled))
                    count += 1
        self.assertEqual(count, 640)

    def test_copy_contraction_retains_dependency(self):
        graph = graph_from_edges(4, [(0, 1), (1, 2), (2, 3)])
        graph["ops"][1]["op"] = "COPY_OUT"
        graph["ops"][1]["pipe"] = "PIPE_MTE3"
        graph["ops"][2]["op"] = "COPY_IN"
        graph["ops"][2]["pipe"] = "PIPE_MTE2"
        for variant in ("chain-wave", "component-pack"):
            plan, _ = mod.construct(graph, 3, variant)
            self.assertEqual(set(plan["node_to_subgraph"]), {0, 3})
            self.assertEqual(plan["node_to_subgraph"][0], plan["node_to_subgraph"][3])

    def test_deterministic_under_edge_order(self):
        graph = graph_from_edges(6, [(0, 2), (1, 2), (2, 3), (2, 4), (4, 5)])
        for variant in ("chain-wave", "component-pack"):
            plan, _ = mod.construct(graph, 4, variant)
            graph["edges"].reverse()
            self.assertEqual(plan, mod.construct(graph, 4, variant)[0])

    def test_invalid_core_counts(self):
        for cores in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                mod.construct(graph_from_edges(2, [(0, 1)]), cores)

    def test_switch_uses_graph_parallelism_without_scoring(self):
        # Four components suffice for four cores; a connected fan-in does not.
        for graph, chosen in ((graph_from_edges(8, [(0, 1), (2, 3), (4, 5), (6, 7)]), "component-pack"),
                              (graph_from_edges(5, [(0, 2), (1, 2), (2, 3), (3, 4)]), "chain-wave")):
            plan, diagnostic = mod.construct(graph, 4, "structural-switch")
            self.assertEqual(diagnostic["selected_variant"], chosen)
            self.assertEqual(plan, mod.construct(graph, 4, chosen)[0])

    def test_joint_cycle_guard_does_not_skip_empty_core(self):
        graph = graph_from_edges(4, [(0, 1), (2, 3)])
        # 0->1 and 2->3 data; core-order 1->2 and 3->0 closes a ring.
        plan = {"node_to_subgraph": dict(enumerate(range(4))),
                "core_schedules": [[1, 2], [3, 0], []]}
        with self.assertRaises(ValueError):
            mod.validate_task_order(mod.derive_multicore_plan(graph, plan))


if __name__ == "__main__":
    unittest.main()
