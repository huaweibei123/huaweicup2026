import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from src.q3_yuanzhifang import adaptive_solve as router
from src.q3_yuanzhifang.captain_v2.construct import Index, ROOT, UnsupportedStructure


def shared_jobs(word=("PIPE_M",) * 4, common=True):
    length = len(word)
    return {
        "ops": [{"id": j * length + p + 1, "op": "MUL", "pipe": pipe,
                 "cycles": 10} for j in range(3) for p, pipe in enumerate(word)],
        "tensors": [{"id": 100, "pos": "L1", "size": 60}],
        "edges": [{"source": j * length + p + 1, "target": j * length + p + 2}
                  for j in range(3) for p in range(length - 1)] +
                 ([{"source": 100, "target": j * length + 1} for j in range(3)]
                  if common else []),
    }


class AdaptiveTest(unittest.TestCase):
    def test_shared_chain_uses_one_evaluation_and_exact_coverage(self):
        graph = shared_jobs()
        evaluate, save = Mock(return_value={"makespan": 777}), Mock(return_value={})
        with patch.object(router, "captain_candidates", side_effect=AssertionError("wrong route")):
            winner, calls, records, selection = router.evaluate_candidates(Index(graph), 2, evaluate, save)
        plan = winner[0]
        self.assertEqual(calls, 1)
        evaluate.assert_called_once_with(plan)
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(range(1, 13)))
        self.assertEqual(sorted(s for seq in plan["core_schedules"] for s in seq), list(range(12)))
        self.assertEqual(records[0]["metadata"]["cuts"], [0, 2, 4])
        self.assertEqual(selection["router"]["route"], "shared_pipeline")

    def test_word_single_core_and_nonshared_graphs_preserve_captain_policy(self):
        returned = (({}, {"makespan": 123}, "captain"), 2, [], {"rule": "unchanged"})
        for graph, cores in [(shared_jobs(("PIPE_M", "PIPE_V", "PIPE_M")), 2),
                             (shared_jobs(), 1), (shared_jobs(common=False), 2)]:
            with self.subTest(cores=cores, graph=graph):
                index, evaluate, save = Index(graph), Mock(), Mock()
                with patch.object(router, "captain_candidates", return_value=returned) as captain:
                    actual = router.evaluate_candidates(index, cores, evaluate, save)
                captain.assert_called_once_with(index, cores, evaluate, save)
                evaluate.assert_not_called()
                self.assertEqual(actual[:3], returned[:3])
                self.assertEqual(actual[3]["rule"], "unchanged")

    def test_evaluation_failure_cannot_trigger_fallback(self):
        with patch.object(router, "captain_candidates") as captain:
            with self.assertRaisesRegex(UnsupportedStructure, "evaluation sentinel"):
                router.evaluate_candidates(Index(shared_jobs()), 2,
                    Mock(side_effect=UnsupportedStructure("evaluation sentinel")), Mock())
            captain.assert_not_called()

    def test_zero_cycles_rejects_pipeline_before_duration_clamping(self):
        graph = shared_jobs()
        graph["ops"][0]["cycles"] = 0
        accepted, reason = router.pipeline_request(Index(graph), 2)
        self.assertFalse(accepted)
        self.assertIn("positive integer", reason)

    def test_pinned_captain_bytes_and_only_root_adaptation(self):
        self.assertEqual(ROOT, Path(__file__).resolve().parents[2])
        manifest = json.loads((ROOT / "src/q3_yuanzhifang/captain_v2/UPSTREAM.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["files"]), 12)
        for row in manifest["files"]:
            data = (ROOT / row["destination"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), row["destination_sha256"])
            if row["source"].endswith("/construct.py"):
                self.assertEqual(data.count(b"parents[3]"), 1)
                data = data.replace(b"parents[3]", b"parents[2]")
            self.assertEqual(hashlib.sha256(data).hexdigest(), row["source_sha256"])
            header = b"blob " + str(len(data)).encode() + b"\0"
            self.assertEqual(hashlib.sha1(header + data).hexdigest(), row["source_git_blob"])


if __name__ == "__main__":
    unittest.main()
