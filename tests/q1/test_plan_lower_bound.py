"""Hand-computed P1 fixed-plan bounds; no official evaluator calls."""
import copy
import unittest

from src.q1.plan_lower_bound import plan_lower_bound


def op(ident, pipe="PIPE_V", cycles=1, kind="RELU"):
    return {"id": ident, "op": kind, "pipe": pipe, "cycles": cycles}


def graph(ops, tensors=(), edges=()):
    return {"ops": ops,
            "tensors": [{"id": ident, "size": size, "pos": "UB"}
                        for ident, size in tensors],
            "edges": [{"source": a, "target": b} for a, b in edges]}


def plan(mapping, schedules):
    return {"node_to_subgraph": mapping, "core_schedules": schedules}


class PlanLowerBoundTests(unittest.TestCase):
    def test_one_task_overlapping_pipes_and_unchanged_inputs(self):
        g = graph([op(1, "PIPE_M", 7), op(2, "PIPE_V", 11)])
        p = plan({1: 0, 2: 0}, [[0]])
        before = copy.deepcopy((g, p))
        result = plan_lower_bound(g, p, 8, 3, 5)
        self.assertEqual((result["bound"], result["task_dag"], result["mandatory_ddr"]),
                         (11, 11, 0))
        self.assertEqual((g, p), before)

    def test_same_and_cross_gates_and_duplicate_dependency(self):
        g = graph([op(1, cycles=2), op(2, cycles=3), op(3, cycles=4)],
                  [(101, 8)], [(1, 101), (101, 2)])
        p = plan({1: 0, 2: 1, 3: 2}, [[0, 1], [2]])
        result = plan_lower_bound(g, p, 8, 5, 7)
        # Task 0 writes once (1); Task 1 reads once (1), so durations
        # 2, 3 and 4. The 0->1 dependency and core-order wait overlap.
        self.assertEqual(result["task_dag"], 10)
        self.assertEqual(result["mandatory_ddr"], 2)
        g["edges"].append({"source": 101, "target": 3})
        result = plan_lower_bound(g, p, 8, 5, 7)
        self.assertEqual(result["tasks"][2]["earliest_start_bound"], 9)
        self.assertEqual(result["task_dag"], 13)

    def test_shared_input_once_per_task_and_copy_pipe_addition(self):
        g = graph([op(1, "PIPE_MTE2", 4), op(2), op(3)],
                  [(101, 16)], [(101, 1), (101, 2), (101, 3)])
        p = plan({1: 0, 2: 0, 3: 1}, [[0, 1]])
        result = plan_lower_bound(g, p, 8, 0, 0)
        self.assertEqual(result["mandatory_ddr"], 4)
        self.assertEqual(result["tasks"][0]["copy_in_tensors"], [101])
        self.assertEqual(result["tasks"][0]["pipe_work"]["PIPE_MTE2"], 6)

    def test_multiple_producers_and_original_copy_bridge(self):
        g = graph([op(1), op(2), op(3), op(4, kind="COPY_OUT")],
                  [(101, 8), (102, 8)],
                  [(1, 101), (2, 101), (101, 3), (3, 102), (102, 4)])
        p = plan({1: 0, 2: 0, 3: 1}, [[0], [1]])
        result = plan_lower_bound(g, p, 8, 0, 0)
        self.assertEqual(result["tasks"][0]["copy_out_tensors"], [101])
        self.assertEqual(result["tasks"][1]["copy_in_tensors"], [101])
        self.assertEqual(result["tasks"][1]["copy_out_tensors"], [102])
        self.assertEqual(result["mandatory_ddr"], 3)
        self.assertEqual(result["task_dag"], 4)

    def test_copy_bridge_contracts_to_task_dependency(self):
        g = graph([op(1), op(2, kind="COPY_IN"), op(3)],
                  [(101, 8), (102, 8)],
                  [(1, 101), (101, 2), (2, 102), (102, 3)])
        p = plan({1: 0, 3: 1}, [[0], [1]])
        result = plan_lower_bound(g, p, 8, 0, 4)
        self.assertEqual(result["task_dag"], 6)
        self.assertEqual(result["mandatory_ddr"], 2)

    def test_copy_bridge_inside_task_does_not_serialize_compute_pipes(self):
        g = graph([op(1, "PIPE_M", 100), op(2, kind="COPY_IN"),
                   op(3, "PIPE_V", 100)], [(101, 8), (102, 8)],
                  [(1, 101), (101, 2), (2, 102), (102, 3)])
        result = plan_lower_bound(g, plan({1: 0, 3: 0}, [[0]]), 8, 7, 11)
        self.assertEqual(result["bound"], 100)
        self.assertEqual(result["mandatory_ddr"], 2)

    def test_augmented_cycle_and_parameter_domain(self):
        g = graph([op(1), op(2), op(3)], edges=[(1, 3)])
        p = plan({1: 0, 2: 1, 3: 2}, [[2, 1], [0]])
        # 0->2 dependency plus 2->1 order is acyclic; add 1->0.
        g["edges"].append({"source": 2, "target": 1})
        with self.assertRaisesRegex(ValueError, "augmented Task schedule"):
            plan_lower_bound(g, p, 8, 0, 0)
        for args in [(0, 0, 0), (True, 0, 0), (8, -1, 0), (8, 0, True)]:
            with self.assertRaises(ValueError):
                plan_lower_bound(g, p, *args)


if __name__ == "__main__":
    unittest.main()
