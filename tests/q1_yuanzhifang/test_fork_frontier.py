"""Independent finite DAG coverage and coarse-stage regression tests; no E0."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
from fork_frontier import construct
from test_construct import graph_from_edges


class ForkFrontierTests(unittest.TestCase):
    def test_unit_frontiers_have_acyclic_joint_orders(self):
        possible = [(u, v) for u in range(4) for v in range(u + 1, 4)]
        for bits in range(64):
            edges = [e for j, e in enumerate(possible) if bits & (1 << j)]
            graph = graph_from_edges(4, edges)
            for cores in range(1, 6):
                plan, info = construct(graph, cores, frontier_tasks="unit")
                m = plan["node_to_subgraph"]
                self.assertEqual(set(m), set(range(4)))
                ts = [t for row in plan["core_schedules"] for t in row]
                self.assertEqual(len(ts), len(set(ts)))
                self.assertEqual(set(ts), set(m.values()))
                reach = {(m[a], m[b]) for a, b in edges if m[a] != m[b]}
                reach.update((a, b) for row in plan["core_schedules"] for a, b in zip(row, row[1:]))
                for v in ts:
                    for a in ts:
                        for b in ts:
                            if (a, v) in reach and (v, b) in reach:
                                reach.add((a, b))
                self.assertFalse(any((t, t) in reach for t in ts))
                self.assertTrue(all(t["units"] == 1 for t in info["tasks"]))

    def test_small_dags_cover_ops_and_have_no_joint_cycle(self):
        possible = [(u, v) for u in range(4) for v in range(u + 1, 4)]
        for bits in range(64):
            edges = [e for j, e in enumerate(possible) if bits & (1 << j)]
            graph = graph_from_edges(4, edges)
            for cores in range(1, 6):
                plan, _ = construct(graph, cores)
                mapping = plan["node_to_subgraph"]
                self.assertEqual(set(mapping), set(range(4)))
                ts = [t for row in plan["core_schedules"] for t in row]
                self.assertEqual(len(ts), len(set(ts)))
                self.assertEqual(set(ts), set(mapping.values()))
                reach = {(mapping[a], mapping[b]) for a, b in edges if mapping[a] != mapping[b]}
                reach.update((a, b) for row in plan["core_schedules"] for a, b in zip(row, row[1:]))
                for v in ts:
                    for a in ts:
                        for b in ts:
                            if (a, v) in reach and (v, b) in reach:
                                reach.add((a, b))
                self.assertFalse(any((t, t) in reach for t in ts))

    def test_repeated_fork_join_keeps_entire_chains_and_one_reduction_tail(self):
        edges, ops, previous = [], [], None
        for stage in range(3):
            leaves = []
            for branch in range(4):
                ids = list(range(len(ops), len(ops) + 3))
                ops.extend({"id": u, "op": "X", "pipe": "PIPE_V", "cycles": 500} for u in ids)
                edges.extend(zip(ids, ids[1:]))
                if previous is not None:
                    edges.append((previous, ids[0]))
                leaves.append(ids[-1])
            accumulator = leaves[0]
            for leaf in leaves[1:]:
                u = len(ops)
                ops.append({"id": u, "op": "ADD", "pipe": "PIPE_V", "cycles": 1})
                edges.extend(((accumulator, u), (leaf, u)))
                accumulator = u
            previous = accumulator
        graph = graph_from_edges(len(ops), edges)
        graph["ops"] = ops
        plan, d = construct(graph, 2)
        self.assertEqual(d["stages"], 3)
        self.assertEqual(d["task_count"], 9)
        self.assertEqual([x["ops"] for x in d["tasks"] if x["phase"] == 1], [3, 3, 3])
        for stage in range(3):
            for branch in range(4):
                ids = range(stage * 15 + branch * 3, stage * 15 + branch * 3 + 3)
                self.assertEqual(len({plan["node_to_subgraph"][u] for u in ids}), 1)
        graph["edges"].reverse()
        self.assertEqual(plan, construct(graph, 2)[0])
        separate, details = construct(graph, 2, frontier_tasks="unit")
        self.assertEqual(details["task_count"], 15)
        self.assertEqual([x["ops"] for x in details["tasks"] if x["phase"] == 1], [3, 3, 3])
        for stage in range(3):
            for branch in range(4):
                ids = range(stage * 15 + branch * 3, stage * 15 + branch * 3 + 3)
                self.assertEqual(len({separate["node_to_subgraph"][u] for u in ids}), 1)

    def test_copy_bridge_exclusion_and_argument_checks(self):
        graph = graph_from_edges(4, [(0, 1), (1, 2), (2, 3)])
        graph["ops"][1]["op"] = "COPY_OUT"
        graph["ops"][2]["op"] = "COPY_IN"
        plan, _ = construct(graph, 3)
        self.assertEqual(set(plan["node_to_subgraph"]), {0, 3})
        for cores in (0, 6, True, 2.5):
            with self.assertRaises(ValueError):
                construct(graph, cores)
        with self.assertRaises(ValueError):
            construct(graph, 2, grain=0)
        with self.assertRaises(ValueError):
            construct(graph, 2, frontier_tasks="unknown")


if __name__ == "__main__":
    unittest.main()
