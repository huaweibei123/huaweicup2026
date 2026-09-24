"""Synthetic control/evidence tests only: never import a constructor/evaluator."""
import gzip
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.q3 import feedback_benchmark as bench
from src.q3.board_export import export_batch


def manifest(stage="first", cases=("002",)):
    return {"schema": "q3-feedback-benchmark-v1", "run_id": "test-run", "stage_id": stage,
            "producer_session": "nikolastarx/s-test", "task_url": "https://github.com/huaweibei123/huaweicup2026/issues/51",
            "solver_commit": "a" * 40, "solver_module": "src.q3.safe_solve",
            "algorithm": {"id": "q3-test", "name": "synthetic fixture only", "authors": ["NikolaStarx"],
                          "method": "test", "references": [], "upstream": []},
            "runtime_id": "test-host", "budget": {"max_e0_calls": 4, "total_wall_seconds": 900, "per_job_seconds": 90},
            "jobs": [{"case_id": case, "cores": 4, "variant": "test", "solver_args": [], "parameters": {}, "e0_call_limit": 2}
                     for case in cases], "offline_costs": "none (test fixture)"}


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / "results/a/q3-nikolastarx/test-run"
        data = self.root / "data/raw/a/official/data"
        data.mkdir(parents=True)
        (data / "config.txt").write_text("synthetic config")
        for case in ("002", "062", "063"):
            (data / f"case_{case}.json").write_text("{}")
        self.env = {"os": "test", "cpu": "test", "gpu": "none", "ram_bytes": 1000,
                    "python": "test", "dependencies": "test", "threads": 1, "workers": 1, "peak_rss_bytes": None}
        self.patchers = [patch.object(bench, "verify_source", return_value=("f" * 64, {})),
                         patch.object(bench, "environment", return_value=self.env)]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.temp.cleanup()

    def child(self, argv, timeout, folder, root):
        # Emulate files only. No constructor, subprocess, E0/E1/E2 invocation.
        graph = root / argv[4]
        plan = root / argv[argv.index("-o") + 1]
        evidence = root / argv[argv.index("--evidence") + 1]
        evidence.mkdir()
        bench.write(plan, {"node_to_subgraph": {"0": 0}, "core_schedules": [[0], [], [], []]})
        result = {"scene": "B", "problem": 3, "cache_mode": "read_only", "num_cores": 4,
                  "makespan": 7.25, "data_movement_bytes": {"scheduled_copy_bytes": 8, "added_copy_bytes": 2,
                                                              "spill_added_copy_bytes": 0},
                  "cache_stats": {"hit_rate": 0.5}, "diagnostic": ["preserved"]}
        (evidence / "result.json.gz").write_bytes(gzip.compress(json.dumps(result).encode(), mtime=0))
        bench.write(evidence / "receipt.json", {
            "official_e0_calls": 1, "makespan": result["makespan"], "plan_sha256": bench.digest(plan),
            "result_sha256": bench.digest(evidence / "result.json.gz"), "graph_sha256": bench.digest(graph),
            "config_sha256": bench.digest(root / "data/raw/a/official/data/config.txt")})
        return {"status": "ok", "exit_code": 0, "wall_seconds": 0.125, "argv": ["python", *argv[1:]]}

    def run_fixture(self, m=None, continuing=False):
        with patch.object(bench, "run_child", side_effect=self.child) as child:
            result = bench.execute(m or manifest(), self.output, continuing, self.root,
                                   ["python", "-m", "src.q3.feedback_benchmark", "fixture.json", "results/test"])
        return result, child.call_count

    def test_success_keeps_numeric_type_and_artifacts(self):
        result, calls = self.run_fixture()
        self.assertEqual(calls, 1)
        self.assertEqual(result["e0_budget_used"], 1)
        feed = export_batch(self.output / "batch.json", self.root)
        record = feed["records"][0]
        self.assertIs(type(record["metrics"]["makespan_cycles"]), float)
        self.assertEqual(record["metrics"]["makespan_cycles"], 7.25)
        self.assertEqual(record["metrics"]["solver_wall_seconds"], 0.125)
        self.assertIsNone(record["metrics"]["evaluation_wall_seconds"])
        self.assertEqual(record["identity"]["plan_sha256"], record["artifacts"]["plan"]["sha256"])
        self.assertIsNone(record["cache_pair"])
        self.assertEqual(record["provenance"]["measurement"]["calls"]["E0"], 1)
        self.assertIn("provenance.measurement.cold_start", record["provenance"]["missing_reasons"])

    def test_timeout_is_charged_and_stops_before_next_job(self):
        with patch.object(bench, "run_child", return_value={"status": "timeout", "exit_code": -9, "wall_seconds": 1.0}) as child:
            result = bench.execute(manifest(cases=("002", "062")), self.output, root=self.root)
        self.assertEqual(child.call_count, 1)
        self.assertEqual(result["e0_budget_used"], 2)
        record = export_batch(self.output / "batch.json", self.root)["records"][0]
        self.assertEqual(record["status"], "timeout")
        self.assertIsNone(record["metrics"]["makespan_cycles"])
        self.assertIsNone(record["provenance"]["measurement"]["calls"]["E0"])
        self.assertEqual(record["provenance"]["measurement"]["failure"]["exit_code"], -9)

    def test_continue_preserves_origin_and_existing_records(self):
        old, _ = self.run_fixture()
        feed_before = export_batch(self.output / "batch.json", self.root)
        new, calls = self.run_fixture(manifest("second", ("062",)), continuing=True)
        self.assertEqual(calls, 1)
        self.assertEqual(old["started_at"], new["started_at"])
        self.assertEqual(new["e0_budget_used"], 2)
        self.assertEqual(export_batch(self.output / "batch.json", self.root)["records"][0], feed_before["records"][0])
        with self.assertRaises(ValueError):
            self.run_fixture(manifest("second", ("062",)), continuing=True)

    def test_continue_cannot_reset_budget_or_retry_failed_stage(self):
        self.run_fixture()
        changed = manifest("second", ("062",))
        changed["budget"]["max_e0_calls"] = 100
        with self.assertRaises(ValueError):
            self.run_fixture(changed, continuing=True)
        state = bench.read(self.output / "batch.json")
        state["status"] = "stopped_on_failure"
        bench.write(self.output / "batch.json", state)
        with self.assertRaises(ValueError):
            self.run_fixture(manifest("second", ("062",)), continuing=True)

    def test_export_rejects_changed_artifact(self):
        batch, _ = self.run_fixture()
        ref = batch["records"][0]["artifacts"]["plan"]
        (self.root / ref["path"]).write_text("{}")
        with self.assertRaises(ValueError):
            export_batch(self.output / "batch.json", self.root)

    def test_changed_result_type_or_hash_stops_batch(self):
        original = self.child
        def corrupt(argv, timeout, folder, root):
            answer = original(argv, timeout, folder, root)
            path = folder / "evidence/receipt.json"
            receipt = bench.read(path)
            receipt["makespan"] = 7
            bench.write(path, receipt)
            return answer
        with patch.object(bench, "run_child", side_effect=corrupt):
            batch = bench.execute(manifest(), self.output, root=self.root)
        self.assertEqual(batch["status"], "stopped_on_failure")
        self.assertEqual(batch["e0_budget_used"], 2)

    def test_manifest_blocks_output_override_and_invalid_budget(self):
        for key, value in (("solver_args", ["--output=elsewhere"]), ("cores", True), ("e0_call_limit", 0)):
            m = manifest()
            m["jobs"][0][key] = value
            with self.assertRaises(ValueError):
                bench.validate_manifest(m)

    def test_against_available_shared_submission_protocol(self):
        root = Path(os.environ.get("Q3_BOARD_PROTOCOL_ROOT", bench.ROOT))
        path = root / "src/benchmark_board/protocol.py"
        if not path.exists():
            self.skipTest("Set Q3_BOARD_PROTOCOL_ROOT to a checkout with the shared board protocol")
        spec = importlib.util.spec_from_file_location("q3_test_board_protocol", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.run_fixture()
        self.assertTrue(module.validate_feed(export_batch(self.output / "batch.json", self.root), submission=True))

    def test_candidate_rejection_stops_but_keeps_confirmed_plan(self):
        original = self.child
        def rejected(argv, timeout, folder, root):
            answer = original(argv, timeout, folder, root)
            evidence = folder / "evidence"
            path = evidence / "receipt.json"
            receipt = bench.read(path)
            # Preserve exact chosen bytes; the independent auditor re-hashes both.
            (evidence / "seed").mkdir()
            final_plan = next(folder.glob("*multicore_res.json"))
            (evidence / "seed/plan.json").write_bytes(final_plan.read_bytes())
            (evidence / "seed/result.json.gz").write_bytes((evidence / "result.json.gz").read_bytes())
            receipt.update(official_e0_calls=2, selected_strategy="seed-test", candidates=[
                {"name": "seed", "strategy": "seed-test", "status": "ok", "makespan": 7.25,
                 "artifacts": {"plan": {"path": "seed/plan.json", "sha256": receipt["plan_sha256"]},
                               "result": {"path": "seed/result.json.gz", "sha256": receipt["result_sha256"]}}},
                {"name": "tree", "strategy": "tree-test", "status": "rejected", "makespan": None}])
            bench.write(path, receipt)
            bench.write(evidence / "evaluations.json", [{"status": "ok"}, {"status": "failed"}])
            return answer
        with patch.object(bench, "run_child", side_effect=rejected) as child:
            result = bench.execute(manifest(cases=("002", "062")), self.output, root=self.root)
        self.assertEqual(child.call_count, 1)
        self.assertEqual(result["status"], "stopped_on_candidate_rejection")
        feed = export_batch(self.output / "batch.json", self.root)
        self.assertEqual(feed["records"][0]["status"], "ok")
        self.assertEqual(feed["records"][0]["metrics"]["makespan_cycles"], 7.25)
        self.assertIn("tree candidate rejected", " ".join(feed["records"][0]["notes"]))

    def test_pruned_candidate_is_not_scored_or_charged_as_e0(self):
        def pruned(argv, timeout, folder, root):
            answer = self.child(argv, timeout, folder, root)
            evidence = folder / "evidence"
            receipt = bench.read(evidence / "receipt.json")
            (evidence / "seed").mkdir()
            plan = next(folder.glob("*multicore_res.json"))
            (evidence / "seed/plan.json").write_bytes(plan.read_bytes())
            (evidence / "seed/result.json.gz").write_bytes((evidence / "result.json.gz").read_bytes())
            receipt.update(selected_strategy="seed-test", candidates=[
                {"name": "seed", "strategy": "seed-test", "status": "ok", "makespan": 7.25,
                 "artifacts": {"plan": {"path": "seed/plan.json", "sha256": receipt["plan_sha256"]},
                               "result": {"path": "seed/result.json.gz", "sha256": receipt["result_sha256"]}}},
                {"name": "release", "status": "bound_pruned", "makespan": None,
                 "certified_lower_bound_cycles": 8,
                 "unscored_plan": bench.read(plan),
                 "unscored_plan_sha256": __import__('hashlib').sha256(
                     (json.dumps(bench.read(plan), separators=(",", ":")) + "\n").encode()).hexdigest()}])
            bench.write(evidence / "receipt.json", receipt)
            bench.write(evidence / "evaluations.json", [{"status": "ok"}])
            return answer
        with patch.object(bench, "run_child", side_effect=pruned):
            result = bench.execute(manifest(), self.output, root=self.root)
        self.assertEqual(result["e0_budget_used"], 1)
        row = export_batch(self.output / "batch.json", self.root)["records"][0]
        self.assertEqual(row["metrics"]["makespan_cycles"], 7.25)
        folder = self.root / result["records"][0]["artifacts"]["trace"]["path"]
        receipt = bench.read(folder)
        receipt["candidates"][-1]["certified_lower_bound_cycles"] = 7
        bench.write(folder, receipt)
        with self.assertRaisesRegex(ValueError, "adequate lower bound"):
            bench.validate_result(folder.parent.parent, manifest()["jobs"][0], self.root)


if __name__ == "__main__":
    unittest.main()
