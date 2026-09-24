"""Small original tensor/COPY stage graphs; static checks only, never E0."""
import json
import unittest

from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan, topo
from src.q3.stage_fork_join import construct, recognize
from src.q3.pipe_bound import analyze


def stage_graph(lanes=2, stages=2):
    """Power-of-two lanes with immutable inputs and original binary reductions."""
    if lanes < 2 or lanes & (lanes - 1):
        raise ValueError("fixture requires a power-of-two lane count")
    graph = {"ops": [], "tensors": [], "edges": []}
    next_op, next_tensor = 1, 1000

    def tensor(position, size):
        nonlocal next_tensor
        tid = next_tensor
        next_tensor += 1
        graph["tensors"].append({"id": tid, "pos": position, "size": size})
        return tid

    def operation(kind, pipe, cycles, inputs, output):
        nonlocal next_op
        oid = next_op
        next_op += 1
        graph["ops"].append({"id": oid, "op": kind, "pipe": pipe, "cycles": cycles})
        graph["edges"].extend({"source": tid, "target": oid} for tid in inputs)
        graph["edges"].append({"source": oid, "target": output})
        return oid

    immutable = []
    for _ in range(lanes):
        ddr, local = tensor("DDR", 64), tensor("L1", 64)
        operation("COPY_IN", "PIPE_MTE2", 0, [ddr], local)
        immutable.append(local)
    layout = {"immutable": immutable, "stages": []}
    previous_scalar = None
    for stage in range(stages):
        chains, scalars = [], []
        for lane in range(lanes):
            vector = tensor("UB", 64)
            inputs = [immutable[lane]] + ([] if previous_scalar is None else [previous_scalar])
            head = operation("RELU" if stage == 0 else "ADD", "PIPE_V", 20, inputs, vector)
            scalar = tensor("UB", 2)
            tail = operation("REDUCE", "PIPE_V", 20, [vector], scalar)
            chains.append([head, tail])
            scalars.append(scalar)
        level = list(scalars)
        joins = []
        while len(level) > 1:
            next_level = []
            for left, right in zip(level[::2], level[1::2]):
                output = tensor("UB", 2)
                joins.append(operation("ADD", "PIPE_V", 1, [left, right], output))
                next_level.append(output)
            level = next_level
        previous_scalar = level[0]
        layout["stages"].append({"chains": chains, "lane_scalars": scalars,
                                  "joins": joins, "root": joins[-1]})
    final_ddr = tensor("DDR", 2)
    operation("COPY_OUT", "PIPE_MTE3", 0, [previous_scalar], final_ddr)
    return graph, layout


def op_owners(plan):
    core_by_subgraph = {sg: c for c, seq in enumerate(plan["core_schedules"]) for sg in seq}
    return {int(u): core_by_subgraph[sg] for u, sg in plan["node_to_subgraph"].items()}


class StageForkJoinTests(unittest.TestCase):
    def test_two_stage_coverage_determinism_and_original_unchanged(self):
        graph, layout = stage_graph()
        before = json.dumps(graph, sort_keys=True)
        index = Index(graph)
        recognized = recognize(index)
        self.assertEqual(len(recognized["stages"]), 2)
        self.assertEqual(recognized["lane_ids"], layout["immutable"])
        for cores in (1, 2, 5):
            plan, meta = construct(index, cores)
            self.assertEqual((plan, meta), construct(index, cores))
            self.assertEqual((plan, meta), construct(index, cores, collector_policy="fixed"))
            self.assertEqual(meta["strategy"], "stage_fork_join")
            self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
            self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(index.ops))
            scheduled = [sg for seq in plan["core_schedules"] for sg in seq]
            self.assertEqual(len(scheduled), len(index.ops))
            self.assertEqual(set(scheduled), set(plan["node_to_subgraph"].values()))
            self.assertEqual(len(plan["core_schedules"]), cores)
            derive_multicore_plan(graph, plan)  # Official static format/coverage check, not E0.
            owner = op_owners(plan)
            for lane in range(2):
                lane_ops = [u for s in layout["stages"] for u in s["chains"][lane]]
                self.assertEqual(len({owner[u] for u in lane_ops}), 1)
            # Independently add the entire submitted core order, stronger than
            # checking only this fixture's per-Pipe order, and reject any cycle.
            inverse = {sg: int(u) for u, sg in plan["node_to_subgraph"].items()}
            adjacency = {u: set(index.succ[u]) for u in index.ops}
            for seq in plan["core_schedules"]:
                for a, b in zip(seq, seq[1:]):
                    adjacency[inverse[a]].add(inverse[b])
            self.assertEqual(len(topo(adjacency, adjacency)), len(index.ops))
        self.assertEqual(json.dumps(graph, sort_keys=True), before)

    def test_original_reduction_paths_have_at_most_one_cross_core_hop(self):
        # Four lanes give a nontrivial depth-two original tree. Three cores
        # create both pure and mixed ADD nodes without re-associating the tree.
        graph, layout = stage_graph(lanes=4)
        index = Index(graph)
        plan, _ = construct(index, 3)
        owner = op_owners(plan)
        for stage in layout["stages"]:
            for chain in stage["chains"]:
                u = chain[-1]
                hops = 0
                visited = set()
                while u != stage["root"]:
                    self.assertNotIn(u, visited)
                    visited.add(u)
                    self.assertEqual(len(index.succ[u]), 1)
                    v = next(iter(index.succ[u]))
                    self.assertIn(v, stage["joins"])
                    hops += owner[u] != owner[v]
                    u = v
                self.assertLessEqual(hops, 1)

    def test_extra_internal_tensor_input_is_rejected(self):
        graph, layout = stage_graph()
        tail = layout["stages"][0]["chains"][0][-1]
        graph["edges"].append({"source": layout["immutable"][1], "target": tail})
        # An extra immutable input adds no compute predecessor, so adjacency
        # recognition alone would miss it; the exact tensor-port guard must act.
        with self.assertRaisesRegex(UnsupportedStructure, "lane-internal tensor input"):
            construct(Index(graph), 2)

    def test_later_lane_input_replacement_is_rejected(self):
        graph, layout = stage_graph()
        head = layout["stages"][1]["chains"][0][0]
        for edge in graph["edges"]:
            if edge == {"source": layout["immutable"][0], "target": head}:
                edge["source"] = layout["immutable"][1]
                break
        else:
            self.fail("fixture lacks the later-stage immutable input edge")
        with self.assertRaisesRegex(UnsupportedStructure, "duplicate immutable lane input"):
            construct(Index(graph), 2)

    def test_ambiguous_tensor_producer_is_rejected(self):
        graph, layout = stage_graph()
        stage = layout["stages"][0]
        graph["edges"].append({"source": stage["chains"][1][-1],
                               "target": stage["lane_scalars"][0]})
        # Both producers already precede the same join; the original compute
        # graph stays acyclic, but this is no longer a uniquely produced lane.
        with self.assertRaisesRegex(UnsupportedStructure, "producer|one output tensor"):
            construct(Index(graph), 2)


    def test_rotate_heavy_keeps_lanes_and_original_tree_on_each_stage(self):
        graph, layout = stage_graph(lanes=8, stages=4)
        before = json.dumps(graph, sort_keys=True)
        index = Index(graph)
        rec = recognize(index)
        plan, meta = construct(index, 3, collector_policy="rotate_heavy")
        self.assertEqual((plan, meta), construct(index, 3, collector_policy="rotate_heavy"))
        self.assertEqual(meta["collector_cycle"], [0, 1])
        self.assertIsNone(meta["collector_core"])
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        owner = op_owners(plan)
        self.assertEqual(set(owner), set(index.ops))
        for lane in range(8):
            all_ops = [u for stage in layout["stages"] for u in stage["chains"][lane]]
            self.assertEqual(len({owner[u] for u in all_ops}), 1)
        for i, stage in enumerate(rec["stages"]):
            collector = i % 2
            self.assertEqual(owner[stage["root"]], collector)
            self.assertEqual(meta["stage_diagnostics"][i]["collector_core"], collector)
            for u in stage["join_order"]:
                lane_owners = {owner[stage["chains"][lane][-1]]
                               for lane in stage["descendants"][u]}
                expected = next(iter(lane_owners)) if len(lane_owners) == 1 else collector
                self.assertEqual(owner[u], expected)
            for chain in stage["chains"].values():
                u, hops = chain[-1], 0
                while u != stage["root"]:
                    v = next(iter(index.succ[u]))
                    hops += owner[u] != owner[v]
                    u = v
                self.assertLessEqual(hops, 1)
        derive_multicore_plan(graph, plan)
        analyze(graph, plan, 50)  # Independently reject any induced pipe-FIFO cycle.
        self.assertEqual(json.dumps(graph, sort_keys=True), before)

    def test_alternating_two_roots_hides_one_remote_leg(self):
        graph, _ = stage_graph(lanes=2, stages=4)
        index = Index(graph)
        fixed, _ = construct(index, 2)
        rotated, _ = construct(index, 2, collector_policy="rotate_heavy")
        # Lane work C=40, original scalar join a=1, remote delta=50.
        # Fixed: first C+delta+a, later C+2delta+a; rotated: C+delta+a.
        fixed_bound = analyze(graph, fixed, 50)["with_cross_core_delay"]["lower_bound_cycles"]
        rotated_bound = analyze(graph, rotated, 50)["with_cross_core_delay"]["lower_bound_cycles"]
        self.assertEqual(fixed_bound, 91 + 3 * 141)
        self.assertEqual(rotated_bound, 4 * 91)
        self.assertEqual(fixed_bound - rotated_bound, 3 * 50)

    def test_rotate_heavy_rejects_other_load_patterns_without_fallback(self):
        graph, _ = stage_graph(lanes=8)
        index = Index(graph)
        for cores in (1, 4, 5):
            with self.subTest(cores=cores):
                with self.assertRaisesRegex(UnsupportedStructure, "exactly two most-loaded"):
                    construct(index, cores, collector_policy="rotate_heavy")
        with self.assertRaisesRegex(ValueError, "collector_policy"):
            construct(index, 3, collector_policy="unknown")


if __name__ == "__main__":
    unittest.main()
