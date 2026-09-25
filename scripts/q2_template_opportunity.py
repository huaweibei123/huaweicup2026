#!/usr/bin/env python3
"""Recompute K5 necessary-bound slack for the frozen finite template domain."""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee"
SUMMARY = ROOT / "results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json"
BOUNDS = ROOT / "results/a/q2-nikolastarx/goal-20260924/global-bounds.json"
OUTPUT = ROOT / "results/a/q2-nikolastarx/template-opportunity-20260925/report.json"
TEMPLATES = ["028", "044", "046", "067", "073", "078", "083", "090", "092"]
TRIALS = ["044", "046", "078"]

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def read_json(path: Path):
    return json.loads(path.read_text())

def main() -> None:
    summary, bounds = read_json(SUMMARY), read_json(BOUNDS)
    assert summary["status"] == "completed" and summary["accepted_cells"] == 500
    rows = summary["rows"]
    assert len(rows) == 500 and len({(r["case"], r["cores"]) for r in rows}) == 500
    assert all(r["status"] == "accepted" for r in rows)
    certificate = ROOT / "src/q2_nikolastarx/global_bounds.py"
    assert sha(certificate.read_bytes()) == bounds["certificate_source_sha256"]
    graph_hash = {r["case"]: r["graph_sha256"] for r in rows}
    assert all(r["graph_sha256"] == graph_hash[r["case"]] for r in rows)
    k5 = {r["case"]: r["official"]["makespan"] for r in rows if r["cores"] == 5}
    assert len(k5) == 100
    lb = {}
    for record in bounds["records"]:
        case = record["graph_file"][5:8]
        assert record["supported"] and case not in lb
        assert record["graph_sha256"] == graph_hash[case]
        lb[case] = next(x["makespan_lower_bound_cycles"] for x in record["by_core_count"] if x["cores"] == 5)
    assert len(lb) == 100 and set(lb) == set(k5)

    feed_files = sorted(ARCHIVE.glob("cases-*/board-feed.json"))
    assert len(feed_files) == 10
    feeds = []
    for path in feed_files:
        feeds.extend(read_json(path)["records"])
    assert len(feeds) == 500
    coords = {(r["case_id"], r["cores"]) for r in feeds}
    assert len(coords) == 500 and coords == {(r["case"], r["cores"]) for r in rows}
    baseline_by_case = {}
    for r in feeds:
        case = r["case_id"]
        base = r["baseline"]
        assert base["route"] == "E0" and base["entrypoint"] == "singlecore_evaluate.evaluate_singlecore"
        assert base["graph_sha256"] == r["identity"]["graph_sha256"]
        assert base["graph_sha256"] == graph_hash[case]
        ref = base["result"]
        path = ROOT / ref["path"]
        raw = path.read_bytes()
        assert sha(raw) == ref["sha256"]
        B = json.loads(gzip.decompress(raw))["makespan"]
        identity = (B, ref["path"], ref["sha256"])
        assert case not in baseline_by_case or baseline_by_case[case] == identity
        baseline_by_case[case] = identity
    assert len(baseline_by_case) == 100

    cells = []
    for case in sorted(k5):
        B, path, digest = baseline_by_case[case]
        M, L = k5[case], lb[case]
        assert M >= L > 0
        cells.append({"case": case, "B": B, "M": M, "LB": L,
                      "slack": B / L - B / M,
                      "baseline_result_path": path, "baseline_result_sha256": digest})
    def group(cases):
        selected = [r for r in cells if r["case"] in cases]
        total = sum(r["slack"] for r in selected)
        return {"cases": sorted(cases), "n": len(selected), "slack_sum": total,
                "mean_increment_if_all_reach_LB": total / 100,
                "share_of_all100_slack": total / sum(r["slack"] for r in cells)}
    all_slack = sum(r["slack"] for r in cells)
    report = {
        "scope": "read-only arithmetic ceiling from necessary lower bounds; not attainable-gain prediction",
        "solver_or_evaluator_calls": 0,
        "inputs": {
            "completed_summary": {"path": str(SUMMARY.relative_to(ROOT)), "sha256": sha(SUMMARY.read_bytes())},
            "global_bounds": {"path": str(BOUNDS.relative_to(ROOT)), "sha256": sha(BOUNDS.read_bytes()),
                              "certificate_source_sha256": bounds["certificate_source_sha256"]},
            "board_feeds": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p.read_bytes())} for p in feed_files],
            "baseline_population": "feed baseline.result E0 singlecore_evaluate.evaluate_singlecore; all referenced blobs hash-verified"
        },
        "coverage": {"accepted_summary_cells": len(rows), "unique_coordinates": len(coords),
                     "unique_cases": len(baseline_by_case), "unique_k5_bounds": len(lb)},
        "k5": {"mean_B_over_M": sum(r["B"] / r["M"] for r in cells) / 100,
               "mean_B_over_LB_ceiling": sum(r["B"] / r["LB"] for r in cells) / 100,
               "total_slack_sum": all_slack, "mean_increment_if_all100_reach_LB": all_slack / 100},
        "template9": group(TEMPLATES), "trial3": group(TRIALS), "cells": cells,
        "caveat": "LB relaxes constraints including data movement; attaining every LB is unproved and may be impossible."
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)), "template9": report["template9"], "trial3": report["trial3"], "k5": report["k5"]}, indent=2))

if __name__ == "__main__":
    main()
