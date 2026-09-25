"""Static bridge relocation tests; no Task compiler or evaluator calls."""
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from src.q1 import branch_aid
from src.q1.general_bridge_probe import (
    _data_edges, _peak, _queue_projection, _queue_screen, construct)


def op(ident, cycles, pipe="PIPE_M"):
    return {"id": ident, "op": "ADD", "pipe": pipe, "cycles": cycles}


def edge(a, b):
    return {"source": a, "target": b}


class GeneralBridgeTests(unittest.TestCase):
    def test_idle_helper_and_same_height_core_order(self):
        graph = {"ops": [op(1, 12), op(2, 12), op(3, 1, "PIPE_V"),
                         op(4, 1)], "tensors": [],
                 "edges": [edge(1, 3), edge(2, 3)]}
        base = {"node_to_subgraph": {1: 0, 2: 0, 3: 0, 4: 1},
                "core_schedules": [[0, 1], []]}
        old, old_info = branch_aid.construct(graph, 2, base)
        self.assertEqual(old, base)
        self.assertIn("strictly advance Task height", old_info["reason"])
        plan, info = construct(graph, 2, base)
        self.assertEqual(plan, base)
        self.assertEqual(info["status"], "unsupported")
        self.assertEqual(info["census"]["old_tasks"], 2)
        self.assertEqual(info["census"]["acyclic_insertion_slots"], 1)
        self.assertEqual(info["census"]["queue_rejected_slots"], 1)
        self.assertEqual(info["scoring_calls"], {"E1": 0, "E0": 0, "E2": 0})
        branch_aid.validate_task_order(branch_aid.derive_multicore_plan(graph, plan))
        self.assertEqual(base["core_schedules"], [[0, 1], []])

    def test_helper_slot_after_required_predecessor(self):
        # Task 1 -> donor Task 0; exported X contains op 1, so X cannot
        # precede Task 1 on its helper. Donor also has two same-height Tasks.
        graph = {"ops": [op(1, 4), op(2, 12), op(3, 1, "PIPE_V"),
                         op(4, 1), op(5, 1)], "tensors": [],
                 "edges": [edge(1, 3), edge(2, 3), edge(4, 1)]}
        base = {"node_to_subgraph": {1: 0, 2: 0, 3: 0, 4: 1, 5: 2},
                "core_schedules": [[0, 2], [1]]}
        plan, info = construct(graph, 2, base)
        self.assertEqual(plan, base)
        self.assertEqual(info["census"]["acyclic_insertion_slots"], 1)
        self.assertEqual(info["census"]["queue_rejected_slots"], 1)
        branch_aid.validate_task_order(branch_aid.derive_multicore_plan(graph, plan))

    def test_frozen_068_bad_helper_slot_rejected_without_scorer(self):
        root = Path(__file__).resolve().parents[2]
        result = root / "results/a/p1-general-bridge-probe-20260926"
        graph = json.loads((result / "runs/20260925T180611Z-068-k5/068-k5/case_068.json").read_text())
        baseline = json.loads((root / "results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500/cells/068-k5/originals/plan.json").read_text())
        bad = json.loads((result / "068-k5/candidate-plan.json").read_text())
        ops = {op["id"]: op for op in graph["ops"] if op["op"] not in branch_aid.COPY}
        _, full_succ = branch_aid._build_op_adjacency(graph)
        _, succ = branch_aid._contract_excluded_copy_nodes(sorted(ops), full_succ)

        def projection(plan):
            view = branch_aid.derive_multicore_plan(graph, plan)
            tasks = set(view["subgraph_ids"])
            edges = _data_edges(view["mapping"], succ, tasks)
            durations = {task: _peak(branch_aid._work(view["nodes_by_subgraph"][task], ops))
                         for task in tasks}
            orders = [view["core_orders"][core] for core in range(5)]
            return _queue_projection(edges, orders, durations, 100, 1000)

        base_queue, bad_queue = projection(baseline), projection(bad)
        accepted, delay, slack = _queue_screen(base_queue, bad_queue, 42)
        self.assertFalse(accepted)
        self.assertEqual(bad["core_schedules"][4][5], 62)
        self.assertEqual(delay, 8848)
        self.assertGreater(delay, slack)
        self.assertEqual(base_queue["starts"][42], 52402)
        self.assertEqual(bad_queue["starts"][42], 61250)
        with patch("subprocess.run", side_effect=AssertionError("scorer launched")), \
             patch("subprocess.Popen", side_effect=AssertionError("scorer launched")):
            plan, info = construct(graph, 5, baseline)
        self.assertEqual(info["scoring_calls"], {"E1": 0, "E0": 0, "E2": 0})
        self.assertGreater(info["census"]["queue_rejected_slots"], 0)
        self.assertNotEqual(plan, bad)

    def test_no_witness_keeps_exact_baseline(self):
        graph = {"ops": [op(1, 2), op(2, 2)], "tensors": [], "edges": []}
        base = {"node_to_subgraph": {1: 0, 2: 1},
                "core_schedules": [[0], [1]]}
        plan, info = construct(graph, 2, base)
        self.assertEqual(plan, base)
        self.assertEqual(info["status"], "unsupported")
        self.assertEqual(info["census"]["bridge_witnessed_tasks"], 0)


if __name__ == "__main__":
    unittest.main()
