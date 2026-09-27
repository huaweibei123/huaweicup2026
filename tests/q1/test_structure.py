"""Graph-level regressions; full Task execution is checked by E0 experiments."""
import itertools
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src/q1"), str(ROOT / "data/raw/a/official/code")]
from structure import structural_partition, fuse_covers
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def graph(n, edges):
    result = {"ops": [{"id": i, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": 1} for i in range(n)],
              "tensors": [], "edges": []}
    for i, (u, v) in enumerate(edges, 10000):
        result["tensors"].append({"id": i, "pos": "UB", "size": 1})
        result["edges"].extend([{"source": u, "target": i}, {"source": i, "target": v}])
    return result


class StructuralCandidates(unittest.TestCase):
    def test_alternate_path_forbids_contraction(self):
        g = graph(3, [(0, 1), (1, 2)])
        p = {"node_to_subgraph": {v: v for v in range(3)}, "core_schedules": [[0, 2], [1]]}
        _, info = fuse_covers(g, p, 3, False)
        self.assertEqual(info["merges"], [])

    def test_export_guard_is_a_separate_candidate_choice(self):
        g = graph(3, [(0, 2)])
        p = {"node_to_subgraph": {v: v for v in range(3)}, "core_schedules": [[0, 1], [2]]}
        _, guarded = fuse_covers(g, p, 3, True)
        unguarded, free = fuse_covers(g, p, 3, False)
        self.assertEqual(guarded["merges"], [])
        self.assertEqual(free["merges"], [[0, 1]])
        validate_task_order(derive_multicore_plan(g, unguarded))

    def test_empty_core_does_not_bypass_cycle_check(self):
        g = graph(4, [(2, 1), (0, 3)])
        p = {"node_to_subgraph": {v: v for v in range(4)}, "core_schedules": [[1, 0], [3, 2], []]}
        with self.assertRaises(ValueError):
            fuse_covers(g, p, 3, False)

    def test_all_four_node_forward_dags(self):
        pairs = list(itertools.combinations(range(4), 2))
        for mask in range(1 << len(pairs)):
            g = graph(4, [edge for i, edge in enumerate(pairs) if mask & (1 << i)])
            for kind in ("chain", "component"):
                validate_task_order(derive_multicore_plan(g, structural_partition(g, 2, kind)))
            for assignment in itertools.product(range(2), repeat=4):
                p = {"node_to_subgraph": {v: v for v in range(4)},
                     "core_schedules": [[v for v in range(4) if assignment[v] == k] for k in range(2)]}
                result, _ = fuse_covers(g, p, 4, False)
                validate_task_order(derive_multicore_plan(g, result))
                owner = {t: k for k, order in enumerate(result["core_schedules"]) for t in order}
                self.assertEqual(set(result["node_to_subgraph"]), set(range(4)))
                for v, t in result["node_to_subgraph"].items():
                    self.assertEqual(owner[t], assignment[v])


if __name__ == "__main__":
    unittest.main()
