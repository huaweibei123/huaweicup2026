from __future__ import annotations
import copy
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

from research.a.e2_search import E2Evaluator, E2BatchEvaluator
from research.a.e2_search import _native
from src.eval_exact import read_config
from src.eval_exact._official import REPO_ROOT, load_problem1_bundle
from src.eval_exact.batch_benchmark import equal

sys.path.insert(0, str(REPO_ROOT / "tests/eval_exact"))
from fixtures import tensor_graph


def simple_graph():
    return dict(ops=[dict(id=i, op="CONV", pipe="PIPE_M", cycles=i) for i in (1, 2, 3)],
                tensors=[], edges=[dict(source=1, target=3)])


PLAN = dict(node_to_subgraph={"1": 0, "2": 1, "3": 2}, core_schedules=[[0, 2], [1]])


class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle, cls.support = load_problem1_bundle("_e2_search_test_oracle")
        cls.config = read_config(REPO_ROOT / "data/raw/a/official/data/config.txt")

    def compare(self, graph, plan, engine, config=None):
        config = self.config if config is None else config
        try:
            expected = self.oracle.evaluate_scene_a(graph, plan, **config)
        except Exception as error:
            record = engine.evaluate_record(plan, **config)
            self.assertIn(record["status"], ("invalid", "error"))
            self.assertEqual(record["error_type"], type(error).__name__)
            self.assertEqual(record["message"], str(error))
            return record
        record = engine.evaluate_record(plan, **config)
        self.assertEqual(record["status"], "ok", record)
        for key in ("makespan", "data_movement_bytes", "cross_task_traffic"):
            self.assertTrue(equal(expected[key], record[key]), (key, expected[key], record[key]))
        return record

    def test_native_cache_and_graph_partition_config_isolation(self):
        graph, plan = simple_graph(), copy.deepcopy(PLAN)
        engine = E2Evaluator(graph)
        self.assertEqual(self.compare(graph, plan, engine)["route"], "native")
        graph["ops"][0]["cycles"] += 500
        self.compare(simple_graph(), plan, engine)
        # A returned metadata mutation must not change a future score.
        result = self.compare(simple_graph(), plan, engine)
        result["data_movement_bytes"]["added_copy_bytes"] = -123
        self.compare(simple_graph(), plan, engine)
        for name, config in (
            ("wait", dict(self.config, same_core_wait=7, cross_core_wait=3)),
            ("bandwidth", dict(self.config, bandwidth=self.config["bandwidth"] / 2)),
            ("capacity", dict(self.config, capacity={"UB": 2 ** 20, "L1": 2 ** 20})),
        ):
            with self.subTest(name=name):
                self.compare(simple_graph(), plan, engine, config)
        merged = dict(node_to_subgraph={"1": 0, "2": 0, "3": 0}, core_schedules=[[0]])
        self.compare(simple_graph(), merged, engine)
        self.compare(simple_graph(), dict(plan, core_schedules=[[], [0, 1, 2]]), engine)
        self.assertEqual(engine.cache_stats()["misses"], 4)
        self.assertEqual(engine.cache_stats()["entries"], 4)
        self.assertEqual(plan, PLAN)

    def test_native_failure_falls_back_without_invalid_or_cache_poison(self):
        graph = simple_graph()
        engine = E2Evaluator(graph)
        low_iter = dict(self.config, max_iter=1)
        limited = self.compare(graph, PLAN, engine, low_iter)
        self.assertEqual(limited["status"], "error")
        self.assertEqual(engine.cache_stats()["entries"], 0)
        self.assertIn("native status=3", limited["fallback_reason"]["message"])
        for config in (dict(self.config, same_core_wait=.5), dict(self.config, cross_core_wait=1.5)):
            self.assertEqual(self.compare(graph, PLAN, engine, config)["route"], "e1_fallback")
        with patch.object(_native, "get_lib", side_effect=OSError("missing native library")):
            row = self.compare(graph, PLAN, engine)
            self.assertEqual(row["route"], "e1_fallback")
        self.assertEqual(self.compare(graph, PLAN, engine)["route"], "native")
        self.assertEqual(self.compare(graph, PLAN, E2Evaluator(graph, max_native_ops=1))["route"], "e1_fallback")

    def test_invalid_hit_and_cold_match_official_errors(self):
        engine = E2Evaluator(simple_graph())
        self.compare(simple_graph(), PLAN, engine)
        bad_plans = [{}, dict(PLAN, extra=0), dict(PLAN, core_schedules=[]),
                     dict(PLAN, core_schedules=((0, 2), (1,))),
                     dict(PLAN, core_schedules=[[True, 2], [1]]),
                     dict(PLAN, core_schedules=[[0, 0, 2], [1]]),
                     dict(PLAN, core_schedules=[[2, 0], [1]]),
                     dict(PLAN, node_to_subgraph={"1": 0, "2": 1}),
                     dict(PLAN, node_to_subgraph={"1": 0, 1: 0, "2": 1, "3": 2})]
        for plan in bad_plans:
            for evaluator in (engine, E2Evaluator(simple_graph())):
                self.assertEqual(self.compare(simple_graph(), plan, evaluator)["status"], "invalid")
        for changes in ({"bandwidth": 0}, {"same_core_wait": float("nan")},
                        {"capacity": {"L1": 2}}, {"max_iter": 0}):
            self.assertEqual(self.compare(simple_graph(), PLAN, engine, dict(self.config, **changes))["status"], "invalid")

    def test_spill_incarnations_and_form_regressions(self):
        graph, plan = tensor_graph()
        engine = E2Evaluator(graph)
        row = self.compare(graph, plan, engine)
        self.assertEqual(row["route"], "native")
        self.assertGreater(row["data_movement_bytes"]["spill_added_copy_bytes"], 0)
        self.compare(graph, dict(plan, core_schedules=[[], [0]]), engine)
        cases = json.loads((REPO_ROOT / "tests/eval_exact/form_cases.json").read_text())["cases"]
        for case in cases:
            with self.subTest(sample=case["sample_id"]):
                engine = E2Evaluator(case["graph"])
                self.compare(case["graph"], case["plan"], engine)
                self.compare(case["graph"], case["plan"], engine)

    def test_cache_capacity_eviction_clear_and_full_route(self):
        graph = simple_graph()
        for limit in (0, 1):
            engine = E2Evaluator(graph, cache_bytes=limit)
            for _ in range(2):
                self.compare(graph, PLAN, engine)
            self.assertEqual(engine.cache_stats()["entries"], 0)
        engine = E2Evaluator(graph, max_cache_entries=1)
        merged = dict(node_to_subgraph={"1": 0, "2": 0, "3": 0}, core_schedules=[[0]])
        for plan in (PLAN, merged, PLAN):
            self.compare(graph, plan, engine)
        self.assertEqual(engine.cache_stats()["evictions"], 2)
        stats = engine.cache_stats()
        self.assertLessEqual(stats["accounted_bytes"], stats["limit_bytes"])
        full = engine.evaluate_record(PLAN, full=True, **self.config)
        self.assertTrue(equal(full["result"], self.oracle.evaluate_scene_a(graph, PLAN, **self.config)))
        self.assertEqual(full["route"], "e1_full")
        engine.clear_cache()
        self.assertEqual(engine.cache_stats()["accounted_bytes"], 0)

    def test_seeded_ddr_micro_graphs_cold_hit_and_reorder(self):
        for seed in range(80):
            rng = random.Random(731000 + seed)
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
            orders = [[] for _ in range(1 + seed % 5)]
            for j in range(n):
                orders[rng.randrange(len(orders))].append(j)
            plan = dict(node_to_subgraph={str(oid): j for j, oid in enumerate(ids)}, core_schedules=orders)
            engine = E2Evaluator(graph)
            with self.subTest(seed=seed):
                for _ in range(2):
                    self.assertEqual(self.compare(graph, plan, engine)["route"], "native")
                self.compare(graph, dict(plan, core_schedules=list(reversed(orders))), engine)

    def test_pool_order_error_recycling_and_cleanup(self):
        with E2BatchEvaluator(simple_graph(), workers=2, max_tasks_per_worker=2) as pool:
            rows = list(pool.evaluate_batch([PLAN, {}, PLAN, PLAN], **self.config))
            self.assertEqual([r["index"] for r in rows], list(range(4)))
            self.assertEqual([r["status"] for r in rows], ["ok", "invalid", "ok", "ok"])
            before = rows[-1]["worker_pid"]
            after = list(pool.evaluate_batch([PLAN, PLAN], **self.config))[-1]["worker_pid"]
            self.assertNotEqual(before, after)
        self.assertTrue(all(s is None for s in pool._slots))
        with E2BatchEvaluator(simple_graph(), recycle_peak_rss_bytes=1) as pool:
            first, second = list(pool.evaluate_batch([PLAN, PLAN], **self.config))
            self.assertTrue(first["recycle_after_response"])
            self.assertNotEqual(first["worker_pid"], second["worker_pid"])

    def test_pool_timeout_crash_cancellation_and_stream_bound(self):
        with E2BatchEvaluator(simple_graph(), timeout_seconds=1e-12) as pool:
            row = list(pool.evaluate_batch([PLAN], **self.config))[0]
            self.assertEqual(row["status"], "timeout")
            pool._timeout = 30
            self.assertEqual(list(pool.evaluate_batch([PLAN], **self.config))[0]["route"], "native")
            pool._slots[0][0].kill()
            pool._slots[0][0].join()
            self.assertEqual(list(pool.evaluate_batch([PLAN], **self.config))[0]["status"], "error")
            self.assertEqual(list(pool.evaluate_batch([PLAN], **self.config))[0]["status"], "ok")
        consumed = []
        def plans():
            for i in range(99):
                consumed.append(i)
                yield PLAN
        with E2BatchEvaluator(simple_graph(), workers=2) as pool:
            iterator = pool.evaluate_batch(plans(), **self.config)
            next(iterator)
            self.assertEqual(len(consumed), 2)
            iterator.close()
        self.assertTrue(all(s is None for s in pool._slots))


if __name__ == "__main__":
    unittest.main()
