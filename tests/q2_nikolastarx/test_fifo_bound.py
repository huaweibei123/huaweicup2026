"""Hand-verifiable fixed-order relaxations. No solver or evaluator calls."""
import copy
import itertools
import unittest

from src.q2_nikolastarx.fifo_bound import fixed_fifo_lower_bound


def op(ident, pipe="PIPE_M", cycles=1, kind="COMPUTE"):
    return {"id": ident, "op": kind, "pipe": pipe, "cycles": cycles}


def graph(ops, pairs=(), tensors=()):
    return {"ops": ops, "tensors": list(tensors),
            "edges": [{"source": a, "target": b} for a, b in pairs]}


def plan(*sequences):
    return {"node_to_subgraph": {str(u): u for seq in sequences for u in seq},
            "core_schedules": [list(seq) for seq in sequences]}


class FixedFifoBoundTests(unittest.TestCase):
    def test_cross_pipe_chain_stronger_than_assigned_work(self):
        g = graph([op(0, cycles=5), op(1, "PIPE_V", 7), op(2, cycles=3)],
                  [(0, 1), (1, 2)])
        r = fixed_fifo_lower_bound(g, plan([0, 1, 2]))
        self.assertTrue(r["supported"])
        self.assertEqual(r["makespan_lower_bound_cycles"], 15)
        self.assertEqual(r["assigned_pipe_work_lower_bound_cycles"], 8)
        self.assertEqual([x["op_id"] for x in r["critical_path"]], [0, 1, 2])
        self.assertFalse(r["official_execution_validated"])

    def test_fixed_fifo_can_change_bound_with_same_assignment(self):
        g = graph([op(0, cycles=5), op(1, "PIPE_V", 7), op(2, cycles=3)], [(0, 1)])
        front = fixed_fifo_lower_bound(g, plan([2, 0, 1]))
        back = fixed_fifo_lower_bound(g, plan([0, 1, 2]))
        self.assertEqual(front["makespan_lower_bound_cycles"], 15)
        self.assertEqual(back["makespan_lower_bound_cycles"], 12)
        self.assertEqual(front["critical_path_edges"][0]["reasons"], ["fixed_compute_fifo"])
        self.assertEqual(front["assigned_pipe_work_lower_bound_cycles"],
                         back["assigned_pipe_work_lower_bound_cycles"])

    def test_different_pipe_total_order_is_not_an_execution_edge(self):
        g = graph([op(0, cycles=5), op(1, "PIPE_V", 7)])
        r = fixed_fifo_lower_bound(g, plan([0, 1]))
        self.assertEqual(r["makespan_lower_bound_cycles"], 7)
        self.assertEqual(r["reconstruction_guard"]["fifo_adjacent_edge_count"], 0)

    def test_cross_core_tensor_and_direct_dependencies_are_retained(self):
        g = graph([op(0, cycles=5), op(1, "PIPE_V", 7), op(2, cycles=3)],
                  [(0, 10), (10, 1), (1, 2)],
                  [{"id": 10, "pos": "DDR", "size": 8}])
        r = fixed_fifo_lower_bound(g, plan([0, 2], [1]))
        self.assertTrue(r["supported"])
        self.assertEqual(r["makespan_lower_bound_cycles"], 15)
        self.assertEqual(r["critical_path_edges"][0]["reasons"], ["original_tensor"])
        self.assertEqual(r["critical_path_edges"][1]["reasons"], ["original_direct"])

    def test_removed_copy_contraction_is_not_a_timing_dependency(self):
        # Source-level counterexample: P2 drops both original direct edges.
        # This is a semantic fixture, not a measured official-case score.
        g = graph([op(0, cycles=10), op(1, "PIPE_MTE3", 1, "COPY_OUT"),
                   op(2, "PIPE_V", 10)], [(0, 1), (1, 2)])
        r = fixed_fifo_lower_bound(g, plan([0, 2]))
        self.assertTrue(r["supported"])
        self.assertEqual(r["makespan_lower_bound_cycles"], 10)
        guard = r["reconstruction_guard"]
        self.assertEqual(guard["d_val_edge_count"], 1)
        self.assertEqual(guard["d_exec_edge_count"], 0)
        self.assertEqual(guard["omitted_copy_contraction_edge_examples"], [[0, 2]])

    def test_multiple_eligible_tensor_producers_abstains(self):
        g = graph([op(0), op(1), op(2)], [(0, 10), (1, 10), (10, 2)],
                  [{"id": 10, "pos": "UB", "size": 8}])
        r = fixed_fifo_lower_bound(g, plan([0, 1, 2]))
        self.assertFalse(r["supported"])
        self.assertEqual(r["reason_code"], "multiple_eligible_tensor_producers")
        self.assertIsNone(r["makespan_lower_bound_cycles"])

    def test_original_copy_producer_is_excluded_from_reconstruction_guard(self):
        g = graph([op(0, "PIPE_MTE2", 100, "COPY_IN"), op(1, cycles=5),
                   op(2, "PIPE_V", 7)], [(0, 10), (1, 10), (10, 2)],
                  [{"id": 10, "pos": "UB", "size": 8}])
        r = fixed_fifo_lower_bound(g, plan([1], [2]))
        self.assertTrue(r["supported"])
        self.assertEqual(r["makespan_lower_bound_cycles"], 12)
        self.assertEqual(r["reconstruction_guard"]["d_exec_edge_count"], 1)
        # A graph-input tensor has no eligible producer; it adds no compute
        # precedence or original COPY duration to this relaxed certificate.
        external = graph([op(0, "PIPE_MTE2", 100, "COPY_IN"), op(1, cycles=5)],
                         [(0, 10), (10, 1)], [{"id": 10, "pos": "UB", "size": 8}])
        r = fixed_fifo_lower_bound(external, plan([1]))
        self.assertTrue(r["supported"])
        self.assertEqual(r["makespan_lower_bound_cycles"], 5)
        self.assertEqual(r["reconstruction_guard"]["d_exec_edge_count"], 0)

    def test_non_singleton_abstains(self):
        g = graph([op(0), op(1)])
        p = {"node_to_subgraph": {"0": 0, "1": 0}, "core_schedules": [[0]]}
        r = fixed_fifo_lower_bound(g, p)
        self.assertEqual(r["reason_code"], "non_singleton_plan")

    def test_global_compute_fifo_cycle_abstains(self):
        # Each local order passes the plan validator; their FIFO edges close
        # a cycle with the two cross-core original dependencies.
        g = graph([op(i) for i in range(4)], [(0, 1), (2, 3)])
        r = fixed_fifo_lower_bound(g, plan([3, 0], [1, 2]))
        self.assertEqual(r["reason_code"], "cyclic_fixed_compute_graph")
        self.assertEqual(r["reconstruction_guard"]["unresolved_op_ids"], [0, 1, 2, 3])
        self.assertIsNone(r["makespan_lower_bound_cycles"])

    def test_invalid_plan_or_graph_abstains(self):
        g = graph([op(0), op(1)])
        for p in (None, plan([0]), plan([0, 1], [0]),
                  {"node_to_subgraph": {"0": 0, "1": 1}, "core_schedules": {0: [0, 1]}},
                  {"node_to_subgraph": {"0": 0, "1": 1}, "core_schedules": [[0, 2]]}):
            with self.subTest(plan=p):
                r = fixed_fifo_lower_bound(g, p)
                self.assertEqual(r["reason_code"], "invalid_plan_structure")
        for cycles in (0.5, True, -1):
            with self.subTest(cycles=cycles):
                r = fixed_fifo_lower_bound(graph([op(0, cycles=cycles)]), plan([0]))
                self.assertEqual(r["reason_code"], "invalid_or_unindexable_graph")
        missing_type = op(0)
        del missing_type["op"]
        self.assertFalse(fixed_fifo_lower_bound(graph([missing_type]), plan([0]))["supported"])

    def test_zero_cycles_mte_compute_and_empty_plan(self):
        g = graph([op(0, "PIPE_MTE2", 0), op(1, "PIPE_MTE2", 3)])
        r = fixed_fifo_lower_bound(g, plan([0, 1]))
        self.assertEqual(r["makespan_lower_bound_cycles"], 4)
        self.assertEqual(sum(x["duration_cycles"] for x in r["critical_path"]), 4)
        empty = fixed_fifo_lower_bound(graph([]), plan([]))
        self.assertTrue(empty["supported"])
        self.assertEqual(empty["makespan_lower_bound_cycles"], 0)
        self.assertEqual(empty["critical_path"], [])

    def test_deterministic_witness_and_input_not_mutated(self):
        g = graph([op(0, cycles=5), op(1, "PIPE_V", 5), op(2)], [(0, 2), (1, 2)])
        p = plan([0, 1, 2])
        originals = copy.deepcopy((g, p))
        first = fixed_fifo_lower_bound(g, p)
        self.assertEqual((g, p), originals)
        shuffled = copy.deepcopy(g)
        shuffled["ops"].reverse()
        shuffled["edges"].reverse()
        self.assertEqual(first, fixed_fifo_lower_bound(shuffled, p))
        self.assertEqual([x["op_id"] for x in first["critical_path"]], [0, 2])
        int_keys = copy.deepcopy(p)
        int_keys["node_to_subgraph"] = {int(u): v for u, v in p["node_to_subgraph"].items()}
        self.assertEqual(first, fixed_fifo_lower_bound(g, int_keys))

    def test_below_all_small_feasible_integer_timelines(self):
        # Independently enumerate integer start times for three operations.
        # Candidate order fixes M: 2 -> 0, and data fixes 0 -> 1 on V.
        # This only tests the relaxed fixed-order model, not COPY/capacity.
        g = graph([op(0, cycles=2), op(1, "PIPE_V", 3), op(2, cycles=1)], [(0, 1)])
        lower = fixed_fifo_lower_bound(g, plan([2, 0, 1]))["makespan_lower_bound_cycles"]
        feasible = []
        for start in itertools.product(range(9), repeat=3):
            if start[0] >= start[2] + 1 and start[1] >= start[0] + 2:
                feasible.append(max(start[u] + d for u, d in enumerate((2, 3, 1))))
        self.assertTrue(feasible)
        self.assertLessEqual(lower, min(feasible))
        self.assertEqual(lower, 6)


if __name__ == "__main__":
    unittest.main()
