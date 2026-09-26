"""Reproduce small P3 paper aggregates; never run a solver or evaluator.

Read ten fixed feeds and two published audit summaries as Git bytes. Baseline
ratios, same-plan gains, and pooled byte hit rates are attributed to the team's
published audits, not independently recomputed from large result originals.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
FEED_SHA = "19bebf35205d23fdd832781540f8879da52eeb62"
SUMMARY_SHA = "cf4d77a018def540358c3b4667c2d2466390981a"
SOLVER_SHA = "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1"
FEED_DIR = ("results/a/q3-nikolastarx/forest-full500-20260925-s59/"
            "20260924T2122Z-s59ee/revision2-baseline-draft")


def main():
    sources = []

    def read(commit, path):
        blob = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                              check=True, capture_output=True).stdout
        sources.append(dict(commit=commit, path=path, bytes=len(blob),
                            sha256=hashlib.sha256(blob).hexdigest()))
        return json.loads(blob)

    cells = {}
    raw_rows = 0
    for shard in range(1, 11):
        feed = read(FEED_SHA, f"{FEED_DIR}/board-feed-s{shard:02}-revision2.json")
        for row in feed["records"]:
            raw_rows += 1
            key = (row["case_id"], row["cores"])
            if key not in cells or row["revision"] > cells[key]["revision"]:
                cells[key] = row
            elif row["revision"] == cells[key]["revision"]:
                assert row == cells[key], f"Conflicting same-revision cell: {key}"
    assert raw_rows == len(cells) == 500
    cases = {case for case, _ in cells}
    assert len(cases) == 100
    assert set(cells) == {(case, k) for case in cases for k in range(1, 6)}
    for row in cells.values():
        assert row["solver_commit"] == SOLVER_SHA
        source = row["provenance"]["solver"]["source"]
        assert source["commit"] == SOLVER_SHA
        assert source["entrypoint"] == "src.q3.forest_solve.main"
        assert row["problem"] == "P3" and row["status"] == "ok"
        assert row["revision"] == 2 and row["metrics"]["makespan_cycles"] > 0
        assert row["evaluator"]["route"] == "E0"
        assert row["timing"]["solver_includes_evaluation"] is True
        assert row["cache_pair"]["cores"] == row["cores"]
        assert row["cache_pair"]["plan_sha256"] == row["identity"]["plan_sha256"]
        assert row["artifacts"]["plan"]["sha256"] == row["identity"]["plan_sha256"]
        for field in ("graph_sha256", "config_sha256", "official_sha256"):
            assert row["baseline"][field] == row["identity"][field]
            assert row["cache_pair"][field] == row["identity"][field]
    assert len({r["identity"]["config_sha256"] for r in cells.values()}) == 1
    assert len({r["identity"]["official_sha256"] for r in cells.values()}) == 1
    for case in cases:
        assert len({cells[case, k]["identity"]["graph_sha256"] for k in range(1, 6)}) == 1

    uniform = read(SUMMARY_SHA,
                   "results/a/q3-nikolastarx/forest-full500-feedback-20260925/independent-audit.json")
    pairs = read(SUMMARY_SHA,
                 "results/a/q3-nikolastarx/forest-cachepair-delta-20260925/independent-audit.json")
    assert uniform["dispatch"]["solver_commit"] == SOLVER_SHA
    assert pairs["sources"]["forest_run_id"] == "q3-forest-full500-20260925-s59"
    assert pairs["validation"]["all_500_coordinates"] is True
    assert pairs["validation"]["same_plan_reuse"] == 476
    assert pairs["validation"]["new_p2_calls_succeeded"] == 24
    comparison = uniform["forest_vs_c2_counts"]
    for counts in comparison.values():
        assert sum(counts[key] for key in ("better", "equal", "worse")) == len(cells)
    calls = {kind: sum(r["provenance"]["measurement"]["calls"][kind]
                       for r in cells.values()) for kind in ("solver", "E0", "E1", "E2")}
    assert calls == uniform["coverage"]["call_ledger"]
    walls = sorted(r["metrics"]["solver_wall_seconds"] for r in cells.values())
    assert all(math.isfinite(w) and w > 0 for w in walls)
    wall_stats = dict(mean=statistics.fmean(walls), median=statistics.median(walls),
                      p95_nearest_rank=walls[math.ceil(.95 * len(walls)) - 1],
                      max=max(walls), min=min(walls))
    for key, value in wall_stats.items():
        assert math.isclose(value, uniform["solver_wall_seconds"][key], abs_tol=1e-9)
    negatives = Counter()
    for cell in pairs["negative_gain_cells"]:
        assert cells[cell["case_id"], cell["cores"]]["metrics"]["makespan_cycles"] == cell["p3_m"]
        assert cell["p2_m"] < cell["p3_m"]
        assert math.isclose(cell["ratio"], cell["p2_m"] / cell["p3_m"], abs_tol=1e-12)
        negatives[cell["cores"]] += 1
    per_core = {}
    for k in range(1, 6):
        rows = [r for (_, core), r in cells.items() if core == k]
        published = pairs["per_core"][str(k)]
        mean_m = statistics.fmean(r["metrics"]["makespan_cycles"] for r in rows)
        assert len(rows) == published["cells"] == 100
        assert math.isclose(mean_m, published["mean_P3_M"], abs_tol=1e-9)
        per_core[str(k)] = dict(
            feed_cells=100, feed_mean_P3_M=mean_m,
            feed_mean_extra_ddr_bytes=statistics.fmean(r["metrics"]["extra_ddr_bytes"] for r in rows),
            feed_mean_case_byte_hit_rate=statistics.fmean(r["metrics"]["cache_hit_rate"] for r in rows),
            published_mean_B_over_M=uniform["forest_vs_official_singlecore_arithmetic_mean_B_over_M"][str(k)],
            published_mean_same_plan_P2_over_P3=published["mean_p2_over_p3"],
            published_pooled_byte_hit_rate=published["P3_byte_hit_rate_weighted"],
            published_cache_gain_below_one_count=negatives[k])
    output = dict(
        schema="p3-paper-evidence-audit-v1", source_files=sources,
        solver_commit=SOLVER_SHA, solver_entrypoint="src.q3.forest_solve.main",
        feed_cells=500, exact_100x5=True, revisions=[2], declared_online_calls=calls,
        published_version_comparison={
            "reference_results_commit": uniform["result_checks"]["paired_c2_source"],
            "counts_and_sums": comparison,
            "scope": "Copied from pinned team audit; category-count totals checked here, deltas not recomputed from old raw results. Version comparison, not a single-module ablation."},
        per_core=per_core, solver_wall_seconds=wall_stats,
        environment_from_feeds={
            "cpu": sorted({r["provenance"]["environment"]["cpu"] for r in cells.values()}),
            "os": sorted({r["provenance"]["environment"]["os"] for r in cells.values()}),
            "global_max_workers": sorted({r["parameters"]["global_max_workers"] for r in cells.values()})},
        limitations=[
            "Only 10 fixed feeds and two published audit summaries were read as Git bytes.",
            "Feed coverage, declared identities/calls, P3 mean M, per-cell hit means, extra DDR and wall statistics were recomputed here.",
            "B/M, same-plan P2/P3, pooled byte hit rates and negative-cell completeness rely on published team audits; baseline/P2/P3 originals were not independently rehashed here.",
            "No solver, derive/Step, E0/E1/E2, network submission or experiments are performed by this script.",
            "Walls are 500 heterogeneous single observations on a shared host, not repeated-measurement latency confidence intervals."])
    target = ROOT / "paper/drafts/p3-published-summary-audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(target.relative_to(ROOT)), feed_cells=500,
                          calls=calls, per_core=per_core, wall=wall_stats), ensure_ascii=False))


if __name__ == "__main__":
    main()
