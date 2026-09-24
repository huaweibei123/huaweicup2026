from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from src.eval_exact._official import OFFICIAL_CODE_DIR, load_problem1
from src.eval_proxy import cli as proxy_cli
from src.eval_proxy.model import (
    ProxyPlanError,
    ProxyUnsupportedError,
    evaluate,
    evaluate_batch,
    prepare_graph,
    validate_plan,
)


class ProxyModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        archive = cls.root / "data" / "raw" / "a" / "official-cases.zip"
        with zipfile.ZipFile(archive) as bundle:
            cls.graph = json.loads(bundle.read("data/case_019.json"))
        if str(OFFICIAL_CODE_DIR) not in sys.path:
            sys.path.insert(0, str(OFFICIAL_CODE_DIR))
        from evaluation_validation import read_evaluation_config, read_required_settings
        from stub_multicore_cut_and_schedule import generate_multicore_plan

        config = cls.root / "data" / "raw" / "a" / "official" / "data" / "config.txt"
        settings = read_evaluation_config(str(config))
        scene = read_required_settings(
            str(config),
            "multicore_scene_a",
            ("task_cross_core_wait_cycles", "task_same_core_wait_cycles"),
        )
        cls.context = prepare_graph(
            cls.graph,
            problem=1,
            bandwidth=settings["bandwidth"],
            capacity=settings["capacity"],
            cross_core_wait=scene["task_cross_core_wait_cycles"],
            same_core_wait=scene["task_same_core_wait_cycles"],
        )
        cls.generate_plan = staticmethod(generate_multicore_plan)
        cls.oracle = load_problem1("_huaweicup_test_proxy_oracle_problem1")
        cls.config = config

    @staticmethod
    def boundary_graph():
        return {
            "ops": [
                {"id": 10, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 1},
                {"id": 20, "op": "A", "pipe": "PIPE_V", "cycles": 3},
                {"id": 30, "op": "B", "pipe": "PIPE_M", "cycles": 5},
                {"id": 40, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 1},
            ],
            "tensors": [
                {"id": 1, "pos": "DDR", "size": 16},
                {"id": 2, "pos": "UB", "size": 16},
                {"id": 3, "pos": "UB", "size": 32},
                {"id": 4, "pos": "UB", "size": 64},
                {"id": 5, "pos": "DDR", "size": 64},
            ],
            "edges": [
                {"source": 1, "target": 10},
                {"source": 10, "target": 2},
                {"source": 2, "target": 20},
                {"source": 20, "target": 3},
                {"source": 3, "target": 30},
                {"source": 30, "target": 4},
                {"source": 4, "target": 40},
                {"source": 40, "target": 5},
            ],
        }

    @staticmethod
    def boundary_context(graph):
        return prepare_graph(
            graph,
            problem=1,
            bandwidth=16,
            capacity={"L1": 1_000_000, "UB": 1_000_000},
            cross_core_wait=7,
            same_core_wait=2,
        )

    def test_valid_plan_is_rank_only_and_deterministic(self):
        plan = self.generate_plan(self.graph, num_cores=4, seed=0)
        validate_plan(self.context, plan)
        first = evaluate(self.context, plan)
        second = evaluate(self.context, plan)
        self.assertEqual(first, second)
        self.assertEqual(first["capability"], "rank_only")
        self.assertEqual(first["numeric_kind"], "none")
        self.assertEqual(first["checks"]["execution"], "unchecked")
        self.assertNotIn("makespan", first)

    def test_missing_node_is_rejected(self):
        plan = self.generate_plan(self.graph, num_cores=4, seed=0)
        invalid = deepcopy(plan)
        invalid["node_to_subgraph"].pop(next(iter(invalid["node_to_subgraph"])))
        with self.assertRaises(ProxyPlanError):
            validate_plan(self.context, invalid)

    def test_bool_subgraph_id_is_rejected(self):
        plan = self.generate_plan(self.graph, num_cores=4, seed=0)
        invalid = deepcopy(plan)
        first_id = next(iter(invalid["node_to_subgraph"]))
        invalid["node_to_subgraph"][first_id] = True
        with self.assertRaises(ProxyPlanError):
            validate_plan(self.context, invalid)

    def test_batch_uses_explicit_unique_ids(self):
        first = self.generate_plan(self.graph, num_cores=4, seed=0)
        second = self.generate_plan(self.graph, num_cores=4, seed=1)
        responses = evaluate_batch(
            self.context,
            [
                {"request_id": "a", "plan": first},
                {"request_id": "b", "plan": second},
            ],
        )
        self.assertEqual([item["request_id"] for item in responses], ["a", "b"])
        with self.assertRaises(ProxyPlanError):
            evaluate_batch(
                self.context,
                [
                    {"request_id": "same", "plan": first},
                    {"request_id": "same", "plan": second},
                ],
            )

    def test_batch_keeps_running_after_invalid_middle_request(self):
        first = self.generate_plan(self.graph, num_cores=4, seed=0)
        third = self.generate_plan(self.graph, num_cores=4, seed=1)
        invalid = deepcopy(first)
        invalid["node_to_subgraph"].pop(next(iter(invalid["node_to_subgraph"])))
        responses = evaluate_batch(
            self.context,
            [
                {"request_id": "valid-before", "plan": first},
                {"request_id": "invalid-middle", "plan": invalid},
                {"request_id": "valid-after", "plan": third},
            ],
        )
        self.assertEqual(
            [response["request_id"] for response in responses],
            ["valid-before", "invalid-middle", "valid-after"],
        )
        self.assertEqual(
            [response["status"] for response in responses],
            ["ok", "invalid", "ok"],
        )
        self.assertEqual(responses[1]["checks"]["plan"], "fail")
        self.assertEqual(
            responses[2]["rank_score"], evaluate(self.context, third)["rank_score"]
        )

    def test_task_boundary_copy_bytes_match_official_builder_on_same_and_cross_core(
        self,
    ):
        graph = self.boundary_graph()
        context = self.boundary_context(graph)
        plans = {
            "same-core": (
                {"node_to_subgraph": {20: 0, 30: 1}, "core_schedules": [[0, 1]]},
                (0, 1),
            ),
            "cross-core": (
                {"node_to_subgraph": {20: 0, 30: 1}, "core_schedules": [[0], [1]]},
                (1, 0),
            ),
        }
        for placement, (plan, expected_counts) in plans.items():
            with self.subTest(placement=placement):
                response = evaluate(context, plan)
                _, _, traffic, _ = self.oracle._build_scene_a_tasks(
                    graph, plan, context.bandwidth, context.capacity
                )
                official_boundary_bytes = (
                    traffic["scheduled_copy_bytes"] - traffic["spill_added_copy_bytes"]
                )
                components = response["components"]
                self.assertEqual(traffic["spill_added_copy_bytes"], 0)
                self.assertEqual(
                    components["task_boundary_copy_bytes"], official_boundary_bytes
                )
                self.assertEqual(
                    components["partition_added_copy_bytes"],
                    traffic["partition_added_copy_bytes"],
                )
                self.assertEqual(official_boundary_bytes, 144)
                self.assertEqual(
                    (
                        components["cross_core_tensor_count"],
                        components["same_core_cross_task_tensor_count"],
                    ),
                    expected_counts,
                )

    def test_problem_2_and_3_are_explicitly_unsupported(self):
        for problem in (2, 3):
            with self.subTest(model_api_problem=problem):
                with self.assertRaisesRegex(
                    ProxyUnsupportedError, "supports problem 1 only"
                ):
                    prepare_graph(
                        self.graph,
                        problem=problem,
                        bandwidth=self.context.bandwidth,
                        capacity=self.context.capacity,
                        cross_core_wait=self.context.cross_core_wait,
                        same_core_wait=self.context.same_core_wait,
                    )

        graph = self.boundary_graph()
        plan = {"node_to_subgraph": {20: 0, 30: 1}, "core_schedules": [[0, 1]]}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            graph_path = directory / "graph.json"
            plan_path = directory / "plan.json"
            graph_path.write_text(json.dumps(graph) + "\n", encoding="utf-8")
            plan_path.write_text(json.dumps(plan) + "\n", encoding="utf-8")
            for problem in (2, 3):
                with self.subTest(cli_problem=problem):
                    output_path = directory / f"problem-{problem}.json"
                    with redirect_stdout(io.StringIO()):
                        code = proxy_cli.main(
                            [
                                str(graph_path),
                                str(plan_path),
                                "--problem",
                                str(problem),
                                "--config",
                                str(self.config),
                                "--output",
                                str(output_path),
                            ]
                        )
                    response = json.loads(output_path.read_text(encoding="utf-8"))
                    self.assertEqual(code, 0)
                    self.assertEqual(response["status"], "unsupported")
                    self.assertEqual(response["problem"], problem)
                    self.assertEqual(response["checks"]["execution"], "unchecked")


if __name__ == "__main__":
    unittest.main()
