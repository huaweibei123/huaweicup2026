"""Independent synthetic-only checks of fixed component_overload implementation.

Pass the read-only source checkout as the only argument. Never evaluates a graph.
"""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

SOURCE = "3c6e41b938c764d207de45584fb526c64f4eb845"
TARGET = Path(sys.argv.pop(1)).resolve()
OUT = Path(__file__).resolve().parent
CHECKOUT_HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=TARGET, text=True).strip()
RECEIPTS = {}
for name in ["src/q1/component_overload.py", "src/q1/heavy_suffix.py", "src/q1/sink_peel.py",
             "src/q1/bounded_tasks.py", "src/q1/tree_frontier.py", "src/q1/component_pack.py",
             "tests/q1/test_component_overload.py", "tests/q1/test_component_pack.py",
             "docs/a/Q1_COMPONENT_OVERLOAD.md", "data/raw/a/official/code/evaluation_validation.py",
             "data/raw/a/official/code/stub_multicore_cut_and_schedule.py",
             "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
             "data/raw/a/official/data/config.txt"]:
    raw = subprocess.check_output(["git", "show", SOURCE + ":" + name], cwd=TARGET)
    assert (TARGET / name).read_bytes() == raw
    RECEIPTS[name] = hashlib.sha256(raw).hexdigest()
sys.path.insert(0, str(TARGET))
from src.q1.component_overload import construct, _place
from src.q1.bounded_tasks import split_large_tasks
from tests.q1.test_component_pack import graph
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order

OBSERVATIONS = {}


def validate(g, plan):
    assert set(plan) == {"node_to_subgraph", "core_schedules"}
    view = derive_multicore_plan(g, plan)
    validate_task_order(view)
    return view


class IndependentReviewTests(unittest.TestCase):
    def test_strict_integer_ceil_threshold(self):
        rows = []
        for root_work, expected in [(1, False), (2, False), (3, True)]:
            g = graph([(1, "V", root_work), (2, "V", 1), (3, "V", 1),
                       (10, "V", 3), (20, "V", 3)], [(1, 2), (1, 3)])
            p, d = construct(g, 3)
            validate(g, p)
            self.assertEqual(d["selected"] == "overload-list", expected)
            rows.append({"component_work": root_work + 2, "total": root_work + 8,
                         "ceil_total_over_3": (root_work + 10) // 3, "split": expected})
        OBSERVATIONS["threshold"] = rows

    def test_zero_cycles_are_positive_unit_work(self):
        g = graph([(1, "V", 0), (2, "V", 0), (3, "V", 0),
                   (10, "V", 0), (20, "V", 0)], [(1, 2), (1, 3)])
        original = copy.deepcopy(g)
        p, d = construct(g, 3)
        validate(g, p)
        self.assertEqual(d["selected"], "overload-list")
        self.assertEqual(d["total_pipe_work"], {"PIPE_V": 5})
        self.assertTrue(all(w >= 1 for w in d["placement"]["task_compute_weight"]))
        self.assertEqual(g, original)
        OBSERVATIONS["zero_cycles"] = {"effective_total": d["total_pipe_work"], "weights": d["placement"]["task_compute_weight"]}

    def test_two_split_components_and_retained_shared_external_input(self):
        g = graph([(1, "V", 100), (2, "V", 200), (3, "V", 200),
                   (10, "M", 100), (11, "M", 200), (12, "M", 200),
                   (20, "V", 1), (30, "M", 1)], [(1, 2), (1, 3), (10, 11), (10, 12)])
        g["ops"].append({"id": 9000, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 1})
        g["tensors"] += [{"id": 9001, "pos": "DDR", "size": 64}, {"id": 9002, "pos": "UB", "size": 64}]
        g["edges"] += [{"source": 9001, "target": 9000}, {"source": 9000, "target": 9002}]
        g["edges"] += [{"source": 9002, "target": u} for u in (1, 10, 20, 30)]
        original = copy.deepcopy(g)
        p, d = construct(g, 4)
        v = validate(g, p)
        self.assertEqual(len(d["split_components"]), 2)
        self.assertEqual(d["components"], 4)
        self.assertEqual(d["retained_components"], 2)
        rank = {t: i for i, t in enumerate(d["placement"]["placement_order"])}
        edges = v["dependency_pairs"] + [(a, b) for order in p["core_schedules"] for a, b in zip(order, order[1:])]
        self.assertTrue(all(rank[a] < rank[b] for a, b in edges))
        self.assertEqual(list(p["node_to_subgraph"]), [o["id"] for o in g["ops"] if o["op"] != "COPY_IN"])
        self.assertEqual(g, original)
        self.assertEqual((p, d), construct(g, 4))
        OBSERVATIONS["two_components"] = {"split_anchors": [x["anchor"] for x in d["split_components"]],
                                           "placement_rank": rank, "augmented_edges": edges}

    def test_copy_chain_stays_within_component_before_wave_partition(self):
        g = graph([(1, "V", 100), (2, "V", 200), (3, "V", 200),
                   (10, "M", 1), (20, "M", 1),
                   (90, "MTE3", 1), (91, "MTE2", 1)],
                  [(1, 90), (90, 91), (91, 2), (1, 3)])
        g["ops"][-2]["op"], g["ops"][-1]["op"] = "COPY_OUT", "COPY_IN"
        p, d = construct(g, 3)
        v = validate(g, p)
        self.assertEqual(d["components"], 3)
        self.assertEqual(d["selected"], "overload-list")
        self.assertNotIn(90, p["node_to_subgraph"])
        self.assertNotIn(91, p["node_to_subgraph"])
        self.assertIn((p["node_to_subgraph"][1], p["node_to_subgraph"][2]), v["dependency_pairs"])

    def test_official_gate_algebra_same_and_cross_core(self):
        g = graph([(1, "V", 10), (2, "V", 1000), (3, "V", 1000)], [(1, 2), (1, 3)])
        ops = {o["id"]: o for o in g["ops"]}
        p, d = _place([[1], [2], [3]], {1: {2, 3}, 2: set(), 3: set()}, ops, 2, 100, 1000)
        validate(g, p)
        self.assertEqual(p["core_schedules"], [[0, 1], [2]])
        self.assertEqual(d["task_start_proxy"], [0, 110, 1010])
        # Same core adds only previous-task wait once; remote depends on end+1000.
        OBSERVATIONS["gates"] = {"schedules": p["core_schedules"], "starts": d["task_start_proxy"]}

    def test_soft_chunks_preserve_global_block_order(self):
        g = graph([(i, "V", 1) for i in range(1, 6)], [(1, 2), (3, 5)])
        p = {"node_to_subgraph": {1: 0, 2: 1, 3: 1, 4: 1, 5: 2}, "core_schedules": [[0], [1], [2]]}
        validate(g, p)
        after, d = split_large_tasks(g, p, trigger_ops=2, chunk_ops=1)
        validate(g, after)
        self.assertEqual(len(after["core_schedules"][1]), 3)
        self.assertEqual(d["tasks_after"], 5)
        OBSERVATIONS["soft_chunks"] = after


def main():
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module("tests.q1.test_component_overload")))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentReviewTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    for name, expected in RECEIPTS.items():
        assert hashlib.sha256((TARGET / name).read_bytes()).hexdigest() == expected
    forbidden = [n for n in sys.modules if n in {"multicore_cut_evaluate_problem_1", "schedule_step1", "schedule_step2", "schedule_step3"}]
    assert not forbidden, forbidden
    record = {"kind": "synthetic_structure_review_not_performance", "source_commit": SOURCE,
              "source_sha256": RECEIPTS, "checkout_head_at_start": CHECKOUT_HEAD,
              "source_files_match_fixed_commit_before_and_after": True,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "tests": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
              "successful": result.wasSuccessful(), "observations": OBSERVATIONS,
              "calls": {"real_graph_construct": 0, "task_compiler": 0, "E0": 0, "E1": 0, "E2": 0},
              "forbidden_evaluator_modules_loaded": forbidden,
              "scope": "Original six synthetic unit tests plus six independent synthetic tests; no case data read."}
    (OUT / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
