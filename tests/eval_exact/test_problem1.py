from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType

from src.eval_exact import benchmark as exact_benchmark
from src.eval_exact import cli as exact_cli
from src.eval_exact import problem1 as exact_problem1
from src.eval_exact._official import load_problem1_bundle
from src.eval_exact.problem1 import evaluate_scene_a, read_scene_a_config

_MISSING = object()


@contextmanager
def installed_modules(modules):
    """Temporarily expose an isolated official bundle under its public names."""
    previous = {name: sys.modules.get(name, _MISSING) for name in modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


class ExactProblem1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        archive = cls.root / "data" / "raw" / "a" / "official-cases.zip"
        with zipfile.ZipFile(archive) as bundle:
            cls.graph = json.loads(bundle.read("data/case_019.json"))
        cls.oracle, cls.oracle_support = load_problem1_bundle(
            "_huaweicup_test_oracle_problem1"
        )
        read_evaluation_config = cls.oracle_support[
            "evaluation_validation"
        ].read_evaluation_config
        generate_multicore_plan = cls.oracle_support[
            "stub_multicore_cut_and_schedule"
        ].generate_multicore_plan

        config = cls.root / "data" / "raw" / "a" / "official" / "data" / "config.txt"
        settings = read_evaluation_config(str(config))
        scene = read_scene_a_config(str(config))
        cls.call_args = {
            "bandwidth": settings["bandwidth"],
            "capacity": settings["capacity"],
            "cross_core_wait": scene["task_cross_core_wait_cycles"],
            "same_core_wait": scene["task_same_core_wait_cycles"],
        }
        cls.generate_plan = staticmethod(generate_multicore_plan)
        cls.plan = generate_multicore_plan(cls.graph, num_cores=4, seed=0)
        cls.config = config

    def run_official_cli(self, argv):
        modules = dict(self.oracle_support)
        modules["multicore_cut_evaluate_problem_1"] = self.oracle
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            installed_modules(modules),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = self.oracle_support["contest_io"].run_problem_cli(1, argv)
        return code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def run_candidate_cli(argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = exact_cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def write_cli_inputs(self, directory, plan):
        graph_path = directory / "case_019.json"
        plan_path = directory / "case_019.plan.json"
        graph_path.write_text(
            json.dumps(self.graph, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return graph_path, plan_path

    def test_full_results_match_for_two_plans(self):
        for seed in (0, 2026):
            with self.subTest(seed=seed):
                plan = self.generate_plan(self.graph, num_cores=4, seed=seed)
                expected = self.oracle.evaluate_scene_a(
                    self.graph, plan, **self.call_args
                )
                actual = evaluate_scene_a(self.graph, plan, **self.call_args)
                self.assertEqual(actual, expected)

    def test_preloaded_same_name_dependency_cannot_contaminate_oracle(self):
        poison = ModuleType("schedule_step1")
        poison.called = False

        def contaminated_step1(*_args, **_kwargs):
            poison.called = True
            raise AssertionError("ambient schedule_step1 was executed")

        poison.step1_schedule = contaminated_step1
        dependency_name = "schedule_step1"
        alias = "_huaweicup_test_preload_isolation_problem1"
        previous_dependency = sys.modules.get(dependency_name, _MISSING)
        previous_alias = sys.modules.get(alias, _MISSING)
        previous_path = list(sys.path)
        alias_sentinel = ModuleType(alias)
        sys.modules[dependency_name] = poison
        sys.modules[alias] = alias_sentinel
        try:
            isolated, support = load_problem1_bundle(alias)
            self.assertIs(sys.modules[dependency_name], poison)
            self.assertIs(sys.modules[alias], alias_sentinel)
            self.assertEqual(sys.path, previous_path)
            self.assertIsNot(support[dependency_name], poison)
            actual = isolated.evaluate_scene_a(self.graph, self.plan, **self.call_args)
            expected = self.oracle.evaluate_scene_a(
                self.graph, self.plan, **self.call_args
            )
            self.assertEqual(actual, expected)
            self.assertFalse(poison.called)
        finally:
            if previous_dependency is _MISSING:
                sys.modules.pop(dependency_name, None)
            else:
                sys.modules[dependency_name] = previous_dependency
            if previous_alias is _MISSING:
                sys.modules.pop(alias, None)
            else:
                sys.modules[alias] = previous_alias

    def test_private_alias_does_not_leak_when_initially_absent(self):
        alias = "_huaweicup_test_no_alias_leak_problem1"
        previous_alias = sys.modules.pop(alias, _MISSING)
        previous_path = list(sys.path)
        try:
            isolated, _ = load_problem1_bundle(alias)
            self.assertEqual(isolated.__name__, alias)
            self.assertNotIn(alias, sys.modules)
            self.assertEqual(sys.path, previous_path)
        finally:
            if previous_alias is not _MISSING:
                sys.modules[alias] = previous_alias

    def test_mixed_core_orders_do_not_skip_cycle_validation(self):
        mixed_view = {
            "core_orders": {0: [0], 1: [1, 2]},
            "dependency_pairs": [(2, 1)],
            "subgraph_ids": [0, 1, 2],
        }
        with self.assertRaisesRegex(ValueError, "task schedule: dependency cycle"):
            exact_problem1._runtime.validate_task_order(mixed_view)

    def test_step3_schema_copy_is_runtime_isolated_and_alias_free(self):
        candidate_globals = exact_problem1._runtime.prepare_step3_execution.__globals__
        oracle_globals = self.oracle_support[
            "schedule_step3"
        ].prepare_step3_execution.__globals__
        self.assertIs(
            candidate_globals["deepcopy"],
            exact_problem1._copy_step3_extended_graph,
        )
        self.assertIsNot(
            oracle_globals["deepcopy"],
            exact_problem1._copy_step3_extended_graph,
        )

        source = {
            "ops": [{"id": 1, "op": "RELU", "cycles": 3}],
            "tensors": [{"id": 10001, "pos": "UB", "size": 16}],
            "edges": [{"source": 1, "target": 10001}],
            "seq_ext": [1],
        }
        copied = exact_problem1._copy_step3_extended_graph(source)
        self.assertEqual(copied, source)
        self.assertIsNot(copied, source)
        for key in ("ops", "tensors", "edges", "seq_ext"):
            self.assertIsNot(copied[key], source[key])
        for key in ("ops", "tensors", "edges"):
            self.assertIsNot(copied[key][0], source[key][0])

        copied["ops"][0]["cycles"] = 99
        copied["tensors"].append({"id": 10002, "pos": "DDR", "size": 16})
        copied["edges"][0]["target"] = 10002
        copied["seq_ext"].append(2)
        self.assertEqual(source["ops"][0]["cycles"], 3)
        self.assertEqual(len(source["tensors"]), 1)
        self.assertEqual(source["edges"][0]["target"], 10001)
        self.assertEqual(source["seq_ext"], [1])

    def test_step3_schema_copy_falls_back_for_nested_or_unknown_fields(self):
        cases = {
            "nested": {
                "ops": [{"id": 1, "metadata": {"labels": ["future"]}}],
                "tensors": [],
                "edges": [],
                "seq_ext": [1],
            },
            "extra_top_level": {
                "ops": [{"id": 1}],
                "tensors": [],
                "edges": [],
                "seq_ext": [1],
                "metadata": {"version": [2]},
            },
        }
        for name, source in cases.items():
            with self.subTest(name=name):
                copied = exact_problem1._copy_step3_extended_graph(source)
                self.assertEqual(copied, source)
                self.assertIsNot(copied, source)
                if name == "nested":
                    self.assertIsNot(
                        copied["ops"][0]["metadata"],
                        source["ops"][0]["metadata"],
                    )
                    self.assertIsNot(
                        copied["ops"][0]["metadata"]["labels"],
                        source["ops"][0]["metadata"]["labels"],
                    )
                else:
                    self.assertIsNot(copied["metadata"], source["metadata"])
                    self.assertIsNot(
                        copied["metadata"]["version"],
                        source["metadata"]["version"],
                    )

    def test_step3_schema_copy_uses_saved_deepcopy_on_schema_drift(self):
        source = {
            "ops": [{"id": 1, "metadata": {"future": True}}],
            "tensors": [],
            "edges": [],
            "seq_ext": [1],
        }
        original = exact_problem1._official_step3_deepcopy
        calls = []

        def recording_deepcopy(value):
            calls.append(value)
            return original(value)

        exact_problem1._official_step3_deepcopy = recording_deepcopy
        try:
            copied = exact_problem1._copy_step3_extended_graph(source)
        finally:
            exact_problem1._official_step3_deepcopy = original
        self.assertEqual(copied, source)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0], source)
        self.assertIsNot(copied["ops"][0]["metadata"], source["ops"][0]["metadata"])

    def test_step3_schema_copy_preserves_aliases_via_fallback(self):
        shared_record = {"id": 1}
        source = {
            "ops": [shared_record, shared_record],
            "tensors": [],
            "edges": [],
            "seq_ext": [1],
        }
        copied = exact_problem1._copy_step3_extended_graph(source)
        self.assertIs(copied["ops"][0], copied["ops"][1])

        shared_container = []
        source = {
            "ops": shared_container,
            "tensors": shared_container,
            "edges": [],
            "seq_ext": [],
        }
        copied = exact_problem1._copy_step3_extended_graph(source)
        self.assertIs(copied["ops"], copied["tensors"])

    def test_benchmark_artifacts_use_lf_and_hash_delivered_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "matrix"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = exact_benchmark.main(
                    [
                        "--cases",
                        "case_001.json",
                        "--output-dir",
                        str(output_dir),
                        "--seed",
                        "2026",
                        "--cores",
                        "4",
                        "--warmup",
                        "0",
                        "--repeats",
                        "1",
                        "--min-subgraph-size",
                        "4",
                        "--max-subgraph-size",
                        "12",
                    ]
                )
            self.assertEqual(code, 0)

            plan_path = output_dir / "plans" / "case_001.plan.json"
            artifacts = (
                plan_path,
                output_dir / "paired-timings.csv",
                output_dir / "run.json",
            )
            for path in artifacts:
                with self.subTest(artifact=path.name):
                    content = path.read_bytes()
                    self.assertNotIn(b"\r", content)
                    self.assertTrue(content.endswith(b"\n"))

            run = json.loads((output_dir / "run.json").read_bytes())
            plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            self.assertEqual(run["plan_sha256"]["case_001.json"], plan_hash)
            source_hashes = run["candidate_implementation"]["delivery_lf_sha256"]
            for relative, expected_hash in source_hashes.items():
                source = (self.root / relative).read_bytes().replace(b"\r\n", b"\n")
                with self.subTest(source=relative):
                    self.assertEqual(expected_hash, hashlib.sha256(source).hexdigest())
            benchmark_source = (
                Path(exact_benchmark.__file__).read_bytes().replace(b"\r\n", b"\n")
            )
            self.assertEqual(
                run["benchmark_delivery_lf_sha256"],
                hashlib.sha256(benchmark_source).hexdigest(),
            )

    def test_successful_cli_artifacts_are_byte_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            graph_path, plan_path = self.write_cli_inputs(directory, self.plan)
            official_dir = directory / "official"
            candidate_dir = directory / "candidate"
            official_dir.mkdir()
            candidate_dir.mkdir()
            official_paths = [
                official_dir / "result.json",
                official_dir / "trace.json",
                official_dir / "result.log",
            ]
            candidate_paths = [
                candidate_dir / "result.json",
                candidate_dir / "trace.json",
                candidate_dir / "result.log",
            ]
            common = [str(graph_path), str(plan_path), "--config", str(self.config)]
            official_argv = common + [
                "--output",
                str(official_paths[0]),
                "--trace-output",
                str(official_paths[1]),
                "--log-output",
                str(official_paths[2]),
            ]
            candidate_argv = common + [
                "--output",
                str(candidate_paths[0]),
                "--trace-output",
                str(candidate_paths[1]),
                "--log-output",
                str(candidate_paths[2]),
            ]

            official_code, _, official_error = self.run_official_cli(official_argv)
            candidate_code, _, candidate_error = self.run_candidate_cli(candidate_argv)
            self.assertEqual(official_code, 0)
            self.assertEqual(candidate_code, official_code)
            self.assertEqual(candidate_error, official_error)
            for official_path, candidate_path in zip(official_paths, candidate_paths):
                with self.subTest(artifact=official_path.name):
                    self.assertEqual(
                        candidate_path.read_bytes(), official_path.read_bytes()
                    )

    def test_invalid_plan_matches_official_cli_error_semantics(self):
        invalid_plan = json.loads(json.dumps(self.plan))
        invalid_plan["node_to_subgraph"].pop(
            next(iter(invalid_plan["node_to_subgraph"]))
        )
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            graph_path, plan_path = self.write_cli_inputs(directory, invalid_plan)
            official_output = directory / "official.json"
            candidate_output = directory / "candidate.json"
            common = [str(graph_path), str(plan_path), "--config", str(self.config)]
            official_code, official_stdout, official_error = self.run_official_cli(
                common + ["--output", str(official_output)]
            )
            candidate_code, candidate_stdout, candidate_error = self.run_candidate_cli(
                common + ["--output", str(candidate_output)]
            )

            self.assertEqual(official_code, 1)
            self.assertEqual(candidate_code, official_code)
            self.assertEqual(candidate_stdout, official_stdout)
            self.assertEqual(candidate_error, official_error)
            self.assertTrue(candidate_error.startswith("[EVALUATION ERROR] "))
            self.assertFalse(official_output.exists())
            self.assertFalse(candidate_output.exists())


if __name__ == "__main__":
    unittest.main()
