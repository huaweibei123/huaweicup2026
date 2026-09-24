"""FORM-derived regressions for both E2 algorithm directions.

The quotient-cycle and ranking fixtures are transcribed from FORM PR #17.  The
ranking fixture's Git blob is unchanged through the final handoff commit
dab91d612bd26183e12d30848b13d5fb14e071c7.  They stay local to the E2 test
suite so this task does not merge or claim acceptance of the FORM PR itself.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from src.eval_exact._official import load_problem1
from src.eval_proxy import cli as proxy_cli
from src.eval_proxy.event_model import evaluate_event
from src.eval_proxy.model import (
    ProxyPlanError,
    evaluate,
    prepare_graph,
    validate_plan,
)


class FormRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = load_problem1(
            "_huaweicup_test_proxy_form_regression_oracle_problem1"
        )

    @staticmethod
    def _context(
        graph,
        *,
        bandwidth=60,
        cross_core_wait=1000,
        same_core_wait=100,
    ):
        return prepare_graph(
            graph,
            problem=1,
            bandwidth=bandwidth,
            capacity={"L1": 524288, "UB": 131072},
            cross_core_wait=cross_core_wait,
            same_core_wait=same_core_wait,
        )

    @staticmethod
    def _ranking_graph():
        return {
            "ops": [
                {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
                {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 8},
                {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 8},
                {"id": 4, "op": "VADD", "pipe": "PIPE_V", "cycles": 8},
                {"id": 5, "op": "VADD", "pipe": "PIPE_V", "cycles": 8},
                {"id": 6, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
            ],
            "tensors": [
                {"id": 100, "pos": "DDR", "size": 256},
                {"id": 101, "pos": "L1", "size": 256},
                {"id": 102, "pos": "UB", "size": 256},
                {"id": 103, "pos": "UB", "size": 256},
                {"id": 104, "pos": "UB", "size": 256},
                {"id": 105, "pos": "DDR", "size": 256},
            ],
            "edges": [
                {"source": 100, "target": 1},
                {"source": 1, "target": 101},
                {"source": 101, "target": 2},
                {"source": 2, "target": 102},
                {"source": 101, "target": 3},
                {"source": 3, "target": 103},
                {"source": 102, "target": 4},
                {"source": 103, "target": 4},
                {"source": 4, "target": 104},
                {"source": 104, "target": 5},
                {"source": 5, "target": 105},
                {"source": 5, "target": 6},
            ],
        }

    @staticmethod
    def _ranking_plans():
        mapping = {"2": 0, "3": 0, "4": 0, "5": 1}
        return {
            "a": {
                "node_to_subgraph": dict(mapping),
                "core_schedules": [[0], [1]],
            },
            "b": {
                "node_to_subgraph": dict(mapping),
                "core_schedules": [[0, 1], []],
            },
        }

    @staticmethod
    def _zero_duration_graph():
        return {
            "ops": [
                {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
                {"id": 2, "op": "VADD", "pipe": "PIPE_V", "cycles": 0},
                {"id": 3, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
            ],
            "tensors": [
                {"id": 100, "pos": "DDR", "size": 0},
                {"id": 101, "pos": "UB", "size": 0},
                {"id": 102, "pos": "UB", "size": 0},
                {"id": 103, "pos": "DDR", "size": 0},
            ],
            "edges": [
                {"source": 100, "target": 1},
                {"source": 1, "target": 101},
                {"source": 101, "target": 2},
                {"source": 2, "target": 102},
                {"source": 102, "target": 3},
                {"source": 3, "target": 103},
            ],
        }

    def test_legal_empty_core_is_preserved(self):
        context = self._context(self._ranking_graph())
        plan = self._ranking_plans()["b"]

        view = validate_plan(context, plan)
        static_result = evaluate(context, plan)
        event_result = evaluate_event(context, plan)

        self.assertEqual(view.num_cores, 2)
        self.assertEqual(view.core_orders[1], ())
        self.assertEqual(static_result["status"], "ok")
        self.assertEqual(event_result["status"], "ok")
        self.assertIn("empty_core", static_result["risk_flags"])
        self.assertIn("empty_core", event_result["risk_flags"])

    def test_empty_core_does_not_skip_nontrivial_task_order_validation(self):
        graph = {
            "ops": [
                {"id": op_id, "op": "VADD", "pipe": "PIPE_V", "cycles": 1}
                for op_id in range(1, 5)
            ],
            "tensors": [],
            "edges": [
                {"source": 2, "target": 3},
                {"source": 3, "target": 4},
                {"source": 4, "target": 1},
            ],
        }
        context = self._context(graph)
        plan = {
            "node_to_subgraph": {"1": 0, "2": 1, "3": 2, "4": 3},
            "core_schedules": [[0, 1], [2, 3], []],
        }

        with self.assertRaisesRegex(ProxyPlanError, r"task schedule.*cycle"):
            validate_plan(context, plan)

    def test_decimal_string_keys_cannot_collide_after_integer_normalization(self):
        context = self._context(self._ranking_graph())
        plan = self._ranking_plans()["a"]
        plan["node_to_subgraph"] = {
            "02": 0,
            "2": 0,
            "3": 0,
            "4": 0,
            "5": 1,
        }

        with self.assertRaisesRegex(ProxyPlanError, "duplicate integer op ids"):
            validate_plan(context, plan)

    def test_quotient_cycle_is_rejected(self):
        graph = {
            "ops": [
                {"id": 1, "op": "VADD", "pipe": "PIPE_V", "cycles": 1},
                {"id": 2, "op": "VADD", "pipe": "PIPE_V", "cycles": 1},
                {"id": 3, "op": "VADD", "pipe": "PIPE_V", "cycles": 1},
            ],
            "tensors": [],
            "edges": [
                {"source": 1, "target": 2},
                {"source": 2, "target": 3},
            ],
        }
        context = self._context(graph)
        plan = {
            "node_to_subgraph": {"1": 0, "2": 1, "3": 0},
            "core_schedules": [[0], [1]],
        }

        with self.assertRaisesRegex(ProxyPlanError, "subgraph graph contains a cycle"):
            validate_plan(context, plan)
        with self.assertRaisesRegex(ProxyPlanError, "subgraph graph contains a cycle"):
            evaluate_event(context, plan)

    def test_ranking_inversion_fixture_distinguishes_wait_semantics(self):
        context = self._context(self._ranking_graph())
        plans = self._ranking_plans()

        official = {
            key: self.oracle.evaluate_scene_a(
                self._ranking_graph(),
                plan,
                context.bandwidth,
                context.capacity,
                context.cross_core_wait,
                context.same_core_wait,
            )
            for key, plan in plans.items()
        }
        static = {key: evaluate(context, plan) for key, plan in plans.items()}
        event = {key: evaluate_event(context, plan) for key, plan in plans.items()}

        self.assertEqual(official["a"]["makespan"], 1052)
        self.assertEqual(official["b"]["makespan"], 152)
        self.assertEqual(
            official["a"]["data_movement_bytes"],
            official["b"]["data_movement_bytes"],
        )
        self.assertEqual(
            static["a"]["components"]["task_boundary_copy_bytes"],
            static["b"]["components"]["task_boundary_copy_bytes"],
        )
        self.assertGreater(static["a"]["rank_score"], static["b"]["rank_score"])
        self.assertEqual(event["a"]["numeric_kind"], "estimate")
        self.assertEqual(
            event["a"]["algorithm_direction"],
            "coarse_task_event_list_schedule",
        )
        self.assertEqual(event["a"]["metrics"]["makespan"], 1052)
        self.assertEqual(event["b"]["metrics"]["makespan"], 152)
        self.assertEqual(
            event["a"]["metrics"]["makespan"] - event["b"]["metrics"]["makespan"],
            900,
        )

    def test_zero_cycles_and_zero_size_still_take_one_cycle_each(self):
        graph = self._zero_duration_graph()
        context = self._context(graph)
        plan = {"node_to_subgraph": {"2": 0}, "core_schedules": [[0]]}

        official = self.oracle.evaluate_scene_a(
            graph,
            plan,
            context.bandwidth,
            context.capacity,
            context.cross_core_wait,
            context.same_core_wait,
        )
        event = evaluate_event(context, plan)

        self.assertEqual(official["makespan"], 3)
        self.assertEqual(event["components"]["task_compute_cycles"][0], 1)
        self.assertEqual(event["components"]["task_input_copy_cycles"][0], 1)
        self.assertEqual(event["components"]["task_output_copy_cycles"][0], 1)
        self.assertEqual(event["metrics"]["makespan"], official["makespan"])

    def test_event_direction_is_selectable_from_internal_cli(self):
        root = Path(__file__).resolve().parents[2]
        config_path = root / "data/raw/a/official/data/config.txt"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            graph_path = directory / "graph.json"
            plan_path = directory / "plan.json"
            output_path = directory / "event.json"
            graph_path.write_text(
                json.dumps(self._ranking_graph()) + "\n", encoding="utf-8"
            )
            plan_path.write_text(
                json.dumps(self._ranking_plans()["a"]) + "\n",
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                code = proxy_cli.main(
                    [
                        str(graph_path),
                        str(plan_path),
                        "--engine",
                        "event",
                        "--config",
                        str(config_path),
                        "--output",
                        str(output_path),
                    ]
                )
            response = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(response["engine"], "proxy-task-event-v0")
        self.assertEqual(response["metrics"]["makespan"], 1052)
        self.assertEqual(response["checks"]["execution"], "unchecked")


if __name__ == "__main__":
    unittest.main()
