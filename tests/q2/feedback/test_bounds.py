"""Analytical fixtures and tree cut oracles; no evaluator/scheduler calls.

Run this file with --census OUTPUT to verify frozen graph bytes and the structural
domain used by the proof. This reads graph/baseline receipts, not result scores.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

from src.q2.feedback.bounds import graph_bounds
from src.q2.feedback.construct import Index, ROOT
from src.q2.feedback.tree import connected_partition


def op(ident, cycles, pipe="PIPE_M", kind="COMPUTE"):
    return {"id": ident, "cycles": cycles, "pipe": pipe, "op": kind}


def graph(ops, tensors=(), edges=()):
    return {"ops": list(ops), "tensors": [
        {"id": tid, "size": size, "pos": pos} for tid, size, pos in tensors],
        "edges": [{"source": u, "target": v} for u, v in edges]}


class BoundsTests(unittest.TestCase):
    def test_rejects_original_logical_aliases_outside_proof_domain(self):
        g = graph([op(1, 10)], [(100, 60, 'UB')], [(100, 1)])
        g['tensors'][0]['logical_tid'] = 99
        with self.assertRaisesRegex(ValueError, 'logical aliases'):
            graph_bounds(g, [1], energetic=True)

    def test_release_tail_resource_bound_excludes_unavoidable_idle_ends(self):
        g = graph([op(1, 10, 'PIPE_V'), op(2, 10), op(3, 10), op(4, 10),
                   op(5, 10, 'PIPE_V')],
                  edges=[(1, 2), (1, 3), (1, 4), (2, 5), (3, 5), (4, 5)])
        basic = graph_bounds(g, [1, 2])
        strong = graph_bounds(g, [1, 2], energetic=True)
        self.assertEqual(basic['by_core']['1']['lower_bound_cycles'], 30)
        self.assertEqual(strong['by_core']['1']['lower_bound_cycles'], 50)
        self.assertEqual(strong['by_core']['2']['lower_bound_cycles'], 35)
        cert = strong['by_core']['1']['release_tail_pipe_certificates']['PIPE_M']
        self.assertEqual((cert['release'], cert['tail'], cert['work'], cert['jobs']),
                         (10, 10, 30, 3))
        # On one core, V source [0,10], three M jobs [10,40], V sink [40,50]
        # attains this relaxation. On two cores indivisible 10-cycle jobs take
        # at least 20 cycles, hence 35 is not an attainability claim.

    def test_energetic_does_not_restore_copy_contracted_dependencies(self):
        g = graph([op(1, 100), op(2, 1, 'PIPE_MTE3', 'COPY_OUT'),
                   op(3, 1, 'PIPE_MTE2', 'COPY_IN'), op(4, 100, 'PIPE_V')],
                  [(10, 60, 'UB'), (11, 60, 'DDR'), (12, 60, 'UB')],
                  [(1, 10), (10, 2), (2, 11), (11, 3), (3, 12), (12, 4)])
        result = graph_bounds(g, [1, 2], energetic=True)
        self.assertEqual(result['contracted_edges_not_used_in_bound'], 1)
        self.assertTrue(all(r['lower_bound_cycles'] == 101
                            for r in result['by_core'].values()))

    def test_rejects_empty_eligible_domain_including_copy_only_graph(self):
        for g in (graph([]), graph([op(1, 1, "PIPE_MTE2", "COPY_IN")])):
            with self.subTest(graph=g), self.assertRaisesRegex(ValueError, "nonempty eligible"):
                graph_bounds(g, [1])

    def test_rejects_multiple_original_producers_even_if_only_one_is_eligible(self):
        for second in (op(2, 1, "PIPE_V"), op(2, 1, "PIPE_MTE2", "COPY_IN")):
            g = graph([op(1, 1), second, op(3, 1)], [(100, 60, "UB")],
                      [(1, 100), (2, 100), (100, 3)])
            with self.subTest(second=second), self.assertRaisesRegex(ValueError, "original producer"):
                graph_bounds(g, [1])

    def test_rejects_invalid_core_counts(self):
        for cores in ([], [0], [6], [1, 6], [1.0], [True]):
            with self.subTest(cores=cores), self.assertRaisesRegex(ValueError, "core counts"):
                graph_bounds(graph([op(1, 1)]), cores)

    def test_rejects_nonpositive_or_nonfinite_bandwidth(self):
        for bandwidth in (True, 0, -1, float("inf"), float("-inf"), float("nan")):
            with self.subTest(bandwidth=bandwidth), self.assertRaisesRegex(ValueError, "bandwidth"):
                graph_bounds(graph([op(1, 1)]), [1], bandwidth)

    def test_pipe_work_is_per_pipe_and_path_is_not_divided_by_cores(self):
        result = graph_bounds(graph([op(1, 7), op(2, 4), op(3, 3, "PIPE_V")]), [1, 2])
        self.assertEqual(result["pipe_work_cycles"]["PIPE_M"], 11)
        self.assertEqual(result["compute_critical_path"], 7)
        self.assertEqual(result["by_core"]["1"]["lower_bound_cycles"], 11)
        self.assertEqual(result["by_core"]["2"]["pipe_work"], 6)
        self.assertEqual(result["by_core"]["2"]["lower_bound_cycles"], 7)

    def test_endpoint_path_and_ddr_work_use_reconstructed_copies(self):
        g = graph([op(1, 7), op(2, 3, "PIPE_V")],
                  [(100, 60, "L1"), (101, 120, "UB"), (102, 180, "UB")],
                  [(101, 1), (1, 100), (100, 2), (2, 102)])
        result = graph_bounds(g, [1, 5])
        self.assertEqual(result["compute_critical_path"], 10)
        self.assertEqual(result["compulsory_copy_bytes"], 300)
        for row in result["by_core"].values():
            self.assertEqual(row["path_with_endpoint_copies"], 15)
            self.assertEqual(row["compulsory_ddr_work"], 5)
            self.assertEqual(row["lower_bound_cycles"], 15)

    def test_shared_input_is_counted_once_not_once_per_consumer_or_core(self):
        g = graph([op(1, 1), op(2, 1, "PIPE_V"), op(3, 1)],
                  [(100, 61, "DDR")], [(100, 1), (100, 2), (100, 3)])
        result = graph_bounds(g, [1, 5])
        self.assertEqual(result["compulsory_copy_bytes"], 61)
        for row in result["by_core"].values():
            self.assertEqual(row["compulsory_ddr_work"], 2)
            self.assertEqual(row["path_with_endpoint_copies"], 3)

    def test_per_transfer_ceiling_is_stronger_than_ceiling_total_bytes(self):
        g = graph([op(1, 1), op(2, 1, "PIPE_V")],
                  [(100, 1, "L1"), (101, 1, "UB")], [(100, 1), (101, 2)])
        result = graph_bounds(g, [2])
        # Two mandatory transfers each enter the shared pool with work 1.
        # ceil((1 + 1) / 60) = 1 would lose this frozen-model information.
        self.assertEqual(result["by_core"]["2"]["compulsory_ddr_work"], 2)

    def test_zero_size_and_zero_cycles_still_take_one_cycle(self):
        g = graph([op(1, 0)], [(100, 0, "UB"), (101, 0, "UB")],
                  [(100, 1), (1, 101)])
        result = graph_bounds(g, [1])
        self.assertEqual(result["compulsory_copy_bytes"], 0)
        self.assertEqual(result["by_core"]["1"]["compulsory_ddr_work"], 2)
        self.assertEqual(result["by_core"]["1"]["lower_bound_cycles"], 3)

    def test_original_copy_cycles_are_not_reused_and_final_output_is_retained(self):
        g = graph([op(1, 5), op(2, 2, "PIPE_V"),
                   op(3, 999, "PIPE_MTE2", "COPY_IN"),
                   op(4, 999, "PIPE_MTE3", "COPY_OUT")],
                  [(100, 60, "UB"), (101, 60, "UB")],
                  [(3, 100), (100, 1), (1, 101), (101, 2), (101, 4)])
        result = graph_bounds(g, [1])
        self.assertEqual(result["eligible_ops"], 2)
        self.assertEqual(result["compulsory_copy_bytes"], 120)
        self.assertEqual(result["by_core"]["1"]["compulsory_ddr_work"], 2)
        self.assertEqual(result["by_core"]["1"]["path_with_endpoint_copies"], 8)

    def test_copy_contracted_edge_is_excluded_from_completion_path(self):
        g = graph([op(1, 100), op(2, 1, "PIPE_MTE3", "COPY_OUT"),
                   op(3, 1, "PIPE_MTE2", "COPY_IN"), op(4, 100, "PIPE_V")],
                  [(10, 60, "UB"), (11, 60, "DDR"), (12, 60, "UB")],
                  [(1, 10), (10, 2), (2, 11), (11, 3), (3, 12), (12, 4)])
        index = Index(g)
        self.assertEqual(index.pred[4], {1})
        result = graph_bounds(g, [1, 2])
        self.assertEqual(result["contracted_edges_not_used_in_bound"], 1)
        self.assertEqual(result["compute_critical_path"], 100)
        self.assertEqual(result["by_core"]["2"]["lower_bound_cycles"], 101)
        # Source reconstruction has no tensor with BOTH eligible producer and
        # eligible consumer, hence no cross_link joins 1 and 4. A source-derived
        # schedule: input COPY 0..1, op4 1..101, op1 0..100, output COPY 100..101.
        # Its M/V operations overlap; treating the contracted edge as a 200-cycle
        # completion path is invalid. No official evaluator is invoked here.

    def test_direct_compute_dependency_remains_in_the_relaxation(self):
        result = graph_bounds(graph([op(1, 7), op(2, 4, "PIPE_V")],
                                    edges=[(1, 2)]), [5])
        self.assertEqual(result["compute_critical_path"], 11)
        self.assertEqual(result["by_core"]["5"]["lower_bound_cycles"], 11)


class TreeDominanceTests(unittest.TestCase):
    def test_deterministic_shapes_match_all_cut_sets_with_nonmonotone_ids(self):
        # Exhaustive cuts for stars/chains/unequal branches, including k > n.
        order = [8, 2, 17, 6, 99]
        for parents in ({8: 99, 2: 99, 17: 99, 6: 99},
                        {8: 2, 2: 17, 17: 6, 6: 99},
                        {8: 17, 2: 17, 17: 99, 6: 99}):
            children = {u: [] for u in order}
            for u, parent in parents.items():
                children[parent].append(u)
            for vector in itertools.product((1, 3), repeat=len(order)):
                weights = dict(zip(order, vector))
                for requested in range(1, 7):
                    parts = min(requested, len(order))
                    def loads(cuts):
                        totals = defaultdict(int)
                        for u in order:
                            v = u
                            while v in parents and (v, parents[v]) not in cuts:
                                v = parents[v]
                            totals[v] += weights[u]
                        return list(totals.values())
                    expected = min(max(loads(set(cuts))) for cuts in
                                   itertools.combinations(parents.items(), parts - 1))
                    cap, cuts, _ = connected_partition(order, children, weights, requested)
                    self.assertEqual(cap, expected)
                    self.assertEqual(len(loads(cuts)), parts)
                    self.assertEqual(max(loads(cuts)), expected)

    def test_scalar_optimum_is_not_a_lower_bound_for_multpipe_makespan(self):
        order, children, weights = [1, 2, 3], {1: [], 2: [], 3: [1, 2]}, {1: 10, 2: 10, 3: 1}
        cap, _, _ = connected_partition(order, children, weights, 1)
        self.assertEqual(cap, 21)
        # A compute-only in-tree: 1 on M and 2 on V run 0..10; sink3 on M
        # runs 10..11. This explicitly feasible pipe/dependency schedule has
        # length 11 < scalar C, without making an E0 score claim.
        self.assertGreater(cap, 11)


def census(output):
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    counts = Counter()
    rows = []
    config = ROOT / "data/raw/a/official/data/config.txt"
    config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    for path in sorted((ROOT / "data/raw/a/official/data").glob("case_*.json")):
        raw = path.read_bytes()
        g = json.loads(raw)
        receipt = json.loads((ROOT / "results/benchmark-board/official-singlecore-20260924" /
                              path.stem[-3:] / "run.json").read_bytes())
        digest = hashlib.sha256(raw).hexdigest()
        if digest != receipt["graph_sha256"] or config_hash != receipt["config_sha256"]:
            raise ValueError(f"frozen baseline input identity mismatch: {path.name}")
        ops = {o["id"]: o for o in g["ops"]}
        tensors = {t["id"]: t for t in g["tensors"]}
        producers = defaultdict(set)
        for edge in g["edges"]:
            if edge["source"] in ops and edge["target"] in tensors:
                producers[edge["target"]].add(edge["source"])
        row = {"case_id": path.stem[-3:], "graph_sha256": digest,
               "baseline_graph_and_config_hash_match": True,
               "ops": len(ops), "tensors": len(tensors),
               "eligible_ops": sum(o["op"] not in {"COPY_IN", "COPY_OUT"} for o in ops.values()),
               "multiple_original_producer_tensors": sum(len(p) > 1 for p in producers.values()),
               "direct_op_edges": sum(e["source"] in ops and e["target"] in ops for e in g["edges"]),
               "zero_size_tensors": sum(t["size"] == 0 for t in tensors.values()),
               "max_tensor_size": max((t["size"] for t in tensors.values()), default=0),
               "max_op_cycles": max((o["cycles"] for o in ops.values()), default=0)}
        rows.append(row)
        for field in ("ops", "tensors", "eligible_ops", "multiple_original_producer_tensors",
                      "direct_op_edges", "zero_size_tensors"):
            counts[field] += row[field]
    if len(rows) != 100 or any(r["eligible_ops"] == 0 for r in rows):
        raise ValueError("proof domain requires exactly 100 nonempty official graphs")
    sources = ["data/raw/a/official/code/multicore_cut_evaluate_problem_2.py",
               "data/raw/a/official/code/schedule_step2.py",
               "data/raw/a/official/code/schedule_step3.py",
               "data/raw/a/official/code/stub_multicore_cut_and_schedule.py"]
    frozen = "45f647b395b84e9569f418fd33d62c2b8eb4d190"
    source_rows = []
    for rel in sources:
        local = (ROOT / rel).read_bytes()
        committed = subprocess.check_output(["git", "show", f"{frozen}:{rel}"], cwd=ROOT)
        if local != committed:
            raise ValueError(f"frozen source bytes differ: {rel}")
        source_rows.append({"path": rel, "sha256": hashlib.sha256(local).hexdigest(),
                            "matches_frozen_git_bytes": True})
    record = {"scope": "Read-only structural/hash census; no solver, evaluator, Step2, or Step3 execution.",
              "command": ".venv/Scripts/python.exe -X utf8 -B -m tests.q2.feedback.test_bounds --census results/a/q2-yuanzhifang/feedback-20260924/theory/review-structure.json",
              "started_at_utc": started_at, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
              "wall_seconds": time.perf_counter() - started, "official_source_commit": frozen,
              "config_sha256": config_hash, "graphs": len(rows), "totals": dict(counts),
              "max_tensor_size": max(r["max_tensor_size"] for r in rows),
              "max_op_cycles": max(r["max_op_cycles"] for r in rows),
              "official_sources": source_rows, "evaluator_calls": 0, "solver_calls": 0,
              "rows": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in record.items() if k not in {"rows", "official_sources"}}))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--census":
        census(Path(sys.argv[2]))
    else:
        unittest.main()
