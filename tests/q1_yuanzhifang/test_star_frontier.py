"""Structural/model checks, not official E0 experiments."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
from star_frontier import construct, guarded_stages

WAITS = {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000}


def model_graph(rounds, shape):
    ops, edges, root = [], [], None

    def op(cost, parents):
        u = len(ops)
        ops.append({"id": u, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": cost})
        edges.extend({"source": p, "target": u} for p in parents)
        return u

    for _ in range(rounds):
        leaves = []
        for _ in range(12):
            previous = root
            for _ in range(4):
                previous = op(524, [] if previous is None else [previous])
            leaves.append(previous)
        if shape == "comb":
            root = leaves[0]
            for leaf in leaves[1:]:
                root = op(13, [root, leaf])
        else:
            while len(leaves) > 1:
                nxt = [op(13, leaves[i:i + 2]) for i in range(0, len(leaves) - 1, 2)]
                if len(leaves) % 2:
                    nxt.append(leaves[-1])
                leaves = nxt
            root = leaves[0]
    return {"ops": ops, "edges": edges, "tensors": []}


class StarTests(unittest.TestCase):
    def test_two_reduction_shapes_and_round_counts(self):
        for shape in ("balanced", "comb"):
            for rounds, expected in ((1, 6483), (2, 13442), (24, 166540)):
                graph = model_graph(rounds, shape)
                plan, info = construct(graph, 5, WAITS)
                self.assertEqual(info["selected"], "split-chain-star")
                self.assertEqual(info["model_r_cycles"], expected)
                self.assertEqual(info["task_count"], 10 + 11 * (rounds - 1))
                # Independently check whole data+core quotient by closure.
                mapping = plan["node_to_subgraph"]
                arcs = {(mapping[e["source"]], mapping[e["target"]]) for e in graph["edges"]
                        if mapping[e["source"]] != mapping[e["target"]]}
                arcs.update((a, b) for seq in plan["core_schedules"] for a, b in zip(seq, seq[1:]))
                # Numeric Task IDs were emitted in phase order, giving an
                # independent strict ranking certificate for every arc.
                self.assertTrue(all(a < b for a, b in arcs))

    def test_structural_guard_not_graph_name_or_branch_count_only(self):
        graph = model_graph(2, "balanced")
        graph["ops"][2]["pipe"] = "PIPE_M"
        self.assertIsNone(guarded_stages(graph)[0])
        self.assertEqual(construct(graph, 5, WAITS)[1]["selected"], "fork-fallback")
        graph = model_graph(2, "comb")
        graph["edges"].append({"source": 0, "target": 5})
        self.assertIsNone(guarded_stages(graph)[0])
        for k in (True, 5.0, 0, 6):
            with self.assertRaises(ValueError):
                construct(graph, k, WAITS)

    def test_node_relabeling_and_edge_order_preserve_model_value(self):
        graph = model_graph(2, "balanced")
        remap = {o["id"]: 10000 - 3 * o["id"] for o in graph["ops"]}
        for o in graph["ops"]:
            o["id"] = remap[o["id"]]
        for e in graph["edges"]:
            e["source"], e["target"] = remap[e["source"]], remap[e["target"]]
        graph["edges"].reverse()
        self.assertEqual(construct(graph, 5, WAITS)[1]["model_r_cycles"], 13442)


if __name__ == "__main__":
    unittest.main()
