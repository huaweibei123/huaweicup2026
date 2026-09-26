from __future__ import annotations

import contextlib
import copy
import io
import json
import random
from pathlib import Path
import unittest

from src.eval_exact import P1Evaluator, P1BatchEvaluator, read_config
from src.eval_exact._official import REPO_ROOT, load_problem1_bundle
from fixtures import tensor_graph


def strict_equal(test, expected, actual):
    test.assertIs(type(actual), type(expected))
    if isinstance(expected, dict):
        test.assertEqual(expected.keys(), actual.keys())
        for key in expected:
            strict_equal(test, expected[key], actual[key])
    elif isinstance(expected, (list, tuple)):
        test.assertEqual(len(expected), len(actual))
        for a, b in zip(expected, actual):
            strict_equal(test, a, b)
    elif isinstance(expected, float):
        test.assertEqual(expected.hex(), actual.hex())
    else:
        test.assertEqual(expected, actual)


def outcome(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            return dict(status="ok", result=function(*args, **kwargs))
        except Exception as error:
            return dict(status="error", error_type=type(error).__name__, message=str(error))


def simple_graph():
    return dict(ops=[dict(id=i, op="CONV", pipe="PIPE_M", cycles=i) for i in (1, 2, 3)],
                tensors=[], edges=[dict(source=1, target=3)])


PLAN = dict(node_to_subgraph={"1": 0, "2": 1, "3": 2}, core_schedules=[[0, 2], [1]])


class BatchExactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle, cls.support = load_problem1_bundle("_batch_test_oracle")
        cls.config = read_config(REPO_ROOT / "data/raw/a/official/data/config.txt")

    def compare(self, graph, plan, engine, config=None):
        config = self.config if config is None else config
        expected = outcome(self.oracle.evaluate_scene_a, graph, plan, **config)
        actual = outcome(engine.evaluate, plan, **config)
        strict_equal(self, expected, actual)
        return actual

    def test_parameters_plan_order_and_mapping_invalidation(self):
        graph = simple_graph()
        engine = P1Evaluator(graph)
        self.compare(graph, PLAN, engine)
        variants = [
            (dict(PLAN, core_schedules=list(reversed(PLAN["core_schedules"]))), self.config),
            (PLAN, dict(self.config, same_core_wait=self.config["same_core_wait"] + 1)),
            (PLAN, dict(self.config, cross_core_wait=self.config["cross_core_wait"] + 3)),
            (PLAN, dict(self.config, bandwidth=self.config["bandwidth"] / 2)),
            (PLAN, dict(self.config, capacity={"UB": 1048576, "L1": 1048576})),
            (dict(PLAN, node_to_subgraph=dict(reversed(list(PLAN["node_to_subgraph"].items())))), self.config),
        ]
        for plan, config in variants:
            self.compare(graph, plan, engine, config)
        self.assertEqual(engine.cache_stats()["hits"], 3)
        self.assertEqual(engine.cache_stats()["misses"], 4)
        bad = dict(PLAN, core_schedules=[[2, 0], [1]])
        self.compare(graph, bad, engine)
        self.assertEqual(engine.cache_stats()["hits"], 3)

    def test_no_input_or_result_alias_and_graph_snapshot(self):
        graph, plan = tensor_graph()
        saved_graph, saved_plan = copy.deepcopy(graph), copy.deepcopy(plan)
        engine = P1Evaluator(graph)
        first = engine.evaluate(plan, **self.config)
        first["per_core_timeline"].clear()
        first["data_movement_bytes"]["spill_added_copy_bytes"] = -123
        strict_equal(self, graph, saved_graph)
        strict_equal(self, plan, saved_plan)
        self.compare(graph, plan, engine)
        graph["ops"][1]["cycles"] += 5
        self.compare(saved_graph, plan, engine)
        self.compare(graph, plan, P1Evaluator(graph))

    def test_failed_global_evaluation_does_not_commit_and_statuses(self):
        graph = simple_graph()
        engine = P1Evaluator(graph)
        limited = dict(self.config, max_iter=1)
        result = self.compare(graph, PLAN, engine, limited)
        self.assertEqual(result["error_type"], "SceneAEvaluationError")
        self.assertEqual(engine.cache_stats()["entries"], 0)
        self.assertEqual(engine.evaluate_record(PLAN, **limited)["status"], "error")
        self.assertEqual(engine.evaluate_record({}, **self.config)["status"], "invalid")
        self.assertEqual(engine.evaluate_record(PLAN, **dict(self.config, bandwidth=0))["status"], "invalid")
        self.compare(graph, PLAN, engine)
        self.assertEqual(engine.cache_stats()["entries"], 1)
        # A failed request on an existing entry does not replace/corrupt it.
        self.compare(graph, PLAN, engine, limited)
        self.compare(graph, PLAN, engine)

    def test_cache_disabled_oversize_lru_and_clear(self):
        graph = simple_graph()
        for limit in (0, 1):
            engine = P1Evaluator(graph, cache_bytes=limit)
            for _ in range(2):
                self.compare(graph, PLAN, engine)
            self.assertEqual(engine.cache_stats()["payload_bytes"], 0)
        engine = P1Evaluator(graph, max_cache_entries=1)
        other = dict(node_to_subgraph={"1": 0, "2": 0, "3": 0}, core_schedules=[[0]])
        for plan in (PLAN, other, PLAN):
            self.compare(graph, plan, engine)
        self.assertEqual(engine.cache_stats()["evictions"], 2)
        self.assertLessEqual(engine.cache_stats()["payload_bytes"], engine.cache_stats()["limit_bytes"])
        engine.clear_cache()
        self.assertEqual(engine.cache_stats()["payload_bytes"], 0)

    def test_spill_original_backing_repeated_l1_incarnations(self):
        graph, plan = tensor_graph()
        engine = P1Evaluator(graph)
        captured = []
        original = engine._runtime.step2_spill_insertion

        def observe(*args, **kwargs):
            result = original(*args, **kwargs)
            captured.extend(copy.deepcopy(result["spill_records"]))
            return result

        engine._runtime.step2_spill_insertion = observe
        first = self.compare(graph, plan, engine)
        selected = [s for s in captured if s["logical_tid"] == 10002]
        self.assertEqual([s["version"] for s in selected], [1, 2])
        self.assertTrue(all(s["pos"] == "L1" and s["spill_out_id"] is None
                            and s["backing_source"] == "original_copy_in" for s in selected))
        self.assertGreater(first["result"]["data_movement_bytes"]["spill_added_copy_bytes"], 0)
        cold_spill_count = len(captured)
        self.compare(graph, dict(plan, core_schedules=[[], [0]]), engine)
        self.assertEqual(engine.cache_stats()["hits"], 1)
        self.assertEqual(len(captured), cold_spill_count)

    def test_form_published_fixtures_full_cold_and_hit(self):
        cases = json.loads(Path(__file__).with_name("form_cases.json").read_text())["cases"]
        for case in cases:
            with self.subTest(case=case["sample_id"]):
                graph, plan = case["graph"], case["plan"]
                engine = P1Evaluator(graph)
                self.compare(graph, plan, engine)
                self.compare(graph, plan, engine)

    def test_seeded_micro_differential_inputs_and_invalid_plans(self):
        # Reproducible family from acceleration probe, not a sealed test corpus.
        for seed in range(60):
            rng = random.Random(900000 + seed)
            n = rng.randrange(2, 10)
            ids = rng.sample(range(10, 90), n)
            graph = dict(ops=[], tensors=[], edges=[])
            for j, oid in enumerate(ids):
                graph["ops"].append(dict(id=oid, op="RELU", pipe=rng.choice(["PIPE_M", "PIPE_V"]),
                                         cycles=rng.choice([0, 1, 3, 17, 100])))
                tid = 100 + j
                graph["tensors"].append(dict(id=tid, pos="UB", size=rng.choice([0, 1, 16, 60, 128])))
                graph["edges"].append(dict(source=tid, target=oid))
                if j and rng.random() < .8:
                    graph["edges"].append(dict(source=ids[rng.randrange(j)], target=tid))
                if j + 1 < n and rng.random() < .5:
                    graph["edges"].append(dict(source=tid, target=ids[rng.randrange(j + 1, n)]))
            graph["tensors"].append(dict(id=9999, pos="UB", size=0))
            schedule = [[] for _ in range(1 + seed % 5)]
            mapping = {}
            for j, oid in enumerate(ids):
                mapping[str(oid)] = j
                schedule[rng.randrange(len(schedule))].append(j)
            plan = dict(node_to_subgraph=mapping, core_schedules=schedule)
            engine = P1Evaluator(graph)
            with self.subTest(seed=seed):
                for _ in range(2):
                    self.compare(graph, plan, engine)
                bad = copy.deepcopy(plan)
                del bad["node_to_subgraph"][str(ids[0])]
                self.compare(graph, bad, engine)
                self.compare(graph, dict(plan, core_schedules=list(reversed(schedule))), engine)

    def test_pool_order_full_results_cache_reuse_and_process_cleanup(self):
        graph = simple_graph()
        processes = []
        with P1BatchEvaluator(graph, workers=2, max_tasks_per_worker=3) as pool:
            plans = [PLAN, {}, PLAN, PLAN]
            rows = list(pool.evaluate_batch(plans, full=True, **self.config))
            self.assertEqual([r["index"] for r in rows], [0, 1, 2, 3])
            self.assertEqual([r["status"] for r in rows], ["ok", "invalid", "ok", "ok"])
            self.assertEqual(rows[2]["cache"]["hits"], 1)
            expected = self.oracle.evaluate_scene_a(graph, PLAN, **self.config)
            strict_equal(self, expected, rows[0]["result"])
            rows2 = list(pool.evaluate_batch([PLAN] * 6, **self.config))
            self.assertEqual({r["status"] for r in rows2}, {"ok"})
            self.assertNotEqual(rows2[-1]["worker_pid"], rows2[0]["worker_pid"])
            processes = [slot[0].pid for slot in pool._slots if slot]
        self.assertTrue(processes)
        self.assertTrue(all(slot is None for slot in pool._slots))

    def test_pool_timeout_is_distinct_and_next_batch_recovers(self):
        with P1BatchEvaluator(simple_graph(), timeout_seconds=1e-12) as pool:
            rows = list(pool.evaluate_batch([PLAN], **self.config))
            self.assertEqual(rows[0]["status"], "timeout")
            self.assertIsNone(pool._slots[0])
            pool._timeout = 30
            result = list(pool.evaluate_batch([PLAN], **self.config))[0]
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["cache"]["misses"], 1)

    def test_pool_crash_and_bounded_input_consumption(self):
        with P1BatchEvaluator(simple_graph()) as pool:
            list(pool.evaluate_batch([PLAN], **self.config))
            pool._slots[0][0].kill()
            pool._slots[0][0].join()
            self.assertEqual(list(pool.evaluate_batch([PLAN], **self.config))[0]["status"], "error")
            self.assertEqual(list(pool.evaluate_batch([PLAN], **self.config))[0]["status"], "ok")
        consumed = []

        def plans():
            for i in range(100):
                consumed.append(i)
                yield PLAN

        with P1BatchEvaluator(simple_graph(), workers=2) as pool:
            iterator = pool.evaluate_batch(plans(), **self.config)
            next(iterator)
            self.assertEqual(len(consumed), 2)
            iterator.close()
        self.assertTrue(all(slot is None for slot in pool._slots))


if __name__ == "__main__":
    unittest.main()
