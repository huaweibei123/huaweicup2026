"""Online policy/publication unit tests: no E0 simulations and no performance claims."""
from pathlib import Path
import tempfile
import unittest

from src.q3.solve import prepare, publish_new


def graph(vector_work):
    return {"ops": [{"id": 2, "op": "COMPUTE", "pipe": "PIPE_M", "cycles": 10},
                    {"id": 4, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": vector_work},
                    {"id": 8, "op": "COMPUTE", "pipe": "PIPE_M", "cycles": 10}],
            "tensors": [], "edges": [{"source": 2, "target": 4}, {"source": 4, "target": 8}]}


class OnlineTests(unittest.TestCase):
    def test_policy_from_structure_without_filename(self):
        _, word = prepare(graph(15), 2)
        _, affine = prepare(graph(21), 2)
        self.assertEqual(word["strategy"], "resource_word")
        self.assertEqual(affine["strategy"], "affine_eighth")

    def test_publication_never_overwrites_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "plan.json"
            publish_new(p, b"original\n")
            with self.assertRaises(FileExistsError):
                publish_new(p, b"replacement\n")
            self.assertEqual(p.read_bytes(), b"original\n")
            self.assertEqual(list(Path(d).iterdir()), [p])

    def test_policy_returns_only_official_plan_fields(self):
        plan, meta = prepare(graph(15), 5)
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(len(plan["core_schedules"]), 5)
        self.assertEqual(meta["selection"]["rule"], "homogeneous_serial_MVM")


if __name__ == "__main__":
    unittest.main()
