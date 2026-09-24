"""Structural routing and saved records with injected scores; zero official E0."""
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from src.q3 import adaptive_solve as adaptive
from src.q3.attention_rows import construct as attention_construct
from src.q3.construct import Index, UnsupportedStructure
from src.q3.guarded_solve import evaluate_candidates as guarded
from src.q3.stage_fork_join import construct as stage_construct
from src.q3.stage_migration import construct as migration_construct
from tests.q3.test_reduction_tree import graph as reduction_graph
from tests.q3.test_attention_rows import attention_ffn_graph, plan_words
from tests.q3.test_stage_fork_join import stage_graph
from tests.q3.test_stage_migration import stage_graph as migration_stage_graph
from evaluation_validation import EvaluationValidationError


class AdaptiveTests(unittest.TestCase):
    def test_stage_routes_and_saves_one_candidate(self):
        # Equal lane chains make lane count proportional to compute load. Two
        # heavy cores rotate; one, three or four heavy cores stay fixed.
        for lanes, cores, policy in ((8, 1, "fixed"), (8, 2, "rotate_heavy"),
                                     (8, 3, "rotate_heavy"), (8, 4, "fixed"),
                                     (8, 5, "fixed"), (2, 5, "rotate_heavy")):
            with self.subTest(lanes=lanes, cores=cores):
                graph, _ = stage_graph(lanes=lanes, stages=3)
                original = deepcopy(graph)
                index = Index(graph)
                expected, _ = stage_construct(index, cores, collector_policy=policy)
                result = {"makespan": 12.5, "full_result_field": {"untouched": True}}
                refs = {"plan": {"path": "seed-plan.json", "sha256": "plan-digest"},
                        "result": {"path": "seed-result.json.gz", "sha256": "result-digest"}}
                evaluate = Mock(return_value=result)
                save = Mock(return_value=refs)
                with patch.object(adaptive, "stage_construct", wraps=stage_construct) as construct, \
                     patch.object(adaptive, "migration_construct") as migration, \
                     patch.object(adaptive, "attention_construct") as attention, \
                     patch.object(adaptive, "read_required_settings") as config, \
                     patch.object(adaptive, "guarded_candidates") as fallback:
                    winner, calls, records, selection = adaptive.evaluate_candidates(index, cores, evaluate, save)
                construct.assert_called_once_with(index, cores, collector_policy=policy)
                migration.assert_not_called()
                attention.assert_not_called()
                config.assert_not_called()
                fallback.assert_not_called()
                evaluate.assert_called_once_with(expected)
                save.assert_called_once_with("seed", expected, result)
                self.assertIs(winner[1], result)
                self.assertEqual(winner[0], expected)
                self.assertEqual(calls, 1)
                self.assertEqual(len(records), 1)
                record = records[0]
                self.assertEqual((record["name"], record["status"], record["makespan"]), ("seed", "ok", 12.5))
                self.assertIs(record["artifacts"], refs)
                meta = record["metadata"]
                self.assertEqual(meta["collector_policy"], policy)
                self.assertEqual(meta["route"], "stage")
                self.assertEqual(meta["official_e0_calls"], 0)  # Static constructor scope.
                self.assertEqual(meta["router"]["evaluation_calls"], 1)
                self.assertEqual(meta["router"]["stage_construct_attempts"], 1)
                self.assertEqual(meta["router"]["migration_construct_attempts"], 0)
                self.assertEqual(meta["router"]["migration_candidate_plans"], 0)
                self.assertEqual(meta["router"]["stage_candidate_plans"], 1)
                self.assertEqual(meta["router"]["attention_construct_attempts"], 0)
                self.assertEqual(meta["router"]["attention_candidate_plans"], 0)
                self.assertEqual(meta["router"]["route_e0_limit"], 1)
                self.assertEqual(selection["router"], meta["router"])
                if policy == "rotate_heavy":
                    self.assertEqual(len(meta["collector_cycle"]), 2)
                else:
                    self.assertEqual(meta["collector_cycle"], [meta["collector_core"]])
                self.assertEqual(graph, original)

    def test_exact_migration_family_preempts_old_routes_with_one_evaluation(self):
        for stages in (1, 3):
            with self.subTest(stages=stages):
                graph, _ = migration_stage_graph(stages=stages)
                original = deepcopy(graph)
                index = Index(graph)
                expected, expected_meta = migration_construct(index, 5, mode="single_cut")
                result = {"makespan": 10**9, "data_movement_bytes": {"extra": 999}}
                refs = {"plan": {"path": "seed-plan.json"}, "result": {"path": "seed-result.json.gz"}}
                evaluate, save = Mock(return_value=result), Mock(return_value=refs)
                with patch.object(adaptive, "migration_construct", wraps=migration_construct) as migration, \
                     patch.object(adaptive, "stage_construct") as stage, \
                     patch.object(adaptive, "attention_construct") as attention, \
                     patch.object(adaptive, "guarded_candidates") as fallback:
                    winner, calls, records, selection = adaptive.evaluate_candidates(index, 5, evaluate, save)
                migration.assert_called_once_with(index, 5, mode="single_cut", cross_core_delay_cycles=500)
                stage.assert_not_called()
                attention.assert_not_called()
                fallback.assert_not_called()
                evaluate.assert_called_once_with(expected)
                save.assert_called_once_with("seed", expected, result)
                self.assertEqual(winner[0], expected)
                self.assertIs(winner[1], result)
                self.assertEqual(winner[2], "stage_migration_single_cut")
                self.assertEqual((calls, len(records)), (1, 1))
                self.assertIs(records[0]["artifacts"], refs)
                meta = records[0]["metadata"]
                for key, value in expected_meta.items():
                    self.assertEqual(meta[key], value)
                self.assertEqual(meta["route"], "stage_migration")
                self.assertEqual(meta["mode"], "single_cut")
                self.assertEqual(meta["collector_sequence"], [2] * stages)
                self.assertEqual(meta["official_e0_calls"], 0)  # Static constructor only.
                routing = selection["router"]
                self.assertEqual(routing, meta["router"])
                self.assertEqual(routing["route"], "stage_migration")
                self.assertEqual(routing["migration_construct_attempts"], 1)
                self.assertEqual(routing["migration_candidate_plans"], 1)
                self.assertEqual(routing["migration_cross_delay_cycles"], 500)
                for name in ("stage_construct_attempts", "stage_candidate_plans",
                             "attention_construct_attempts", "attention_candidate_plans",
                             "guarded_policy_invocations"):
                    self.assertEqual(routing[name], 0)
                self.assertEqual(routing["evaluation_calls"], evaluate.call_count)
                self.assertEqual(routing["route_e0_limit"], 1)
                self.assertNotIn("migration_guard_reason", routing)
                self.assertEqual(graph, original)

    def test_migration_signature_rejection_keeps_the_old_stage_plan(self):
        for kwargs in ({"cycles": 525}, {"vector": 16384}, {"chain_length": 3}):
            with self.subTest(kwargs=kwargs):
                graph, _ = migration_stage_graph(**kwargs)
                index = Index(graph)
                expected, _ = stage_construct(index, 5, collector_policy="rotate_heavy")
                evaluate, save = Mock(return_value={"makespan": 11}), Mock(return_value={})
                with patch.object(adaptive, "migration_construct", wraps=migration_construct) as migration, \
                     patch.object(adaptive, "stage_construct", wraps=stage_construct) as stage, \
                     patch.object(adaptive, "attention_construct") as attention, \
                     patch.object(adaptive, "guarded_candidates") as fallback:
                    winner, calls, _, selection = adaptive.evaluate_candidates(index, 5, evaluate, save)
                migration.assert_called_once_with(index, 5, mode="single_cut", cross_core_delay_cycles=500)
                stage.assert_called_once_with(index, 5, collector_policy="rotate_heavy")
                attention.assert_not_called()
                fallback.assert_not_called()
                evaluate.assert_called_once_with(expected)
                save.assert_called_once()
                self.assertEqual((winner[0], calls), (expected, 1))
                routing = selection["router"]
                self.assertEqual(routing["route"], "stage")
                self.assertEqual(routing["migration_construct_attempts"], 1)
                self.assertEqual(routing["migration_candidate_plans"], 0)
                self.assertIn("signature", routing["migration_guard_reason"])
                self.assertEqual(routing["stage_candidate_plans"], 1)

    def test_migration_prefilter_does_not_try_other_core_counts(self):
        index = Index(migration_stage_graph()[0])
        expected, _ = stage_construct(index, 4, collector_policy="fixed")
        evaluate = Mock(return_value={"makespan": 11})
        with patch.object(adaptive, "migration_construct") as migration, \
             patch.object(adaptive, "read_required_settings") as config:
            winner, calls, _, selection = adaptive.evaluate_candidates(index, 4, evaluate, Mock())
        migration.assert_not_called()
        config.assert_not_called()
        evaluate.assert_called_once_with(expected)
        self.assertEqual((winner[0], calls), (expected, 1))
        self.assertEqual(selection["router"]["migration_construct_attempts"], 0)

    def test_migration_raw_port_rejection_preserves_full_remaining_route(self):
        graph, layout = migration_stage_graph()
        graph["edges"].append({"source": layout["immutable"][1],
                               "target": layout["stages"][0]["chains"][0][2]})
        index = Index(graph)
        sentinel = (({"fallback": 1}, {"makespan": 7}, "fallback"), 1, [], {"rule": "sentinel"})
        evaluate, save = Mock(), Mock()
        with patch.object(adaptive, "migration_construct", wraps=migration_construct) as migration, \
             patch.object(adaptive, "stage_construct", wraps=stage_construct) as stage, \
             patch.object(adaptive, "attention_construct", wraps=attention_construct) as attention, \
             patch.object(adaptive, "guarded_candidates", return_value=sentinel) as fallback:
            out = adaptive.evaluate_candidates(index, 5, evaluate, save)
        migration.assert_called_once()
        stage.assert_called_once()
        attention.assert_called_once()
        fallback.assert_called_once_with(index, 5, evaluate, save)
        self.assertEqual(out[:3], sentinel[:3])
        routing = out[3]["router"]
        self.assertEqual(routing["route"], "guarded")
        self.assertEqual(routing["migration_construct_attempts"], 1)
        self.assertEqual(routing["migration_candidate_plans"], 0)
        self.assertIn("lane-internal tensor input", routing["migration_guard_reason"])
        evaluate.assert_not_called()
        save.assert_not_called()

    def test_migration_failures_do_not_trigger_other_routes(self):
        index = Index(migration_stage_graph()[0])
        failures = (RuntimeError("bug"), AssertionError("invariant"), ValueError("bad option"),
                    EvaluationValidationError("invalid"))
        for phase in ("construct", "evaluate", "save"):
            for failure in failures + (() if phase == "construct" else (UnsupportedStructure("not a guard"),)):
                with self.subTest(phase=phase, failure=type(failure).__name__):
                    evaluate = Mock(side_effect=failure) if phase == "evaluate" else Mock(return_value={"makespan": 1})
                    save = Mock(side_effect=failure) if phase == "save" else Mock(return_value={})
                    constructor_options = {"side_effect": failure} if phase == "construct" else {"wraps": migration_construct}
                    with patch.object(adaptive, "migration_construct", **constructor_options) as migration, \
                         patch.object(adaptive, "stage_construct") as stage, \
                         patch.object(adaptive, "attention_construct") as attention, \
                         patch.object(adaptive, "guarded_candidates") as fallback:
                        with self.assertRaises(type(failure)):
                            adaptive.evaluate_candidates(index, 5, evaluate, save)
                    migration.assert_called_once()
                    stage.assert_not_called()
                    attention.assert_not_called()
                    fallback.assert_not_called()
                    self.assertEqual(evaluate.call_count, 0 if phase == "construct" else 1)
                    self.assertEqual(save.call_count, 1 if phase == "save" else 0)

    def test_migration_reads_configuration_without_silent_default(self):
        index = Index(migration_stage_graph()[0])
        with patch.object(adaptive, "read_required_settings", return_value={"cross_core_copy_delay_cycles": 17}), \
             patch.object(adaptive, "migration_construct", wraps=migration_construct) as migration:
            _, calls, _, selection = adaptive.evaluate_candidates(index, 5, Mock(return_value={"makespan": 1}), Mock())
        migration.assert_called_once_with(index, 5, mode="single_cut", cross_core_delay_cycles=17)
        self.assertEqual(calls, 1)
        self.assertEqual(selection["router"]["route"], "stage")
        self.assertIn("500-cycle", selection["router"]["migration_guard_reason"])
        with patch.object(adaptive, "read_required_settings", side_effect=OSError("missing config")), \
             patch.object(adaptive, "migration_construct") as migration, \
             patch.object(adaptive, "stage_construct") as stage:
            evaluate, save = Mock(), Mock()
            with self.assertRaises(OSError):
                adaptive.evaluate_candidates(index, 5, evaluate, save)
            migration.assert_not_called()
            stage.assert_not_called()
            evaluate.assert_not_called()
            save.assert_not_called()

    def test_real_attention_ffn_routes_and_saves_exactly_one_candidate(self):
        for cores in (1, 2, 5):
            with self.subTest(cores=cores):
                builder, _, diamonds = attention_ffn_graph()
                graph, original = builder.graph, deepcopy(builder.graph)
                index = Index(graph)
                expected, expected_meta = attention_construct(index, cores, cross_delay=500, pack_ffn=True)
                result = {"makespan": 987654, "full_result_field": {"untouched": True}}
                refs = {"plan": {"path": "seed-plan.json", "sha256": "p"},
                        "result": {"path": "seed-result.json.gz", "sha256": "r"}}
                evaluate, save = Mock(return_value=result), Mock(return_value=refs)
                with patch.object(adaptive, "stage_construct", wraps=stage_construct) as stage, \
                     patch.object(adaptive, "attention_construct", wraps=attention_construct) as attention, \
                     patch.object(adaptive, "guarded_candidates") as fallback:
                    winner, calls, records, selection = adaptive.evaluate_candidates(index, cores, evaluate, save)
                stage.assert_called_once()
                attention.assert_called_once_with(index, cores, cross_delay=500, pack_ffn=True)
                fallback.assert_not_called()
                evaluate.assert_called_once_with(expected)
                save.assert_called_once_with("seed", expected, result)
                self.assertEqual(winner[0], expected)
                self.assertIs(winner[1], result)
                self.assertEqual(winner[2], "attention_rows_ffn")
                self.assertEqual(calls, 1)
                self.assertEqual(len(records), 1)
                self.assertIs(records[0]["artifacts"], refs)
                meta = records[0]["metadata"]
                for key, value in expected_meta.items():
                    self.assertEqual(meta[key], value)  # Preserve all constructor diagnostics.
                self.assertEqual(meta["packed_ffn_count"], len(diamonds))
                self.assertEqual(meta["route"], "attention")
                self.assertTrue(meta["pack_ffn"])
                self.assertNotIn("collector_core", meta)
                routing = selection["router"]
                self.assertEqual(routing, meta["router"])
                self.assertEqual(routing["route"], "attention")
                self.assertEqual(routing["stage_construct_attempts"], 1)
                self.assertEqual(routing["stage_candidate_plans"], 0)
                self.assertEqual(routing["attention_construct_attempts"], 1)
                self.assertEqual(routing["attention_candidate_plans"], 1)
                self.assertEqual(routing["attention_cross_delay_cycles"], 500)
                self.assertEqual(routing["guarded_policy_invocations"], 0)
                self.assertEqual(routing["route_e0_limit"], 1)
                self.assertEqual(routing["evaluation_calls"], evaluate.call_count)
                self.assertIn("stage_guard_reason", routing)
                self.assertNotIn("attention_guard_reason", routing)
                self.assertEqual(set(winner[0]), {"node_to_subgraph", "core_schedules"})
                words = plan_words(expected)
                owner = {u: c for c, word in enumerate(words) for u in word}
                self.assertEqual(set(owner), set(index.ops))
                for diamond in diamonds:
                    self.assertEqual(len({owner[op[0]] for op in diamond}), 1)
                self.assertEqual(graph, original)

    def test_attention_uses_frozen_config_delay_and_config_errors_propagate(self):
        index = Index(attention_ffn_graph()[0].graph)
        expected, _ = attention_construct(index, 2, cross_delay=17, pack_ffn=True)
        with patch.object(adaptive, "read_required_settings", return_value={"cross_core_copy_delay_cycles": 17}) as read, \
             patch.object(adaptive, "attention_construct", wraps=attention_construct) as attention:
            winner, _, _, selection = adaptive.evaluate_candidates(index, 2, Mock(return_value={"makespan": 10}), Mock())
        read.assert_called_once_with(adaptive.ROOT / "data/raw/a/official/data/config.txt", "multicore_scene_b",
                                     ("cross_core_copy_delay_cycles",))
        attention.assert_called_once_with(index, 2, cross_delay=17, pack_ffn=True)
        self.assertEqual(winner[0], expected)
        self.assertEqual(selection["router"]["attention_cross_delay_cycles"], 17)
        for failure in (OSError("missing config"), EvaluationValidationError("bad config")):
            with self.subTest(failure=type(failure).__name__), \
                 patch.object(adaptive, "read_required_settings", side_effect=failure), \
                 patch.object(adaptive, "attention_construct") as attention, \
                 patch.object(adaptive, "guarded_candidates") as fallback:
                evaluate, save = Mock(), Mock()
                with self.assertRaises(type(failure)):
                    adaptive.evaluate_candidates(index, 2, evaluate, save)
                attention.assert_not_called()
                fallback.assert_not_called()
                evaluate.assert_not_called()
                save.assert_not_called()

    def run_guarded_comparison(self, policy, graph, scores, lower=None):
        values = iter(scores)
        evaluated, saved = [], []

        def evaluate(plan):
            evaluated.append(deepcopy(plan))
            value = next(values)
            if isinstance(value, Exception):
                raise value
            return {"makespan": value}

        def save(name, plan, result):
            saved.append((name, deepcopy(plan), deepcopy(result)))
            return {"path": name}

        if lower is None:
            output = policy(Index(graph), 4, evaluate, save)
        else:
            bound = {"with_cross_core_delay": {"lower_bound_cycles": lower}}
            with patch("src.q3.guarded_solve.analyze", return_value=bound), \
                 patch("src.q3.guarded_solve.release", return_value=(
                     {"candidate": 1}, {"strategy": "release_place_forest"})):
                output = policy(Index(graph), 2, evaluate, save)
        return output, evaluated, saved

    def assert_same_guarded_policy(self, graph, scores, lower=None):
        direct, direct_evaluated, direct_saved = self.run_guarded_comparison(guarded, graph, scores, lower)
        with patch.object(adaptive, "guarded_candidates", wraps=guarded) as fallback:
            routed, evaluated, saved = self.run_guarded_comparison(adaptive.evaluate_candidates, graph, scores, lower)
        fallback.assert_called_once()
        self.assertEqual(routed[:3], direct[:3])
        self.assertEqual(evaluated, direct_evaluated)
        self.assertEqual(saved, direct_saved)
        self.assertEqual({k: v for k, v in routed[3].items() if k != "router"}, direct[3])
        route = routed[3]["router"]
        self.assertEqual(route["route"], "guarded")
        self.assertEqual(route["evaluation_calls"], len(evaluated))
        self.assertEqual(route["guarded_policy_invocations"], 1)
        self.assertEqual(route["stage_candidate_plans"], 0)
        self.assertEqual(route["stage_construct_attempts"], 1)
        self.assertEqual(route["attention_construct_attempts"], 1)
        self.assertEqual(route["attention_candidate_plans"], 0)
        self.assertIn("stage_guard_reason", route)
        self.assertIn("attention_guard_reason", route)
        self.assertEqual(route["route_e0_limit"], 2)
        self.assertLessEqual(len(evaluated), 2)
        return routed

    def test_nonstage_tree_preserves_guarded_choices_and_call_budget(self):
        for scores, lower in (([100, 90], 80), ([100, 100], 80),
                              ([100, 130], 80), ([100], 100),
                              ([100, EvaluationValidationError("capacity")], 80)):
            with self.subTest(scores=scores, lower=lower):
                self.assert_same_guarded_policy(reduction_graph(), scores, lower)

    def test_nonstage_forest_preserves_existing_overlap_policy(self):
        graph = {"ops": [], "tensors": [], "edges": []}
        for j in range(20):
            graph["ops"].extend({"id": 3*j+u, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": 1}
                                for u in range(3))
            graph["edges"].extend({"source": 3*j+u, "target": 3*j+2} for u in (0, 1))
        output = self.assert_same_guarded_policy(graph, [100])
        self.assertEqual(output[1], 1)
        self.assertEqual(output[2][-1]["status"], "unsupported")
        self.assertIn("uncut", output[2][-1]["reason"])

    def test_strict_tensor_guard_rejection_routes_to_guarded(self):
        graph, layout = stage_graph()
        graph["edges"].append({"source": layout["immutable"][1],
                               "target": layout["stages"][0]["chains"][0][-1]})
        index = Index(graph)
        sentinel = (({"fallback": 1}, {"makespan": 7}, "fallback"), 1, [], {"rule": "sentinel"})
        evaluate, save = Mock(), Mock()
        with patch.object(adaptive, "guarded_candidates", return_value=sentinel) as fallback:
            out = adaptive.evaluate_candidates(index, 2, evaluate, save)
        fallback.assert_called_once_with(index, 2, evaluate, save)
        self.assertEqual(out[:3], sentinel[:3])
        self.assertIn("lane-internal tensor input", out[3]["router"]["stage_guard_reason"])
        evaluate.assert_not_called()
        save.assert_not_called()

    def test_attention_raw_closure_rejection_reaches_guarded_without_scoring(self):
        builder, row, _ = attention_ffn_graph()
        builder.op("RELU", "PIPE_V", 3, [row["exp"][1]])
        index = Index(builder.graph)
        sentinel = (({"fallback": 1}, {"makespan": 7}, "fallback"), 1, [], {"rule": "sentinel"})
        evaluate, save = Mock(), Mock()
        with patch.object(adaptive, "attention_construct", wraps=attention_construct) as attention, \
             patch.object(adaptive, "guarded_candidates", return_value=sentinel) as fallback:
            out = adaptive.evaluate_candidates(index, 2, evaluate, save)
        attention.assert_called_once_with(index, 2, cross_delay=500, pack_ffn=True)
        fallback.assert_called_once_with(index, 2, evaluate, save)
        self.assertEqual(out[:3], sentinel[:3])
        self.assertIn("interior compute consumer", out[3]["router"]["attention_guard_reason"])
        self.assertEqual(out[3]["router"]["attention_candidate_plans"], 0)
        evaluate.assert_not_called()
        save.assert_not_called()

    def test_incidental_case_names_and_history_do_not_affect_structural_routes(self):
        for graph, cores in ((stage_graph()[0], 2), (attention_ffn_graph()[0].graph, 2),
                             (migration_stage_graph()[0], 5)):
            outcomes = []
            for label, historical in (("unseen-a", 1), ("unseen-b", 10**12)):
                tagged = deepcopy(graph)
                tagged["case_id"] = label
                tagged["historical_results"] = {"makespan": historical}
                evaluate, save = Mock(return_value={"makespan": 123}), Mock(return_value={})
                outcomes.append(adaptive.evaluate_candidates(Index(tagged), cores, evaluate, save))
                evaluate.assert_called_once()
                save.assert_called_once()
            self.assertEqual(outcomes[0], outcomes[1])

    def test_constructor_defects_do_not_silently_fallback(self):
        index = Index(stage_graph()[0])
        for failure in (RuntimeError("bug"), AssertionError("invariant"), ValueError("bad option")):
            with self.subTest(failure=type(failure).__name__):
                evaluate, save = Mock(), Mock()
                with patch.object(adaptive, "stage_construct", side_effect=failure), \
                     patch.object(adaptive, "attention_construct") as attention, \
                     patch.object(adaptive, "guarded_candidates") as fallback:
                    with self.assertRaises(type(failure)):
                        adaptive.evaluate_candidates(index, 2, evaluate, save)
                fallback.assert_not_called()
                attention.assert_not_called()
                evaluate.assert_not_called()
                save.assert_not_called()

    def test_attention_constructor_defects_do_not_silently_fallback(self):
        index = Index(attention_ffn_graph()[0].graph)
        for failure in (RuntimeError("bug"), AssertionError("invariant"), ValueError("bad option"),
                        EvaluationValidationError("constructor invalid")):
            with self.subTest(failure=type(failure).__name__):
                evaluate, save = Mock(), Mock()
                with patch.object(adaptive, "attention_construct", side_effect=failure) as attention, \
                     patch.object(adaptive, "guarded_candidates") as fallback:
                    with self.assertRaises(type(failure)):
                        adaptive.evaluate_candidates(index, 2, evaluate, save)
                attention.assert_called_once()
                fallback.assert_not_called()
                evaluate.assert_not_called()
                save.assert_not_called()

    def test_evaluation_failures_do_not_trigger_fallback_or_save(self):
        for route, graph in (("stage", stage_graph()[0]), ("attention", attention_ffn_graph()[0].graph)):
            index = Index(graph)
            for failure in (EvaluationValidationError("capacity"), UnsupportedStructure("from evaluator"),
                            RuntimeError("runtime")):
                with self.subTest(route=route, failure=type(failure).__name__):
                    evaluate, save = Mock(side_effect=failure), Mock()
                    with patch.object(adaptive, "attention_construct", wraps=attention_construct) as attention, \
                         patch.object(adaptive, "guarded_candidates") as fallback:
                        with self.assertRaises(type(failure)):
                            adaptive.evaluate_candidates(index, 2, evaluate, save)
                    self.assertEqual(attention.call_count, 0 if route == "stage" else 1)
                    evaluate.assert_called_once()
                    save.assert_not_called()
                    fallback.assert_not_called()

    def test_save_failure_is_not_silently_fallback(self):
        for route, graph in (("stage", stage_graph()[0]), ("attention", attention_ffn_graph()[0].graph)):
            for failure in (OSError("disk"), UnsupportedStructure("from save")):
                with self.subTest(route=route, failure=type(failure).__name__):
                    evaluate, save = Mock(return_value={"makespan": 1}), Mock(side_effect=failure)
                    with patch.object(adaptive, "guarded_candidates") as fallback:
                        with self.assertRaises(type(failure)):
                            adaptive.evaluate_candidates(Index(graph), 2, evaluate, save)
                    evaluate.assert_called_once()
                    save.assert_called_once()
                    fallback.assert_not_called()

    def test_fallback_exception_propagates(self):
        with patch.object(adaptive, "guarded_candidates", side_effect=RuntimeError("guarded bug")):
            with self.assertRaisesRegex(RuntimeError, "guarded bug"):
                adaptive.evaluate_candidates(Index(reduction_graph()), 2, Mock(), Mock())

    def test_main_injects_router_into_shared_cli(self):
        with patch.object(adaptive, "run_solver", return_value=17) as run:
            self.assertEqual(adaptive.main(), 17)
        run.assert_called_once_with(policy=adaptive.evaluate_candidates)

    def test_invalid_core_count_is_not_a_structure_fallback(self):
        index = Index(stage_graph()[0])
        for cores in (0, -1, True, 1.5):
            with self.subTest(cores=cores), \
                 patch.object(adaptive, "migration_construct") as migration, \
                 patch.object(adaptive, "stage_construct") as construct, \
                 patch.object(adaptive, "attention_construct") as attention, \
                 patch.object(adaptive, "guarded_candidates") as fallback:
                with self.assertRaises(ValueError):
                    adaptive.evaluate_candidates(index, cores, Mock(), Mock())
                construct.assert_not_called()
                migration.assert_not_called()
                attention.assert_not_called()
                fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
