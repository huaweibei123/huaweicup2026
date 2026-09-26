"""Boundary checks for the read-only P1 evidence auditor; no solver calls."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

PATH = Path(__file__).resolve().parents[2] / "src/analysis/p1_full_yuanzhifang.py"
SPEC = importlib.util.spec_from_file_location("p1_audit", PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class AuditBoundaryTests(unittest.TestCase):
    def test_mean_is_casewise_not_ratio_of_sums(self):
        baseline, result = [100, 10], [50, 10]
        summary = audit.distribution([b / m for b, m in zip(baseline, result)])
        self.assertEqual(summary["mean"], 1.5)
        self.assertNotEqual(summary["mean"], sum(baseline) / sum(result))

    def test_nonfinite_bool_and_numeric_type_changes_rejected(self):
        for raw in (b'{"cycles":NaN}', b'{"cycles":Infinity}'):
            with self.assertRaises(ValueError):
                audit.read_json(raw)
        for a, b in ((True, 1), (3.0, 3), (4, 5)):
            with self.assertRaises(ValueError):
                audit.same_number(a, b, "fixture")

    def test_artifact_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("org-repo-6664a63/results/result.json", b'{"makespan":7}')
            source = audit.Source(path)
            try:
                with self.assertRaises(ValueError):
                    source.artifact({"path": "results/result.json", "sha256": "0" * 64})
                with self.assertRaises(ValueError):
                    source.get("../result.json")
            finally:
                source.close()

    def test_nearest_rank_p95(self):
        self.assertEqual(audit.distribution(list(range(1, 101)))["p95_nearest_rank"], 95)


if __name__ == "__main__":
    unittest.main()
