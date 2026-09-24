"""Independent synthetic/static tests for stage migration; never run E0."""
from collections import Counter
import copy
import json
import unittest

from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan, topo
from src.q3.pipe_bound import analyze
from src.q3.stage_migration import construct


def stage_graph(stages=2, lanes=12, chain_length=4, vector=32768, scalar=2,
                cycles=524, add_cycles=13, tree_permutation=None):
    """Build actual COPY/tensor ports and an unchanged pairwise 8+4 tree."""
    graph = {"ops": [], "tensors": [], "edges": []}
    next_op, next_tensor = 1, 1_000_000

    def tensor(pos, size):
        nonlocal next_tensor
        tid = next_tensor
        next_tensor += 1
        graph["tensors"].append({"id": tid, "pos": pos, "size": size})
        return tid

    def operation(kind, pipe, work, inputs, output):
        nonlocal next_op
        oid = next_op
        next_op += 1
        graph["ops"].append({"id": oid, "op": kind, "pipe": pipe, "cycles": work})
        graph["edges"].extend({"source": tid, "target": oid} for tid in inputs)
        graph["edges"].append({"source": oid, "target": output})
        return oid

    immutable = []
    for _ in range(lanes):
        ddr, local = tensor("DDR", vector), tensor("L1", vector)
        operation("COPY_IN", "PIPE_MTE2", 0, [ddr], local)
        immutable.append(local)
    layout = {"immutable": immutable, "stages": []}
    previous_scalar = None
    for number in range(stages):
        chains, chain_outputs, scalars = [], [], []
        for lane in range(lanes):
            chain, outputs = [], []
            for j in range(chain_length):
                output = tensor("UB", scalar if j == chain_length - 1 else vector)
                if j == 0:
                    kind = "RELU" if number == 0 else "ADD"
                    inputs = [immutable[lane]] + ([] if previous_scalar is None else [previous_scalar])
                else:
                    kind = "REDUCE" if j == chain_length - 1 else "RELU"
                    inputs = [outputs[-1]]
                chain.append(operation(kind, "PIPE_V", cycles, inputs, output))
                outputs.append(output)
            chains.append(chain)
            chain_outputs.append(outputs)
            scalars.append(outputs[-1])
        permutation = list(range(lanes)) if tree_permutation is None else tree_permutation
        level = [scalars[lane] for lane in permutation]
        joins, join_outputs = [], []
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level) - 1, 2):
                output = tensor("UB", scalar)
                joins.append(operation("ADD", "PIPE_V", add_cycles, level[i:i + 2], output))
                join_outputs.append(output)
                next_level.append(output)
            if len(level) % 2:
                next_level.append(level[-1])
            level = next_level
        previous_scalar = level[0]
        layout["stages"].append({"chains": chains, "chain_outputs": chain_outputs,
                                 "joins": joins, "root": joins[-1],
                                 "root_tensor": previous_scalar, "join_outputs": join_outputs})
    final_ddr = tensor("DDR", scalar)
    operation("COPY_OUT", "PIPE_MTE3", 0, [previous_scalar], final_ddr)
    return graph, layout


def inspect_plan(index, plan, delay=500):
    """Independent max-plus timing of original edges plus the ENTIRE core word."""
    inverse = {sg: int(u) for u, sg in plan["node_to_subgraph"].items()}
    words = [[inverse[sg] for sg in word] for word in plan["core_schedules"]]
    owner = {u: c for c, word in enumerate(words) for u in word}
    edges = {u: {v: delay if owner[u] != owner[v] else 0 for v in index.succ[u]}
             for u in index.ops}
    for word in words:
        for u, v in zip(word, word[1:]):
            edges[u][v] = max(edges[u].get(v, 0), 0)
    order = topo(index.ops, edges)
    start = dict.fromkeys(index.ops, 0)
    finish = {}
    for u in order:
        finish[u] = start[u] + index.ops[u]["cycles"]
        for v, lag in edges[u].items():
            start[v] = max(start[v], finish[u] + lag)
    return owner, words, finish


class StageMigrationTests(unittest.TestCase):
    def test_coverage_original_unchanged_and_augmented_timing(self):
        for stages in (1, 2, 4):
            graph, layout = stage_graph(stages=stages)
            before = json.dumps(graph, sort_keys=True)
            index = Index(graph)
            for mode in ("single_cut", "two_cut"):
                with self.subTest(stages=stages, mode=mode):
                    plan, meta = construct(index, 5, mode)
                    self.assertEqual((plan, meta), construct(index, 5, mode))
                    self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
                    self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(index.ops))
                    owner, words, finish = inspect_plan(index, plan)
                    self.assertEqual(Counter(u for word in words for u in word), Counter(index.ops.keys()))
                    self.assertEqual(len(plan["core_schedules"]), 5)
                    self.assertEqual(len(set(plan["node_to_subgraph"].values())), len(index.ops))
                    derive_multicore_plan(graph, plan)
                    expected = 6379 * stages if mode == "single_cut" else 6279 * stages - 500
                    self.assertEqual(max(finish.values()), expected)
                    self.assertEqual(meta["compute_plus_500_bound"], expected)
                    self.assertEqual(meta["compute_model_template_cycles"], expected)
                    independent = analyze(graph, plan, 500)
                    self.assertEqual(independent["with_cross_core_delay"]["lower_bound_cycles"], expected)
                    self.assertEqual(meta["zero_delay_bound"], independent["zero_delay"]["lower_bound_cycles"])
                    self.assertLessEqual(meta["zero_delay_bound"], expected)
                    self.assertEqual(meta["official_e0_calls"], 0)
                    self.assertFalse(meta["official_execution_feasibility_proved"])
                    self.assertFalse(meta["global_official_optimality_claimed"])
                    stage_of = {u: i for i, st in enumerate(layout["stages"])
                                for u in st["joins"] + [v for ch in st["chains"] for v in ch]}
                    for word in words:
                        self.assertEqual([stage_of[u] for u in word], sorted(stage_of[u] for u in word))
                    root_ends = [finish[st["root"]] for st in layout["stages"]]
                    first, interval = (6379, 6379) if mode == "single_cut" else (5779, 6279)
                    self.assertEqual(root_ends, [first + i * interval for i in range(stages)])
            self.assertEqual(json.dumps(graph, sort_keys=True), before)

    def test_exact_cuts_and_head_vs_leaf_ownership(self):
        graph, layout = stage_graph(stages=3)
        index = Index(graph)
        for mode in ("single_cut", "two_cut"):
            plan, meta = construct(index, 5, mode)
            owner, _, _ = inspect_plan(index, plan)
            observed = []
            for number, stage in enumerate(layout["stages"]):
                for lane, chain in enumerate(stage["chains"]):
                    for j, (u, v) in enumerate(zip(chain, chain[1:])):
                        if owner[u] != owner[v]:
                            observed.append((number + 1, lane, j, u, v))
                wanted_collector = 2 if mode == "single_cut" else 1 - number % 2
                self.assertEqual(owner[stage["root"]], wanted_collector)
                self.assertEqual(meta["collector_sequence"][number], wanted_collector)
                if mode == "single_cut":
                    # J1 consumes migrated lane 2 and lane 3, both finishing on
                    # core 1. Using lane-head ownership would wrongly place it.
                    self.assertEqual(owner[stage["joins"][1]], 1)
                    self.assertEqual(owner[stage["chains"][2][0]], 0)
                    self.assertEqual(owner[stage["chains"][2][-1]], 1)
                else:
                    # First-stage original J5 has a unique boundary placement.
                    self.assertEqual(owner[stage["joins"][5]], 0 if number == 0 else wanted_collector)
                    if number > 0:
                        self.assertTrue(all(owner[u] == wanted_collector for u in stage["joins"]))
            target_lanes = (2,) if mode == "single_cut" else (2, 9)
            self.assertEqual([(s, lane, j) for s, lane, j, _, _ in observed],
                             [(s, lane, 1) for s in range(1, 4) for lane in target_lanes])
            self.assertEqual([(e["stage"], e["lane_slot"], e["source_op"], e["target_op"])
                              for e in meta["large_vector_migration_edges"]],
                             [(s, lane, u, v) for s, lane, _, u, v in observed])
            self.assertEqual(meta["large_vector_migrations"], 3 * len(target_lanes))

    def test_op_id_tie_breaks_do_not_change_template(self):
        graph, _ = stage_graph(stages=3)
        original = Index(graph)
        # Reverse op IDs globally, preserving tensor IDs/immutable lane order.
        # This reverses independent ADD tie breaks but not original edges.
        transformed = copy.deepcopy(graph)
        last = max(o["id"] for o in transformed["ops"])
        reid = {o["id"]: last + 1 - o["id"] for o in transformed["ops"]}
        for op in transformed["ops"]:
            op["id"] = reid[op["id"]]
        for edge in transformed["edges"]:
            for endpoint in ("source", "target"):
                edge[endpoint] = reid.get(edge[endpoint], edge[endpoint])
        transformed["ops"].reverse()
        transformed["edges"].reverse()
        changed = Index(transformed)
        for mode in ("single_cut", "two_cut"):
            before, before_meta = construct(original, 5, mode)
            after, after_meta = construct(changed, 5, mode)
            _, before_words, _ = inspect_plan(original, before)
            _, after_words, _ = inspect_plan(changed, after)
            self.assertEqual(after_words, [[reid[u] for u in word] for word in before_words])
            self.assertEqual(after_meta["compute_plus_500_bound"], before_meta["compute_plus_500_bound"])

    def test_guard_rejects_nearby_families_without_fallback(self):
        for kwargs in ({"lanes": 8}, {"chain_length": 3}, {"cycles": 525},
                       {"add_cycles": 12}, {"vector": 16384}, {"scalar": 4}):
            with self.subTest(kwargs=kwargs):
                graph, _ = stage_graph(**kwargs)
                for mode in ("single_cut", "two_cut"):
                    with self.assertRaises(UnsupportedStructure):
                        construct(Index(graph), 5, mode)
        permutation = list(range(12))
        permutation[1], permutation[2] = permutation[2], permutation[1]
        graph, _ = stage_graph(tree_permutation=permutation)
        with self.assertRaisesRegex(UnsupportedStructure, "8\\+4 tree"):
            construct(Index(graph), 5)

    def test_raw_tensor_extra_port_rejected(self):
        graph, layout = stage_graph()
        # No new compute predecessor: an adjacency-only recognizer misses it.
        graph["edges"].append({"source": layout["immutable"][1],
                               "target": layout["stages"][0]["chains"][0][2]})
        with self.assertRaisesRegex(UnsupportedStructure, "lane-internal tensor input"):
            construct(Index(graph), 5)

    def test_broadcast_stage_boundary_rejected(self):
        graph, layout = stage_graph(stages=3)
        head = layout["stages"][2]["chains"][0][0]
        old_root = layout["stages"][1]["root_tensor"]
        for edge in graph["edges"]:
            if edge == {"source": old_root, "target": head}:
                edge["source"] = layout["stages"][0]["root_tensor"]
                break
        else:
            self.fail("fixture lacks a stage broadcast")
        with self.assertRaises(UnsupportedStructure):
            construct(Index(graph), 5)

    def test_homogeneous_but_different_original_op_kind_rejected(self):
        graph, layout = stage_graph()
        middle = {chain[1] for st in layout["stages"] for chain in st["chains"]}
        for op in graph["ops"]:
            if op["id"] in middle:
                op["op"] = "EXP"
        with self.assertRaisesRegex(UnsupportedStructure, "signature"):
            construct(Index(graph), 5)

    def test_original_copy_signature_rejected(self):
        for field, value in (("cycles", 1), ("pipe", "PIPE_MTE3")):
            graph, _ = stage_graph()
            graph["ops"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(UnsupportedStructure, "zero-cycle COPY"):
                    construct(Index(graph), 5)

    def test_explicit_configuration_only(self):
        graph, _ = stage_graph()
        index = Index(graph)
        for cores in (1, 4, 6, True, 5.0):
            with self.subTest(cores=cores):
                with self.assertRaisesRegex(UnsupportedStructure, "five-core"):
                    construct(index, cores)
        for delay in (0, 499, 501, 500.0, True):
            with self.subTest(delay=delay):
                with self.assertRaisesRegex(UnsupportedStructure, "500-cycle"):
                    construct(index, 5, cross_core_delay_cycles=delay)
        with self.assertRaisesRegex(ValueError, "mode"):
            construct(index, 5, "two_cut_optimal")


if __name__ == "__main__":
    unittest.main()
