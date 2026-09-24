"""Mathematical fixtures only: no solver, E0, E1 or E2 execution."""
import copy
import unittest

from src.q1.lower_bounds import lower_bounds


def op(ident, pipe, cycles, kind="COMPUTE"):
    return {"id": ident, "op": kind, "pipe": "PIPE_" + pipe, "cycles": cycles}


def tensor(ident, size=60, pos="UB"):
    return {"id": ident, "size": size, "pos": pos}


def graph(ops, tensors=(), edges=()):
    return {"ops": list(ops), "tensors": list(tensors),
            "edges": [{"source": a, "target": b} for a, b in edges]}


class LowerBoundTests(unittest.TestCase):
    def test_zero_cycles_still_occupy_one_cycle(self):
        r = lower_bounds(graph([op(1, "M", 0), op(2, "V", 0)]), 5, 60)
        self.assertEqual(r["compute_critical_path_cycles"], 1)
        self.assertEqual(r["pipe_resources"]["PIPE_M"]["work_cycles"], 1)
        self.assertEqual(r["lower_bound_cycles"], 1)

    def test_independent_work_and_serial_critical_path(self):
        independent = graph([op(i, "M", 10) for i in range(1, 5)])
        self.assertEqual(lower_bounds(independent, 2, 60)["lower_bound_cycles"], 20)
        serial = graph([op(1, "M", 10), op(2, "V", 20)], edges=[(1, 2)])
        r = lower_bounds(serial, 5, 60)
        self.assertEqual(r["pipe_load_bound_cycles"], 4)
        self.assertEqual(r["compute_critical_path_cycles"], 30)
        self.assertEqual(r["lower_bound_cycles"], 30)

    def test_release_and_tail_strengthen_workload(self):
        # One shared required read; two independent M10 jobs; separate writes.
        g = graph([op(1, "M", 10), op(2, "M", 10)],
                  [tensor(100), tensor(101), tensor(102)],
                  [(100, 1), (100, 2), (1, 101), (2, 102)])
        before = copy.deepcopy(g)
        r = lower_bounds(g, 1, 60)
        self.assertEqual(r["mandatory_input_tensors"], 1)
        self.assertEqual(r["mandatory_output_tensors"], 2)
        self.assertEqual(r["relaxed_critical_path_cycles"], 12)
        self.assertEqual(r["base_lower_bound_cycles"], 20)
        self.assertEqual(r["lower_bound_cycles"], 22)
        self.assertEqual(lower_bounds(g, 2, 60)["lower_bound_cycles"], 12)
        self.assertEqual(g, before)

    def test_ddr_global_capacity_and_per_copy_rounding(self):
        g = graph([op(1, "M", 1), op(2, "M", 1)],
                  [tensor(i, 121) for i in range(100, 104)],
                  [(100, 1), (101, 2), (1, 102), (2, 103)])
        r = lower_bounds(g, 2, 60)
        self.assertEqual(r["mandatory_ddr_service_bound_cycles"], 12)
        self.assertEqual(r["pipe_resources"]["PIPE_MTE2"]["load_bound_cycles"], 3)
        self.assertEqual(r["lower_bound_cycles"], 12)
        # 484 bytes / 60 rounded once would give only 9 cycles, not 12.
        self.assertEqual(r["mandatory_input_bytes"] + r["mandatory_output_bytes"], 484)

    def test_copy_bridge_must_not_create_operation_level_chain(self):
        # Original M100 -> COPY -> V100. In one P1 Task, COPY is removed:
        # M100 -> required write and required read -> V100 are separate paths.
        g = graph([op(1, "M", 100), op(2, "MTE2", 0, "COPY_IN"), op(3, "V", 100)],
                  [tensor(100), tensor(101)], [(1, 100), (100, 2), (2, 101), (101, 3)])
        r = lower_bounds(g, 1, 60)
        self.assertEqual(r["retained_compute_edges"], 0)
        self.assertEqual(r["compute_critical_path_cycles"], 100)
        self.assertEqual(r["relaxed_critical_path_cycles"], 101)
        self.assertEqual(r["lower_bound_cycles"], 101)
        self.assertFalse(r["proof_scope"]["copy_bridge_contraction"])

    def test_unconsumed_original_copy_is_not_mandatory_traffic(self):
        g = graph([op(1, "V", 1), op(2, "MTE2", 0, "COPY_IN")],
                  [tensor(100, 600000, "DDR"), tensor(101, 600000)], [(100, 2), (2, 101)])
        r = lower_bounds(g, 1, 60)
        self.assertEqual(r["mandatory_ddr_service_bound_cycles"], 0)
        self.assertEqual(r["lower_bound_cycles"], 1)

    def test_multi_producer_mandatory_output_release(self):
        g = graph([op(1, "M", 5), op(2, "V", 11)], [tensor(100)], [(1, 100), (2, 100)])
        r = lower_bounds(g, 5, 60)
        self.assertEqual(r["mandatory_output_tensors"], 1)
        self.assertEqual(r["ddr_resource"]["minimum_release_cycles"], 11)
        self.assertEqual(r["lower_bound_cycles"], 12)

    def test_explicit_domain_validation_and_no_calls(self):
        g = graph([op(1, "M", 1)])
        for k in (0, 6, True):
            with self.assertRaises(ValueError):
                lower_bounds(g, k, 60)
        for bw in (0, -1, True, 60.0):
            with self.assertRaises(ValueError):
                lower_bounds(g, 1, bw)
        with self.assertRaises(ValueError):
            lower_bounds(graph([op(1, "M", 1), op(2, "V", 1)], edges=[(1, 2), (2, 1)]), 1, 60)
        self.assertEqual(lower_bounds(g, 1, 60)["calls"], {"solver": 0, "E0": 0, "E1": 0, "E2": 0})


if __name__ == "__main__":
    unittest.main()
