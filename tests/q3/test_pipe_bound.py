"""Proof-boundary checks; no official simulation or benchmark calls."""
import unittest

from src.q3.pipe_bound import UnsupportedBound, analyze


def graph(nodes, edges=(), tensors=()):
    return {"ops": [{"id": u, "op": "COMPUTE", "pipe": pipe, "cycles": work}
                    for u, pipe, work in nodes],
            "tensors": list(tensors),
            "edges": [{"source": u, "target": v} for u, v in edges]}


def plan(sequences):
    return {"node_to_subgraph": {str(u): u for seq in sequences for u in seq},
            "core_schedules": sequences}


class PipeBoundTests(unittest.TestCase):
    def test_two_pipes_can_overlap_not_summed(self):
        g = graph([(1, "PIPE_M", 10), (2, "PIPE_V", 7), (3, "PIPE_M", 5)])
        b = analyze(g, plan([[1, 2, 3], []]))
        self.assertEqual(b["zero_delay"]["lower_bound_cycles"], 15)
        self.assertFalse(b["execution_legality_proved"])

    def test_graph_and_fifo_duplicate_edge_is_not_added_twice(self):
        g = graph([(1, "PIPE_M", 4), (2, "PIPE_M", 6)], [(1, 2)])
        b = analyze(g, plan([[1, 2]]), 500)
        self.assertEqual(b["augmented_edges"], 1)
        self.assertEqual(b["with_cross_core_delay"]["lower_bound_cycles"], 10)

    def test_tensor_and_direct_cross_edge_use_max_delay(self):
        g = graph([(1, "PIPE_M", 4), (2, "PIPE_V", 6)],
                  [(1, 100), (100, 2), (1, 2)],
                  [{"id": 100, "pos": "UB", "size": 64}])
        b = analyze(g, plan([[1], [2]]), 500)
        self.assertEqual(b["cross_core_dependency_edges"], 1)
        self.assertEqual(b["zero_delay"]["lower_bound_cycles"], 10)
        self.assertEqual(b["with_cross_core_delay"]["lower_bound_cycles"], 510)
        self.assertEqual(b["with_cross_core_delay"]["path_delay_cycles"], 500)

    def test_balanced_load_does_not_prevent_long_resource_path(self):
        # Each core has 20 work, but resource FIFO + dependency makes all 40 serial.
        g = graph([(u, "PIPE_M", 10) for u in (1, 2, 3, 4)], [(2, 3)])
        b = analyze(g, plan([[1, 2], [3, 4]]), 500)
        self.assertEqual(b["zero_delay"]["lower_bound_cycles"], 40)
        self.assertEqual(b["with_cross_core_delay"]["lower_bound_cycles"], 540)
        self.assertEqual([s["core"] for s in b["zero_delay"]["segments"]], [0, 1])

    def test_augmented_global_fifo_cycle_is_rejected(self):
        g = graph([(u, "PIPE_M", 1) for u in (1, 2, 3, 4)], [(1, 4), (3, 2)])
        with self.assertRaisesRegex(UnsupportedBound, "cycle"):
            analyze(g, plan([[2, 1], [4, 3]]))

    def test_multi_operation_subgraph_is_outside_proof(self):
        g = graph([(1, "PIPE_M", 2), (2, "PIPE_V", 3)])
        with self.assertRaisesRegex(UnsupportedBound, "one original"):
            analyze(g, {"node_to_subgraph": {"1": 0, "2": 0}, "core_schedules": [[0]]})

    def test_copy_bridge_is_not_assumed_to_be_a_p3_cross_link(self):
        g = graph([(1, "PIPE_M", 2), (2, "PIPE_V", 3)], [(1, 10), (10, 2)])
        g["ops"].append({"id": 10, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 1})
        with self.assertRaisesRegex(UnsupportedBound, "COPY contraction"):
            analyze(g, plan([[1], [2]]), 500)

    def test_external_input_copy_is_allowed_and_not_charged(self):
        g = graph([(1, "PIPE_M", 2)], [(10, 100), (100, 1)],
                  [{"id": 100, "pos": "UB", "size": 64}])
        g["ops"].append({"id": 10, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 100})
        b = analyze(g, plan([[1]]), 500)
        self.assertEqual(b["zero_delay"]["lower_bound_cycles"], 2)

    def test_unsupported_compute_pipe_and_invalid_delay(self):
        with self.assertRaisesRegex(UnsupportedBound, "PIPE_M/PIPE_V"):
            analyze(graph([(1, "PIPE_MTE2", 2)]), plan([[1]]))
        for delay in (-1, True, 0.5):
            with self.assertRaises(UnsupportedBound):
                analyze(graph([(1, "PIPE_M", 2)]), plan([[1]]), delay)

    def test_zero_work_uses_official_minimum_one_cycle(self):
        b = analyze(graph([(1, "PIPE_M", 0)]), plan([[1]]))
        self.assertEqual(b["zero_delay"]["lower_bound_cycles"], 1)


if __name__ == "__main__":
    unittest.main()
