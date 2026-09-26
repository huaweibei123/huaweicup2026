"""Recompute paper tables from fixed archived observations; never run a solver.

The 100 denominators come from the existing byte-audited baseline index.
This calculation does not independently rerun or audit all 500 E0 artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

ARCHIVE = "9c5f87548cc7588465a638e032993969b5cac891"
SOLVER = "a0537aeb72dc702af86d67d3194587d581ac207c"
FEED = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json"
FEED_SHA256 = "4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764"
AUDIT_COMMIT = "ad670c2f2414007cad80589b1f02621cea4037e8"
AUDIT_PATH = "results/a/q1-yuanzhifang/v4-reuse-audit-20260925/reusable-index.json"


def read_blob(repo: Path, commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), "show", f"{commit}:{path}"])


def describe(values: list[int | float]) -> dict:
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": math.fsum(ordered) / len(ordered),
        "median": statistics.median(ordered),
        "minimum": ordered[0],
        "p95_nearest_rank": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "maximum": ordered[-1],
    }


def recompute(repo: Path) -> dict:
    raw = read_blob(repo, ARCHIVE, FEED)
    if hashlib.sha256(raw).hexdigest() != FEED_SHA256:
        raise ValueError("fixed feed hash mismatch")
    records = json.loads(raw)["records"]
    audit_raw = read_blob(repo, AUDIT_COMMIT, AUDIT_PATH)
    audit = json.loads(audit_raw)
    if audit["summary"]["feed_sha256"] != FEED_SHA256 or audit["summary"]["errors"]:
        raise ValueError("denominator audit does not match feed")
    index = {r["case_id"]: r for r in audit["k4"]}
    cases = {f"{i:03d}" for i in range(1, 101)}
    expected = {(case, k) for case in cases for k in range(1, 6)}
    actual = {(r["case_id"], r["cores"]) for r in records}
    if len(records) != 500 or actual != expected or set(index) != cases:
        raise ValueError("incomplete or duplicated 100 by 5 matrix")
    for row in records:
        prior = index[row["case_id"]]
        if row["status"] != "ok" or row["solver_commit"] != SOLVER:
            raise ValueError("unexpected status or source")
        identity, baseline = row["identity"], row["baseline"]
        if identity["graph_sha256"] != prior["graph_sha256"]:
            raise ValueError("graph identity mismatch")
        for field in ("graph_sha256", "config_sha256", "official_sha256"):
            if baseline[field] != identity[field]:
                raise ValueError("baseline identity mismatch")
        if (baseline["result"]["path"] != prior["baseline_result_path"] or
                baseline["result"]["sha256"] != prior["baseline_gzip_sha256"]):
            raise ValueError("baseline artifact identity mismatch")
    groups = []
    for k in range(1, 6):
        group = sorted((r for r in records if r["cores"] == k), key=lambda r: r["case_id"])
        speedups = [index[r["case_id"]]["baseline_makespan_cycles"] /
                    r["metrics"]["makespan_cycles"] for r in group]
        with localcontext() as context:
            context.prec = 40
            exact_mean = sum((Decimal(index[r["case_id"]]["baseline_makespan_cycles"]) /
                              Decimal(r["metrics"]["makespan_cycles"]) for r in group), Decimal(0)) / 100
        if abs(float(exact_mean) - math.fsum(speedups) / 100) > 1e-12:
            raise ValueError("independent mean calculations disagree")
        extra = [r["metrics"]["extra_ddr_bytes"] for r in group]
        groups.append({
            "cores": k,
            "observed_solver_speedup": describe(speedups),
            "observed_solver_speedup_mean_decimal": str(exact_mean),
            "official_curve_speedup": describe([1.0] * 100 if k == 1 else speedups),
            "solver_wall_seconds": describe([r["metrics"]["solver_wall_seconds"] for r in group]),
            "external_E0_wall_seconds": describe([r["metrics"]["evaluation_wall_seconds"] for r in group]),
            "extra_ddr_bytes": describe(extra),
            "extra_ddr_zero_count": extra.count(0),
            "selected_candidate_counts": dict(sorted(Counter(r["parameters"]["selected"] for r in group).items())),
        })
    first = records[0]["provenance"]
    return {
        "kind": "paper_arithmetic_snapshot_not_new_benchmark",
        "sources": {
            "archive_commit": ARCHIVE, "solver_commit": SOLVER,
            "feed_path": FEED, "feed_sha256": FEED_SHA256,
            "denominator_audit_commit": AUDIT_COMMIT, "denominator_audit_path": AUDIT_PATH,
            "denominator_audit_sha256": hashlib.sha256(audit_raw).hexdigest(),
            "fixed_singlecore_source_commit": audit["summary"]["baseline_source_commit"],
            "config_sha256": audit["summary"]["config_sha256"],
            "official_sha256": audit["summary"]["official_code_sha256_reconstructed"],
        },
        "scope": "500 feed rows recalculated; denominator identities matched to existing 100-case audit. No new solver, Task compilation, E0, E1, or E2.",
        "statistics": "Arithmetic mean of per-case ratios; usual median; p95 nearest rank ceil(0.95*n). Official curve k1=1; solver k1 reoptimization kept separate.",
        "environment": {key: first["environment"][key] for key in ("os", "cpu", "ram_bytes", "python", "workers")},
        "timing": {key: first["measurement"][key] for key in ("cold_start", "solver_scope", "evaluation_scope", "offline_costs")},
        "rows": len(records), "status_counts": dict(Counter(r["status"] for r in records)),
        "archived_calls": {name: sum(r["provenance"]["measurement"]["calls"][name] for r in records)
                           for name in ("solver", "E0", "E1", "E2")},
        "E1_calls_per_cell": dict(sorted(Counter(r["provenance"]["measurement"]["calls"]["E1"] for r in records).items())),
        "groups": groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("use a new output path; do not overwrite an evidence snapshot")
    data = recompute(args.repo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"rows": data["rows"], "status": data["status_counts"],
                      "means": [g["official_curve_speedup"]["mean"] for g in data["groups"]],
                      "new_evaluations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
