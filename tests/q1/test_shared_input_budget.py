"""Synthetic graph contracts only; no real case constructors or E0/E1/E2."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.q1 import shared_input_budget as method
from src.q1.bounded_tasks import construct as bounded
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order
from tests.q1.test_component_pack import graph


def shared_chains(n=4, cycles=100, size=60000):
    ids = [[10 * c + 2, 10 * c + 1] for c in range(n)]
    g = graph([(u, "M", cycles) for chain in ids for u in chain], ids)
    g["tensors"].extend({"id": t, "size": size, "pos": "L1"} for t in (900, 901))
    g["edges"].extend({"source": 900 + i, "target": chain[i]}
                      for chain in ids for i in range(2))
    return g


class SharedInputBudgetTests(unittest.TestCase):
    def test_bandwidth_dominated_selects_one_active_core_and_still_windows(self):
        g = shared_chains()
        untouched = copy.deepcopy(g)
        with patch.object(method, "bounded_construct", wraps=bounded) as base:
            plan, info = method.construct(g, 4, input_budget_bytes=60000, activation_bytes=60000)
        self.assertEqual(base.call_count, 1)
        self.assertEqual(base.call_args.args[1], 1)
        self.assertEqual(info["active_cores"], 1)
        self.assertEqual(len(info["configurations"]), 4)
        self.assertEqual(len(plan["core_schedules"][0]), 2)
        self.assertEqual(plan["core_schedules"][1:], [[], [], []])
        self.assertEqual(list(plan["node_to_subgraph"]), [o["id"] for o in g["ops"]])
        self.assertEqual(g, untouched)
        self.assertEqual(info["chosen_configuration"]["input_copy_proxy_bytes"], 120000)
        validate_task_order(derive_multicore_plan(g, plan))

    def test_compute_dominated_keeps_cores_with_same_shared_inputs(self):
        plan, info = method.construct(shared_chains(cycles=100000), 4,
                                     input_budget_bytes=60000, activation_bytes=60000)
        self.assertEqual(info["active_cores"], 4)
        self.assertEqual([len(order) for order in plan["core_schedules"]], [2] * 4)
        self.assertEqual(info["chosen_configuration"]["input_copy_proxy_bytes"], 480000)
        self.assertEqual(info["chosen_configuration"]["internal_boundary_copy_proxy_bytes"], 512)
        self.assertEqual(info["chosen_configuration"]["same_core_wait_proxy_by_core"], [100] * 4)

    def test_refinement_cannot_recombine_base_tasks_on_same_core(self):
        g = shared_chains(n=2)
        base = {"node_to_subgraph": {2: 7, 1: 7, 12: 4, 11: 4},
                "core_schedules": [[7, 4], []]}
        plan, details = method._refine(base, method._view(g), 60000, 32, 2)
        self.assertEqual([d["base_task"] for d in details], [7, 4])
        self.assertEqual(plan["core_schedules"][0], [7, 8, 4, 9])
        for tid in {v for v in plan["node_to_subgraph"].values()}:
            old = {base["node_to_subgraph"][u] for u, t in plan["node_to_subgraph"].items() if t == tid}
            self.assertEqual(len(old), 1)
        validate_task_order(derive_multicore_plan(g, plan))

    def test_old_chunk_boundaries_count_shared_inputs_per_task(self):
        g = graph([(i, "M", 1) for i in range(4100)], [])
        g["tensors"] = [{"id": 10000, "size": 600000, "pos": "L1"}]
        g["edges"] = [{"source": 10000, "target": i} for i in range(4100)]
        view = method._view(g)
        meta = method._configuration(view, 1, 262144, 32, 60, 100)
        self.assertEqual(meta["base_task_count"], 5)
        self.assertEqual(meta["input_copy_proxy_bytes"], 5 * 600000)
        base, _ = bounded(g, 1)
        plan, _ = method._refine(base, view, 262144, 32, 1)
        self.assertEqual(plan, base)
        self.assertEqual(len(plan["core_schedules"][0]), meta["task_counts_by_core"][0])

    def test_phase_limit_preserves_whole_base_task_and_reports_oversize(self):
        plan, info = method.construct(shared_chains(), 4, input_budget_bytes=60000,
                                     activation_bytes=60000, max_phases=1)
        self.assertEqual(len(plan["core_schedules"][0]), 1)
        self.assertTrue(info["task_refinements"][0]["phase_limit_fallback"])
        self.assertEqual(info["chosen_configuration"]["max_window_input_union_bytes"], 120000)
        self.assertEqual(info["chosen_configuration"]["windows_over_input_budget"], 1)
        self.assertEqual(info["chosen_configuration"]["same_core_wait_proxy_by_core"], [0])

    def test_window_pipe_separation_and_copy_rounding_are_not_lost(self):
        g = shared_chains(n=1, cycles=10, size=1)
        g["ops"][1]["pipe"] = "PIPE_V"
        meta = method._configuration(method._view(g), 1, 1, 32, 60, 100)
        # M then V in separate Tasks cannot share the max-of-global-Pipe proxy.
        self.assertEqual(meta["window_pipe_work_proxy_by_core"], [20])
        self.assertEqual(meta["max_compute_with_wait_proxy_cycles"], 120)
        # Two 1-byte inputs plus two 64-byte activation COPYs: 1+1+2+2.
        self.assertEqual(meta["ddr_service_proxy_cycles"], 6)
        self.assertEqual(meta["total_copy_proxy_bytes"], 130)

    def test_internal_tensor_fanout_counts_each_consuming_task(self):
        g = graph([(1, "M", 10), (2, "M", 10), (3, "M", 10)], [(1, 2), (2, 3)])
        g["edges"].append({"source": 1000, "target": 3})
        for i in range(1, 4):
            g["tensors"].append({"id": 2000+i, "pos": "L1", "size": 1})
            g["edges"].append({"source": 2000+i, "target": i})
        meta = method._configuration(method._view(g), 1, 1, 32, 60, 100)
        self.assertEqual(meta["cut_tensor_payload_bytes_once"], 128)
        self.assertEqual(meta["internal_boundary_copy_proxy_bytes"], 320)
        self.assertEqual(meta["ddr_service_proxy_cycles"], 13)

    def test_declined_route_uses_requested_core_base_once(self):
        g = shared_chains(n=2)
        for k, activation in [(5, 1), (2, 200000)]:
            with patch.object(method, "bounded_construct", wraps=bounded) as called:
                plan, info = method.construct(g, k, activation_bytes=activation)
            self.assertEqual(called.call_count, 1)
            self.assertEqual(called.call_args.args[1], k)
            self.assertEqual(plan, bounded(g, k)[0])
            self.assertEqual(info["configurations"], [])

    def test_copy_bridge_component_and_invalid_domains(self):
        g = graph([(1, "M", 1), (2, "M", 1), (3, "M", 1)], [(1, 2), (2, 3)])
        g["ops"][1]["op"] = "COPY_IN"
        self.assertEqual(len(method._view(g)["components"]), 1)
        for kwargs in ({"cores": True}, {"cores": 6}, {"cores": 2, "input_budget_bytes": 0},
                       {"cores": 2, "max_phases": True}):
            with patch.object(method, "bounded_construct", side_effect=AssertionError("must not call")):
                with self.assertRaises(ValueError):
                    method.construct(shared_chains(), **kwargs)

    def test_cli_emits_only_contract_fields_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / "synthetic.json").write_text(json.dumps(shared_chains()))
            command = [sys.executable, "-B", str(Path(method.__file__)), str(p / "synthetic.json"),
                       "--cores", "4", "--output", str(p / "plan.json"),
                       "--diagnostics", str(p / "info.json"), "--input-budget-bytes", "60000",
                       "--activation-bytes", "60000"]
            subprocess.run(command, check=True, capture_output=True, timeout=30)
            before = (p / "plan.json").read_bytes()
            self.assertEqual(set(json.loads(before)), {"node_to_subgraph", "core_schedules"})
            self.assertEqual(json.loads((p / "info.json").read_text())["active_cores"], 1)
            again = subprocess.run(command, capture_output=True, timeout=30)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual((p / "plan.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
