"""Synthetic structure and arithmetic checks; no official graph or evaluator."""
import copy
import unittest

from src.q1.gated_root_frontier import construct, guarded_stages, root_count, choose_counts


def model_graph(specs, shapes):
    ops, edges, previous_root, all_chains = [], [], None, []
    def op(cost, parents, pipe="PIPE_V"):
        u = len(ops)
        ops.append({"id": u, "op": "COMPUTE", "pipe": pipe, "cycles": cost})
        edges.extend({"source": p, "target": u} for p in parents)
        return u
    for (width, depth, chain_cycle, tail_cycle), shape in zip(specs, shapes):
        chains, leaves = [], []
        for _ in range(width):
            chain, prev = [], previous_root
            for _ in range(depth):
                prev = op(chain_cycle, [] if prev is None else [prev])
                chain.append(prev)
            chains.append(chain)
            leaves.append(prev)
        all_chains.append(chains)
        if shape == "comb":
            previous_root = leaves[0]
            for leaf in leaves[1:]:
                previous_root = op(tail_cycle, [previous_root, leaf])
        else:
            while len(leaves) > 1:
                next_leaves = []
                for i in range(0, len(leaves)-1, 2):
                    next_leaves.append(op(tail_cycle, leaves[i:i+2]))
                if len(leaves) % 2:
                    next_leaves.append(leaves[-1])
                leaves = next_leaves
            previous_root = leaves[0]
    return {"ops": ops, "edges": edges, "tensors": []}, all_chains


class GatedRootTests(unittest.TestCase):
    def test_binary_search_matches_exhaustive_proxy(self):
        for width in range(2, 41):
            for cores in range(2, min(5, width) + 1):
                for h, same, cross in ((1, 0, 0), (3, 1, 7), (11, 4, 4), (100, 2, 900)):
                    for gate in (1, 2):
                        def score(q):
                            return max(q*h + gate*same,
                                       ((width-q+cores-2)//(cores-1))*h + gate*cross)
                        expected = min(range(1, width-cores+2), key=lambda q: (score(q), -q))
                        self.assertEqual(root_count(width, cores, h, gate, same, cross), expected)

    def test_active_core_choice_matches_exhaustive_proxy(self):
        for width in range(2, 21):
            for cores in range(2, 6):
                for h, same, cross in ((1, 0, 0), (10, 1, 9), (100, 5, 25)):
                    for gate in (1, 2):
                        candidates = []
                        for active in range(1, min(width, cores)+1):
                            for q in range(1, width-active+2):
                                score = (width*h+gate*same if active == 1 else
                                         max(q*h+gate*same,
                                             ((width-q+active-2)//(active-1))*h+gate*cross))
                                candidates.append((score, active, -q, q))
                        score, active, _, q = min(candidates)
                        counts, actual_active, actual_q, actual_score = choose_counts(
                            width, cores, h, gate, same, cross)
                        self.assertEqual((actual_score, actual_active, actual_q), (score, active, q))
                        self.assertEqual(len(counts), cores)
                        self.assertEqual(sum(counts), width)
                        self.assertEqual(counts[active:], [0]*(cores-active))

    def test_generic_two_round_shapes_and_rank(self):
        for specs, shapes, cores in (
            ([(7, 3, 30, 2), (9, 2, 21, 5)], ["balanced", "comb"], 3),
            ([(5, 6, 14, 1), (8, 3, 40, 4)], ["comb", "balanced"], 4),
            ([(2, 2, 70, 3), (3, 5, 25, 7)], ["balanced", "comb"], 2),
        ):
            with self.subTest(specs=specs):
                graph, chains = model_graph(specs, shapes)
                plan, info = construct(graph, cores, {"task_same_core_wait_cycles": 2,
                                                      "task_cross_core_wait_cycles": 20})
                self.assertEqual(info["selected"], "gated-root-frontier")
                self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
                mapping = plan["node_to_subgraph"]
                self.assertEqual(set(mapping), {o["id"] for o in graph["ops"]})
                self.assertEqual(info["task_count"],
                                 sum(r["active_cores"] + 1 for r in info["rounds"]))
                self.assertEqual(len(info["rounds"]), 2)
                for round_chains in chains:
                    for chain in round_chains:
                        self.assertEqual(len({mapping[u] for u in chain}), 1)
                ranks = {task["id"]: (task["stage"], task["phase"]) for task in info["tasks"]}
                arcs = {(mapping[e["source"]], mapping[e["target"]])
                        for e in graph["edges"] if mapping[e["source"]] != mapping[e["target"]]}
                arcs.update((a, b) for seq in plan["core_schedules"]
                            for a, b in zip(seq, seq[1:]))
                self.assertTrue(all(ranks[a] < ranks[b] for a, b in arcs))
                for record in info["rounds"]:
                    self.assertEqual(sum(record["counts"]), record["width"])
                    active = record["active_cores"]
                    if active > 1:
                        self.assertLessEqual(max(record["counts"][1:active]) -
                                             min(record["counts"][1:active]), 1)

    def test_variable_active_cores_and_no_empty_tasks(self):
        graph, _ = model_graph([(8, 2, 50, 1), (3, 2, 5, 1)],
                               ["balanced", "comb"])
        plan, info = construct(graph, 5, {"task_same_core_wait_cycles": 0,
                                          "task_cross_core_wait_cycles": 30})
        self.assertIsNotNone(plan)
        active = [r["active_cores"] for r in info["rounds"]]
        self.assertNotEqual(active[0], active[1])
        self.assertEqual(info["task_count"], sum(a+1 for a in active))
        self.assertTrue(all(t["ops"] > 0 for t in info["tasks"]))

    def test_tail_cost_outlier_still_peels_to_chains(self):
        graph, chains = model_graph([(6, 2, 1, 1)], ["balanced"])
        tail_nodes = set(range(len(graph["ops"]))) - {
            u for round_chains in chains for chain in round_chains for u in chain}
        graph["ops"][min(tail_nodes)]["cycles"] = 10**9
        plan, info = construct(graph, 5)
        self.assertIsNotNone(plan)
        self.assertEqual(info["rounds"][0]["width"], 6)
        self.assertEqual(info["rounds"][0]["tail_cycles"], 10**9 + 4)

    def test_optional_reduction_fusion_is_local_and_acyclic(self):
        for shape in ("balanced", "comb"):
            with self.subTest(shape=shape):
                graph, chains = model_graph([(7, 3, 20, 2), (5, 2, 30, 3)],
                                            [shape, shape])
                plain, _ = construct(graph, 3)
                plan, info = construct(graph, 3, fuse_reductions=True)
                self.assertEqual(set(plan["node_to_subgraph"]),
                                 {o["id"] for o in graph["ops"]})
                self.assertEqual(len(plan["node_to_subgraph"]), len(graph["ops"]))
                self.assertEqual(info["fused_reduction_ops"],
                                 sum(len(r["fused_reduction_ops"]) for r in info["rounds"]))
                self.assertLessEqual(info["emitted_tail_count"], 2)
                mapping = plan["node_to_subgraph"]
                branch_ids = {t["id"] for t in info["tasks"] if t["phase"] == 0}
                parents = {o["id"]: set() for o in graph["ops"]}
                for edge in graph["edges"]:
                    parents[edge["target"]].add(edge["source"])
                for record in info["rounds"]:
                    for u in record["fused_reduction_ops"]:
                        self.assertEqual(len(parents[u]), 2)
                        self.assertEqual({mapping[p] for p in parents[u]}, {mapping[u]})
                        self.assertIn(mapping[u], branch_ids)
                rank = {t["id"]: (t["stage"], t["phase"]) for t in info["tasks"]}
                arcs = {(mapping[e["source"]], mapping[e["target"]])
                        for e in graph["edges"] if mapping[e["source"]] != mapping[e["target"]]}
                arcs.update((a, b) for line in plan["core_schedules"]
                            for a, b in zip(line, line[1:]))
                self.assertTrue(all(rank[a] < rank[b] for a, b in arcs))
                self.assertEqual(set(plain["node_to_subgraph"]), set(mapping))

    def test_single_active_core_fuses_entire_tail(self):
        graph, _ = model_graph([(4, 2, 1, 3)], ["comb"])
        plan, info = construct(graph, 5,
                               {"task_same_core_wait_cycles": 0,
                                "task_cross_core_wait_cycles": 10**6},
                               fuse_reductions=True)
        self.assertEqual(info["rounds"][0]["active_cores"], 1)
        self.assertEqual(info["emitted_tail_count"], 0)
        self.assertEqual(info["fused_reduction_ops"], 3)
        self.assertEqual(info["task_count"], 1)
        self.assertEqual(set(plan["node_to_subgraph"].values()), {0})

    def test_rejects_heterogeneous_and_extraneous_structure(self):
        graph, chains = model_graph([(6, 3, 25, 2), (7, 2, 30, 4)], ["balanced", "comb"])
        variants = []
        a = copy.deepcopy(graph)
        a["ops"][chains[0][0][0]]["cycles"] += 1
        variants.append(a)
        b = copy.deepcopy(graph)
        b["ops"][chains[0][0][0]]["pipe"] = "PIPE_M"
        variants.append(b)
        c = copy.deepcopy(graph)
        c["edges"].append({"source": chains[0][0][0], "target": chains[0][1][1]})
        variants.append(c)
        d = copy.deepcopy(graph)
        d["edges"].append({"source": chains[0][0][0], "target": chains[0][1][0]})
        variants.append(d)
        for altered in variants:
            with self.subTest(kind=len(variants)):
                self.assertIsNone(guarded_stages(altered, 3)[0])
                plan, info = construct(altered, 3)
                self.assertIsNone(plan)
                self.assertEqual(info["selected"], "unsupported")


if __name__ == "__main__":
    unittest.main()
