from __future__ import annotations

import csv
import gzip
import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.eval_proxy.compare_routes import _delivery_lf_sha256, _load_pool


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class CompareRoutesPoolIdentityTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.pool_dir = Path(self.temporary.name)
        plan_bytes = b'{"core_schedules":[[0]],"node_to_subgraph":{"1":0}}\n'
        raw_e0 = b'{"makespan":7}\n'
        compressed_e0 = gzip.compress(raw_e0, mtime=0)
        proxy_bytes = b'{"rank_score":3}\n'
        (self.pool_dir / "plan.json").write_bytes(plan_bytes)
        (self.pool_dir / "proxy.json").write_bytes(proxy_bytes)
        (self.pool_dir / "e0.json.gz").write_bytes(compressed_e0)
        self.manifest = {
            "graph_sha256": "graph-current",
            "config_sha256": "config-current",
            "official_code_hash": "official-current",
            "candidate_implementation": {
                "delivery_lf_sha256": {
                    relative: _delivery_lf_sha256(
                        Path(__file__).resolve().parents[2] / relative
                    )
                    for relative in (
                        "src/eval_proxy/dev_pool.py",
                        "src/eval_proxy/model.py",
                    )
                }
            },
            "summary": {"candidate_count": 1},
        }
        self._write_manifest(self.manifest)
        with (self.pool_dir / "candidates.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "candidate_id",
                    "e0_status",
                    "e0_encoding",
                    "plan_path",
                    "plan_sha256",
                    "proxy_output_path",
                    "proxy_output_sha256",
                    "e0_output_path",
                    "e0_output_sha256",
                    "e0_json_sha256",
                    "e0_makespan",
                    "e0_seconds",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "candidate_id": "candidate-000",
                    "e0_status": "ok",
                    "e0_encoding": "gzip",
                    "plan_path": "plan.json",
                    "plan_sha256": _sha256(plan_bytes),
                    "proxy_output_path": "proxy.json",
                    "proxy_output_sha256": _sha256(proxy_bytes),
                    "e0_output_path": "e0.json.gz",
                    "e0_output_sha256": _sha256(compressed_e0),
                    "e0_json_sha256": _sha256(raw_e0),
                    "e0_makespan": 7,
                    "e0_seconds": 0.25,
                }
            )

    def tearDown(self):
        self.temporary.cleanup()

    def _write_manifest(self, manifest):
        (self.pool_dir / "run.json").write_text(
            json.dumps(manifest) + "\n", encoding="utf-8"
        )

    def _load(self):
        return _load_pool(
            self.pool_dir,
            graph_sha256="graph-current",
            config_sha256="config-current",
            official_code_hash="official-current",
        )

    def test_matching_manifest_allows_verified_pool(self):
        rows, plans, truths, candidate_ids, recorded_seconds = self._load()
        self.assertEqual(len(rows), 1)
        self.assertEqual(plans[0]["core_schedules"], [[0]])
        self.assertEqual(truths, [7])
        self.assertEqual(candidate_ids, ["candidate-000"])
        self.assertEqual(recorded_seconds, 0.25)

    def test_manifest_identity_or_count_mismatch_is_rejected(self):
        cases = {
            "graph_sha256": ("graph_sha256", "graph-stale"),
            "config_sha256": ("config_sha256", "config-stale"),
            "official_code_hash": ("official_code_hash", "official-stale"),
            "candidate_count": ("candidate_count", 2),
        }
        for label, (field, stale_value) in cases.items():
            with self.subTest(field=label):
                manifest = deepcopy(self.manifest)
                if field == "candidate_count":
                    manifest["summary"][field] = stale_value
                else:
                    manifest[field] = stale_value
                self._write_manifest(manifest)
                with self.assertRaisesRegex(ValueError, field):
                    self._load()


if __name__ == "__main__":
    unittest.main()
