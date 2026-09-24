"""Synthetic-only independent plan/metadata audit; no Task compiler or evaluator."""
from collections import Counter, defaultdict
import copy
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SOURCE = "288dd520caa5c7baaa1413e4021eb2d4221b6e66"
TARGET = Path(sys.argv.pop(1)).resolve()
OUT = Path(__file__).resolve().parent
RECEIPTS = {}
for name in ["src/q1/shared_input_budget.py", "src/q1/bounded_tasks.py", "src/q1/tree_frontier.py",
             "src/q1/component_pack.py", "tests/q1/test_shared_input_budget.py", "tests/q1/test_component_pack.py",
             "docs/a/Q1_SHARED_INPUT_BUDGET.md", "data/raw/a/official/code/evaluation_validation.py",
             "data/raw/a/official/code/stub_multicore_cut_and_schedule.py",
             "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py", "data/raw/a/official/data/config.txt"]:
    raw = subprocess.check_output(["git", "show", SOURCE + ":" + name], cwd=TARGET)
    assert (TARGET / name).read_bytes() == raw
    RECEIPTS[name] = hashlib.sha256(raw).hexdigest()
sys.path.insert(0, str(TARGET))
from src.q1 import shared_input_budget as method
from src.q1.bounded_tasks import construct as bounded
from tests.q1.test_component_pack import graph
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order

OBSERVATIONS = {}


def plan_metadata(g, p, info):
    """Literal boundary conditions applied per final Task, independent of metadata packer."""
    assert set(p) == {"node_to_subgraph", "core_schedules"}
    v = derive_multicore_plan(g, p)
    validate_task_order(v)
    assert len(p["core_schedules"]) == info["requested_cores"]
    a = info["active_cores"]
    assert all(not order for order in p["core_schedules"][a:])
    assert all(v["core_by_subgraph"][u] == v["core_by_subgraph"][w] for u, w in v["dependency_pairs"])
    ops = {o["id"]: o for o in g["ops"]}
    tensors = {t["id"]: t for t in g["tensors"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    for e in g["edges"]:
        x, y = e["source"], e["target"]
        if x in ops and y in tensors:
            producers[y].add(x)
        if x in tensors and y in ops:
            consumers[x].add(y)
    compute = set(v["mapping"])
    external = {t for t in tensors if consumers[t] & compute and not producers[t] & compute}
    copy_bytes = service = input_bytes = 0
    max_union = over = 0
    weights = dict.fromkeys(range(a), 0)
    compute_counts = dict.fromkeys(range(a), 0)
    bandwidth = info["fixed_bandwidth_bytes_per_cycle"]
    for task, nodes in v["nodes_by_subgraph"].items():
        members = set(nodes)
        union = 0
        for t, tensor in tensors.items():
            lp, lc = producers[t] & members, consumers[t] & members
            eligible = consumers[t] & compute
            source = bool(lc) and not lp
            sink = bool(lp) and (any(ops[u]["op"] == "COPY_OUT" for u in consumers[t]) or not eligible or eligible - members)
            n = int(bool(source)) + int(bool(sink))
            copy_bytes += n * tensor["size"]
            service += n * max(1, (tensor["size"] + bandwidth - 1) // bandwidth)
            if t in external and lc:
                union += tensor["size"]
        input_bytes += union
        max_union = max(max_union, union)
        over += union > info["input_budget_bytes"]
        work = Counter()
        for u in members:
            work[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
        core = v["core_by_subgraph"][task]
        weights[core] += max(work.values())
        compute_counts[core] += len(members)
    same = info["fixed_task_waits"]["task_same_core_wait_cycles"]
    core_counts = [len(order) for order in p["core_schedules"][:a]]
    costs = [weights[c] + max(0, core_counts[c] - 1) * same for c in range(a)]
    expected = dict(total_copy_proxy_bytes=copy_bytes, ddr_service_proxy_cycles=service,
                    input_copy_proxy_bytes=input_bytes,
                    input_repeat_proxy_bytes=input_bytes - sum(tensors[t]["size"] for t in external),
                    task_counts_by_core=core_counts, core_compute_ops=list(compute_counts.values()),
                    max_window_input_union_bytes=max_union, windows_over_input_budget=over,
                    window_pipe_work_proxy_by_core=list(weights.values()),
                    max_compute_with_wait_proxy_cycles=max(costs),
                    cost_proxy_cycles=max(max(costs), service),
                    base_task_count=len(info["task_refinements"]),
                    phase_limit_base_tasks=sum(t["phase_limit_fallback"] for t in info["task_refinements"]))
    for key, value in expected.items():
        assert info["chosen_configuration"][key] == value, (key, info["chosen_configuration"][key], value)
    return expected


class IndependentTests(unittest.TestCase):
    def check(self, g, k, **kw):
        before = copy.deepcopy(g)
        with patch.object(method, "bounded_construct", wraps=bounded) as call:
            p, d = method.construct(g, k, **kw)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[1], d["active_cores"])
        self.assertEqual(d["selected"], "shared-input-budget")
        self.assertEqual(g, before)
        return p, d, plan_metadata(g, p, d)

    def test_full_4096_chunk_route_actual_plan_metadata(self):
        g = graph([(i, "M", 0) for i in range(4100)], [])
        g["tensors"] = [{"id": 10000, "size": 600000, "pos": "L1"}]
        g["edges"] = [{"source": 10000, "target": i} for i in range(4100)]
        _, d, evidence = self.check(g, 1, input_budget_bytes=600000, activation_bytes=1)
        self.assertEqual(evidence["base_task_count"], 5)
        self.assertEqual(evidence["total_copy_proxy_bytes"], 3000000)
        self.assertEqual(evidence["window_pipe_work_proxy_by_core"], [4100])
        OBSERVATIONS["full_chunk_route_zero_cycles"] = evidence

    def test_multi_producers_original_copy_out_and_zero_byte_copies(self):
        g = graph([(1, "M", 2), (2, "V", 0), (3, "M", 4)], [(1, 2)])
        # Two compute producers at different depths; terminal tensor also has original COPY_OUT.
        g["tensors"] += [{"id": 2000, "size": 61, "pos": "UB"},
                         {"id": 2001, "size": 0, "pos": "UB"},
                         {"id": 2002, "size": 0, "pos": "DDR"}]
        g["ops"].append({"id": 90, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0})
        g["edges"] += [{"source": 1, "target": 2000}, {"source": 2, "target": 2000},
                       {"source": 2000, "target": 3}, {"source": 3, "target": 2001},
                       {"source": 2001, "target": 90}, {"source": 90, "target": 2002}]
        for u in (1, 2, 3):
            g["tensors"].append({"id": 3000 + u, "size": 1, "pos": "L1"})
            g["edges"].append({"source": 3000 + u, "target": u})
        p, _, evidence = self.check(g, 1, input_budget_bytes=1, activation_bytes=1)
        self.assertEqual(len(p["core_schedules"][0]), 3)
        OBSERVATIONS["multi_producer_zero_byte_output"] = evidence

    def test_empty_input_levels_copy_bridge_and_local_budget_fallback(self):
        g = graph([(1, "M", 10), (2, "MTE2", 1), (3, "V", 10), (4, "M", 10),
                   (5, "V", 10), (10, "M", 1)], [(1, 2), (2, 3), (3, 4), (4, 5)])
        g["ops"][1]["op"] = "COPY_IN"
        for t, target in [(3000, 3), (3001, 5), (3002, 10)]:
            g["tensors"].append({"id": t, "size": 100, "pos": "L1"})
            g["edges"].append({"source": t, "target": target})
        _, _, first = self.check(g, 2, input_budget_bytes=100, activation_bytes=1)
        _, _, second = self.check(g, 2, input_budget_bytes=100, activation_bytes=1, max_phases=1)
        self.assertGreaterEqual(second["phase_limit_base_tasks"], 1)
        OBSERVATIONS["empty_levels_copy_bridge"] = first
        OBSERVATIONS["local_phase_fallback"] = second


def main():
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module("tests.q1.test_shared_input_budget")))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    for name, expected in RECEIPTS.items():
        assert hashlib.sha256((TARGET / name).read_bytes()).hexdigest() == expected
    forbidden = [n for n in sys.modules if n in {"multicore_cut_evaluate_problem_1", "schedule_step1", "schedule_step2", "schedule_step3"}]
    assert not forbidden, forbidden
    record = {"kind": "synthetic_contract_and_metadata_review_not_performance", "source_commit": SOURCE,
              "source_sha256": RECEIPTS, "source_bytes_match_fixed_commit_before_and_after": True,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "tests": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
              "successful": result.wasSuccessful(), "observations": OBSERVATIONS,
              "calls": {"real_graph_construct": 0, "task_compiler": 0, "E0": 0, "E1": 0, "E2": 0},
              "synthetic_constructors_invoked": True, "forbidden_evaluator_modules_loaded": forbidden}
    (OUT / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
