import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
from diagnose import lower_bounds


class BoundTests(unittest.TestCase):
    def graph(self):
        return {"ops": [{"id": 0, "op": "X", "pipe": "PIPE_M", "cycles": 3},
                        {"id": 1, "op": "X", "pipe": "PIPE_V", "cycles": 4}],
                "tensors": [{"id": 10, "pos": "UB", "size": 1}],
                "edges": [{"source": 0, "target": 10}, {"source": 10, "target": 1}]}

    def test_same_core_and_cross_core_gates(self):
        waits = {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000}
        for schedules, expected in (([[0, 1], []], 107), ([[0], [1]], 1007)):
            b = lower_bounds(self.graph(), {"node_to_subgraph": {0: 0, 1: 1}, "core_schedules": schedules}, waits)
            self.assertEqual(b["task_gate_lower_bound_cycles"], expected)
            self.assertEqual(b["witness_compute_cycles"] + b["witness_gate_cycles"], expected)

    def test_internal_dependency_cannot_overlap_different_pipes(self):
        b = lower_bounds(self.graph(), {"node_to_subgraph": {0: 0, 1: 0}, "core_schedules": [[0]]},
                         {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000})
        self.assertEqual(b["task_gate_lower_bound_cycles"], 7)
        self.assertEqual(b["global_pipe_work_lower_bound_cycles"], 4)

    def test_copy_bridge_is_removed_inside_task_but_gates_separate_tasks(self):
        graph = {"ops": [{"id": 0, "op": "X", "pipe": "PIPE_M", "cycles": 100},
                         {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 1},
                         {"id": 2, "op": "X", "pipe": "PIPE_V", "cycles": 100}],
                 "tensors": [{"id": 10, "pos": "UB", "size": 60},
                             {"id": 11, "pos": "UB", "size": 60}],
                 "edges": [{"source": 0, "target": 10}, {"source": 10, "target": 1},
                           {"source": 1, "target": 11}, {"source": 11, "target": 2}]}
        waits = {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000}
        for mapping, schedules, expected in (({0: 0, 2: 0}, [[0]], 100),
                                             ({0: 0, 2: 1}, [[0], [1]], 1200)):
            b = lower_bounds(graph, {"node_to_subgraph": mapping, "core_schedules": schedules}, waits)
            self.assertEqual(b["task_gate_lower_bound_cycles"], expected)

    def test_zero_cycle_compute_still_takes_one_cycle(self):
        graph = self.graph()
        for op in graph["ops"]:
            op["cycles"] = 0
        b = lower_bounds(graph, {"node_to_subgraph": {0: 0, 1: 0}, "core_schedules": [[0]]},
                         {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000})
        self.assertEqual(b["task_gate_lower_bound_cycles"], 2)

    def test_multiple_release_constraints_use_max_not_sum(self):
        waits = {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000}
        for costs, schedules, expected in (([5000, 1, 3], [[0, 2], [1]], 5103),
                                            ([50, 5000, 3], [[0, 2], [1]], 6003),
                                            ([5, 7, 11], [[0], [1], [2]], 1018)):
            graph = {"ops": [{"id": u, "op": "X", "pipe": "PIPE_V", "cycles": cost}
                             for u, cost in enumerate(costs)],
                     "tensors": [], "edges": [{"source": 0, "target": 2},
                                                {"source": 1, "target": 2}]}
            bound = lower_bounds(graph, {"node_to_subgraph": {0: 0, 1: 1, 2: 2},
                                          "core_schedules": schedules}, waits)
            self.assertEqual(bound["task_gate_lower_bound_cycles"], expected)


if __name__ == "__main__":
    unittest.main()
