"""Synthetic structure/controller contracts; no real E0/E1/E2 scoring.

These checks establish routing, submission shape and guarded selection only.
They do not establish capacity safety, simulated quality or full-matrix speed.
"""
import copy
from contextlib import ExitStack
import hashlib
import json
import sys
import unittest
from unittest.mock import Mock, patch

from src.q1 import unified
from src.q1.fork_frontier import construct as construct_fork
from tests.q1.test_component_pack import graph


def candidate(name, task):
    plan = {"node_to_subgraph": {"1": task}, "core_schedules": [[task], []]}
    return {"name": name, "plan": plan,
            "plan_sha256": hashlib.sha256(unified.plan_bytes(plan)).hexdigest()}


def scored(makespan, copy_bytes):
    return {"status": "ok", "makespan": makespan,
            "data_movement_bytes": {"scheduled_copy_bytes": copy_bytes}}


def private_inputs(sizes):
    g = graph([(u, "V", 10) for u in range(1, len(sizes) + 1)], [])
    for u, size in enumerate(sizes, 1):
        t = 1000 + u
        g["tensors"].append({"id": t, "size": size, "pos": "L1"})
        g["edges"].append({"source": t, "target": u})
    return g


def repeated_fork_join(stages=2):
    nodes, links, branches, accumulator = [], [], [], None
    next_id = 1
    for _ in range(stages):
        leaves = []
        for _ in range(4):
            chain = list(range(next_id, next_id + 3))
            next_id += 3
            nodes.extend((u, "V", 500) for u in chain)
            links.extend(zip(chain, chain[1:]))
            if accumulator is not None:
                links.append((accumulator, chain[0]))
            leaves.append(chain[-1])
            branches.append(chain)
        accumulator = leaves[0]
        for leaf in leaves[1:]:
            nodes.append((next_id, "V", 1))
            links.extend([(accumulator, next_id), (leaf, next_id)])
            accumulator = next_id
            next_id += 1
    return graph(nodes, links), links, branches


class PlanContract(unittest.TestCase):
    def assert_plan_contract(self, plan, graph_input, cores, compute_links):
        """Independently check exact coverage and the augmented Task DAG."""
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
        expected = {o["id"] for o in graph_input["ops"]
                    if o["op"] not in {"COPY_IN", "COPY_OUT"}}
        self.assertEqual(set(mapping), expected)
        self.assertEqual(len(mapping), len(plan["node_to_subgraph"]))
        schedules = plan["core_schedules"]
        self.assertEqual(len(schedules), cores)
        scheduled = [t for order in schedules for t in order]
        self.assertEqual(len(scheduled), len(set(scheduled)))
        self.assertEqual(set(scheduled), set(mapping.values()))
        successors = {t: set() for t in scheduled}
        for u, v in compute_links:
            if mapping[u] != mapping[v]:
                successors[mapping[u]].add(mapping[v])
        for order in schedules:
            for a, b in zip(order, order[1:]):
                successors[a].add(b)
        indegree = dict.fromkeys(scheduled, 0)
        for targets in successors.values():
            for t in targets:
                indegree[t] += 1
        ready = [t for t, degree in indegree.items() if degree == 0]
        visited = 0
        while ready:
            visited += 1
            for t in successors[ready.pop()]:
                indegree[t] -= 1
                if indegree[t] == 0:
                    ready.append(t)
        self.assertEqual(visited, len(scheduled), "Augmented Task graph is cyclic")


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.items = [candidate(name, i) for i, name in enumerate("BHOF")]

    def test_single_candidate_never_calls_scorer(self):
        score = Mock(side_effect=AssertionError("Unexpected online scoring"))
        winner, records, reason = unified.choose(self.items[:1], score)
        self.assertIs(winner, self.items[0])
        self.assertEqual(records, [])
        self.assertEqual(reason, "single-distinct-plan")
        score.assert_not_called()

    def test_makespan_precedes_ddr_and_exact_ties_keep_first(self):
        score = Mock(side_effect=[scored(100, 0), scored(90, 900),
                                  scored(90, 800), scored(90, 800)])
        winner, records, reason = unified.choose(self.items, score)
        self.assertIs(winner, self.items[2])
        self.assertEqual([r["name"] for r in records], list("BHOF"))
        self.assertEqual(reason, "all-distinct-plans-scored")
        self.assertEqual(score.call_count, 4)

    def test_reported_failure_retains_scored_winner_and_stops(self):
        score = Mock(side_effect=[scored(100, 20), scored(80, 30),
                                  {"status": "timeout"}, scored(1, 0)])
        winner, records, reason = unified.choose(self.items, score)
        self.assertIs(winner, self.items[1])
        self.assertEqual(reason, "first-score-failure")
        self.assertEqual(records[-1]["status"], "timeout")
        self.assertEqual(score.call_count, 3)

    def test_exception_retains_scored_winner_and_stops(self):
        score = Mock(side_effect=[scored(100, 20), scored(80, 30),
                                  RuntimeError("synthetic worker exit"), scored(1, 0)])
        winner, records, reason = unified.choose(self.items, score)
        self.assertIs(winner, self.items[1])
        self.assertEqual(reason, "first-score-failure")
        self.assertEqual(records[-1]["status"], "error")
        self.assertEqual(records[-1]["error_type"], "RuntimeError")
        self.assertEqual(score.call_count, 3)

    def test_first_failure_returns_baseline_without_claiming_it_scored_ok(self):
        score = Mock(return_value={"status": "invalid", "message": "synthetic"})
        winner, records, reason = unified.choose(self.items, score)
        self.assertIs(winner, self.items[0])
        self.assertEqual(reason, "first-score-failure")
        self.assertEqual([r["status"] for r in records], ["invalid"])
        score.assert_called_once_with(self.items[0]["plan"])

    def test_empty_candidate_set_is_rejected(self):
        with self.assertRaises(ValueError):
            unified.choose([], Mock())

    def test_events_keep_requested_and_returned_scores_distinct(self):
        events = []
        score = Mock(side_effect=[scored(100, 20), RuntimeError('startup failed')])
        _, records, _ = unified.choose(self.items, score, emit=events.append)
        self.assertEqual([e['event'] for e in events],
                         ['score_attempt_started', 'score_attempt_returned'] * 2)
        self.assertEqual(events[-1]['status'], 'error')
        self.assertEqual(events[-1]['name'], 'H')
        self.assertNotIn('worker_pid', records[-1])


class RoutingTests(PlanContract):
    constructors = ("bounded", "heavy", "overload", "shared_input", "fork_frontier")

    def test_optional_constructor_failure_keeps_baseline_and_emits_record(self):
        g = graph([(1, 'V', 10), (2, 'V', 10)], [])
        events = []
        with patch.object(unified, 'heavy', side_effect=RuntimeError('synthetic proposal failure')):
            items, d = unified.generate_candidates(g, 2, emit=events.append)
        self.assertEqual(items[0]['name'], 'bounded')
        self.assertEqual(d['construction_failures'][0]['name'], 'heavy-or-sink')
        self.assertIn('candidate_construction_failed', [e['event'] for e in events])
        self.assert_plan_contract(items[0]['plan'], g, 2, [])

    def generate_mocked(self, g, cores, identical=False):
        with ExitStack() as stack:
            mocks = {}
            for index, name in enumerate(self.constructors):
                task = 0 if identical else index
                plan = {"node_to_subgraph": {
                    o["id"]: task for o in g["ops"]
                    if o["op"] not in {"COPY_IN", "COPY_OUT"}},
                    "core_schedules": [[task]] + [[] for _ in range(cores - 1)]}
                mocks[name] = stack.enter_context(patch.object(
                    unified, name, return_value=(plan, {"synthetic_constructor": name})))
            candidates, diagnostics = unified.generate_candidates(g, cores)
        self.assertLessEqual(len(candidates), 4)
        self.assertEqual(unified.MAX_DISTINCT_CANDIDATES, 4)
        return candidates, diagnostics, mocks

    def test_large_private_input_union_activates_shared_route(self):
        # Requiring a truly shared tensor would miss this depth-window regime.
        g = private_inputs([300000, 300000])
        candidates, d, mocks = self.generate_mocked(g, 2)
        self.assertEqual(d["features"]["shared_external_input_bytes"], 0)
        self.assertEqual(d["features"]["external_input_bytes"], 600000)
        self.assertEqual(d["features"]["additional_route"], "shared-input")
        self.assertEqual([c["name"] for c in candidates],
                         ["bounded", "heavy-or-sink", "overload", "shared-input"])
        mocks["shared_input"].assert_called_once_with(g, 2)
        mocks["fork_frontier"].assert_not_called()
        for c in candidates:
            self.assert_plan_contract(c["plan"], g, 2, [])

    def test_shared_threshold_is_strict_and_uses_union_not_read_count(self):
        for size, expected in [(524288, "none"), (524289, "shared-input")]:
            with self.subTest(size=size):
                g = graph([(1, "V", 10), (2, "V", 10)], [])
                g["tensors"] = [{"id": 1001, "size": size, "pos": "L1"}]
                g["edges"] = [{"source": 1001, "target": u} for u in (1, 2)]
                _, d, mocks = self.generate_mocked(g, 2)
                self.assertEqual(d["features"]["external_input_bytes"], size)
                self.assertEqual(d["features"]["additional_route"], expected)
                self.assertEqual(mocks["shared_input"].call_count,
                                 int(expected == "shared-input"))

    def test_component_shortage_with_fork_activates_only_fang_additional_route(self):
        links = [(1, 2), (1, 3), (2, 4), (3, 4)]
        g = graph([(u, "V", 10) for u in range(1, 5)], links)
        # A huge external union must not override the component-shortage route.
        g["tensors"].append({"id": 2000, "size": 600000, "pos": "L1"})
        g["edges"].append({"source": 2000, "target": 1})
        candidates, d, mocks = self.generate_mocked(g, 2)
        self.assertEqual(d["features"]["components"], 1)
        self.assertEqual(d["features"]["forks"], 1)
        self.assertEqual(d["features"]["additional_route"], "fork-frontier")
        self.assertEqual([c["name"] for c in candidates],
                         ["bounded", "heavy-or-sink", "overload", "fork-frontier"])
        mocks["fork_frontier"].assert_called_once_with(g, 2, grain=4)
        mocks["shared_input"].assert_not_called()

    def test_component_shortage_without_fork_keeps_three_primary_candidates(self):
        g = graph([(u, "V", 10) for u in (1, 2, 3)], [(1, 2), (2, 3)])
        candidates, d, mocks = self.generate_mocked(g, 5)
        self.assertEqual(d["features"]["additional_route"], "none")
        self.assertEqual([c["name"] for c in candidates],
                         ["bounded", "heavy-or-sink", "overload"])
        mocks["fork_frontier"].assert_not_called()
        mocks["shared_input"].assert_not_called()

    def test_single_core_skips_feature_analysis_and_other_constructors(self):
        g = graph([(1, "V", 10)], [])
        with patch.object(unified, "_view", side_effect=AssertionError("Unexpected view")):
            candidates, d, mocks = self.generate_mocked(g, 1)
        self.assertEqual([c["name"] for c in candidates], ["bounded"])
        self.assertEqual(d["features"], {"cores": 1})
        for name in self.constructors[1:]:
            mocks[name].assert_not_called()

    def test_exact_duplicate_plans_are_not_scored_multiple_times(self):
        g = private_inputs([300000, 300000])
        candidates, d, _ = self.generate_mocked(g, 2, identical=True)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(d["duplicates"]), 3)
        self.assertEqual({x["duplicate_of"] for x in d["duplicates"]}, {"bounded"})
        score = Mock(side_effect=AssertionError("Duplicate-only scoring"))
        self.assertEqual(unified.choose(candidates, score)[1], [])
        score.assert_not_called()

    def test_mapping_order_and_task_ids_are_not_semantically_rehashed(self):
        a = {"node_to_subgraph": {1: 9, 2: 9}, "core_schedules": [[9], []]}
        b = {"node_to_subgraph": {2: 9, 1: 9}, "core_schedules": [[9], []]}
        self.assertEqual(a, b)
        self.assertNotEqual(unified.plan_bytes(a), unified.plan_bytes(b))
        self.assertEqual(list(json.loads(unified.plan_bytes(b))["node_to_subgraph"]),
                         ["2", "1"])
        c = {"node_to_subgraph": {1: 10, 2: 10}, "core_schedules": [[10], []]}
        self.assertNotEqual(unified.plan_bytes(a), unified.plan_bytes(c))

    def test_invalid_core_domains_fail_before_construction(self):
        with patch.object(unified, "bounded") as bounded:
            for bad in (0, 6, True, False, 2.0, "2", None):
                with self.subTest(cores=bad), self.assertRaises(ValueError):
                    unified.generate_candidates({}, bad)
            bounded.assert_not_called()


class SyntheticIntegrationTests(PlanContract):
    def test_single_core_solve_has_no_evaluator_import_or_score(self):
        g, links, _ = repeated_fork_join(1)
        # A real evaluator import is deliberately impossible in this test.
        with patch.dict(sys.modules, {"src.eval_exact": None}):
            plan, diagnostics = unified.solve(g, 1)
        self.assert_plan_contract(plan, g, 1, links)
        self.assertEqual(diagnostics["online_scores"], [])
        self.assertEqual(diagnostics["actual_e1_calls"], 0)
        self.assertEqual(diagnostics["online_score_attempts"], 0)
        self.assertEqual(diagnostics["stop_reason"], "single-distinct-plan")

    def test_real_constructors_keep_submission_and_task_order_on_small_graphs(self):
        cases = [repeated_fork_join(2)[:2]]
        links = [(1, 2), (1, 3)]
        cases.append((graph([(1, "V", 10000), (2, "V", 40000), (3, "V", 40000),
                             (10, "M", 200000), (11, "M", 1), (12, "M", 1)], links), links))
        cases.append((private_inputs([300000, 300000]), []))
        with patch.dict(sys.modules, {"src.eval_exact": None}):
            for g, compute_links in cases:
                original = copy.deepcopy(g)
                for cores in (1, 2, 5):
                    with self.subTest(nodes=len(g["ops"]), cores=cores):
                        candidates, _ = unified.generate_candidates(g, cores)
                        self.assertLessEqual(len(candidates), 4)
                        self.assertEqual(len({c["plan_sha256"] for c in candidates}),
                                         len(candidates))
                        for c in candidates:
                            self.assert_plan_contract(c["plan"], g, cores, compute_links)
                            self.assertEqual(hashlib.sha256(unified.plan_bytes(c["plan"])).hexdigest(),
                                             c["plan_sha256"])
                        self.assertEqual(g, original)

    def test_fang_adapter_preserves_serial_branches_and_shared_reduction_tails(self):
        g, links, branches = repeated_fork_join(2)
        original = copy.deepcopy(g)
        plan, d = construct_fork(g, 2)
        self.assert_plan_contract(plan, g, 2, links)
        self.assertEqual(d["stages"], 2)
        self.assertEqual([t["ops"] for t in d["tasks"] if t["phase"] == 1], [3, 3])
        for branch in branches:
            self.assertEqual(len({plan["node_to_subgraph"][u] for u in branch}), 1)
        reversed_edges = copy.deepcopy(g)
        reversed_edges["edges"].reverse()
        self.assertEqual(construct_fork(reversed_edges, 2), (plan, d))
        self.assertEqual(g, original)

    def test_fang_adapter_contracts_copy_bridges_before_fork_partition(self):
        g = graph([(1, "V", 10), (2, "M", 1), (3, "V", 100), (4, "V", 100)],
                  [(1, 2), (2, 3), (1, 4)])
        g["ops"][1]["op"] = "COPY_IN"
        plan, _ = construct_fork(g, 2)
        self.assert_plan_contract(plan, g, 2, [(1, 3), (1, 4)])
        self.assertNotIn(2, plan["node_to_subgraph"])


if __name__ == "__main__":
    unittest.main()
