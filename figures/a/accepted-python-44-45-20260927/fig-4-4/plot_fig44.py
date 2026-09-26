"""Align figure 4-4 with the frozen paper v8 P1 branch-refinement results.

Layout adapted from LYX figure 4-4 at 96e819b7049c15761b60e271d621bd6505a26522.
This script only redraws existing results; it never runs a solver or evaluator.

The script deliberately keeps the prescribed k=1 plot anchor (1.0) separate
from the observed single-core ratio, which remains in the metrics table.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PALETTE = {
    "blue": "#0F4D92",
    "blue_light": "#3775BA",
    "green": "#8BCF8B",
    "red": "#B64342",
    "neutral": "#767676",
    "grid": "#D9E0E7",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_rows(input_path: Path) -> list[dict]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "P1" not in payload:
        raise ValueError("input must be an object containing P1")
    rows = payload["P1"]
    if not isinstance(rows, list):
        raise ValueError("P1 must be a list")
    if len(rows) != 500:
        raise ValueError(f"expected 500 P1 cells, got {len(rows)}")

    seen: set[tuple[str, int]] = set()
    baselines: dict[str, float] = {}
    cases: set[str] = set()
    cleaned: list[dict] = []
    for row in rows:
        case = str(row["case_id"])
        cores = int(row["cores"])
        if cores not in range(1, 6):
            raise ValueError(f"unexpected core count {cores} for case {case}")
        key = (case, cores)
        if key in seen:
            raise ValueError(f"duplicate cell {key}")
        seen.add(key)
        cases.add(case)
        baseline = float(row["baseline"])
        makespan = float(row["makespan"])
        if baseline <= 0 or makespan <= 0:
            raise ValueError(f"non-positive cycle count in {key}")
        if case in baselines and not np.isclose(baselines[case], baseline):
            raise ValueError(f"baseline denominator changed within case {case}")
        baselines[case] = baseline
        observed = baseline / makespan
        reported = float(row["speedup"])
        if not np.isclose(observed, reported, rtol=1e-10, atol=1e-12):
            raise ValueError(f"reported speedup mismatch in {key}")
        cleaned.append(
            {
                "case": case,
                "cores": cores,
                "baseline_cycles": baseline,
                "makespan_cycles": makespan,
                "observed_speedup": observed,
                "plot_speedup": 1.0 if cores == 1 else observed,
                "attempt_id": str(row.get("attempt_id", "")),
                "revision": int(row.get("revision", 0)),
            }
        )
    if len(cases) != 100 or len(seen) != 500:
        raise ValueError(f"expected 100 cases x 5 cores, got {len(cases)} x {len(seen)}")
    return sorted(cleaned, key=lambda item: (item["case"], item["cores"]))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_normalized_tables(metrics_path: Path, summary_path: Path, rows: list[dict], summary: list[dict]) -> None:
    metrics = []
    for row in rows:
        metrics.append({
            "case": row["case"],
            "cores": row["cores"],
            "method": "p1_branch_refine_834d8c9",
            "baseline": int(row["baseline_cycles"]),
            "makespan": int(row["makespan_cycles"]),
            "speedup": row["observed_speedup"],
            "baseline_cycles": int(row["baseline_cycles"]),
            "makespan_cycles": int(row["makespan_cycles"]),
            "observed_speedup": row["observed_speedup"],
            "plot_speedup": row["plot_speedup"],
            "attempt_id": row["attempt_id"],
            "revision": row["revision"],
        })
    write_csv(metrics_path, metrics, ["case", "cores", "method", "baseline", "makespan", "speedup", "baseline_cycles", "makespan_cycles", "observed_speedup", "plot_speedup", "attempt_id", "revision"])
    normalized_summary = []
    for item in summary:
        normalized_summary.append({
            "method": "p1_branch_refine_834d8c9",
            "cores": item["cores"],
            "n": item["n"],
            "mean_speedup": item["mean_speedup"],
            "sd_speedup": item["sd_speedup"],
            "median_speedup": item["median_speedup"],
            "q1_speedup": item["q1_speedup"],
            "q3_speedup": item["q3_speedup"],
            "min_speedup": item["min_speedup"],
            "max_speedup": item["max_speedup"],
            "mean_observed_speedup": item["mean_observed_speedup"],
        })
    write_csv(summary_path, normalized_summary, ["method", "cores", "n", "mean_speedup", "sd_speedup", "median_speedup", "q1_speedup", "q3_speedup", "min_speedup", "max_speedup", "mean_observed_speedup"])


def summarise(rows: list[dict]) -> list[dict]:
    result = []
    for cores in range(1, 6):
        values = np.array([row["plot_speedup"] for row in rows if row["cores"] == cores])
        observed = np.array([row["observed_speedup"] for row in rows if row["cores"] == cores])
        if len(values) != 100:
            raise ValueError(f"summary has {len(values)} rows for k={cores}")
        result.append(
            {
                "cores": cores,
                "n": len(values),
                "mean_speedup": float(values.mean()),
                "sd_speedup": float(values.std(ddof=1)),
                "median_speedup": float(np.median(values)),
                "q1_speedup": float(np.quantile(values, 0.25)),
                "q3_speedup": float(np.quantile(values, 0.75)),
                "min_speedup": float(values.min()),
                "max_speedup": float(values.max()),
                "mean_observed_speedup": float(observed.mean()),
            }
        )
    return result


def plot_figure(rows: list[dict], summary: list[dict], out_path: Path) -> None:
    plt.rcParams.update(
        {
            "font.family": ["DejaVu Sans", "sans-serif"],
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 1.1,
            "axes.titleweight": "bold",
            "legend.frameon": False,
            "svg.fonttype": "none",
        }
    )
    cores = np.arange(1, 6)
    means = np.array([entry["mean_speedup"] for entry in summary])
    distributions = [
        np.array([row["plot_speedup"] for row in rows if row["cores"] == core])
        for core in range(2, 6)
    ]

    fig, (left, right) = plt.subplots(
        1, 2, figsize=(165 / 25.4, 67 / 25.4), gridspec_kw={"width_ratios": [1.05, 1.35]}
    )
    fig.suptitle("P1 multicore speedup (branch refinement)", fontsize=10.5, fontweight="bold", y=0.995)

    left.plot(cores, cores, linestyle=(0, (4, 3)), linewidth=1.3, color=PALETTE["neutral"], label="Ideal linear")
    left.plot(
        cores,
        means,
        color=PALETTE["blue"],
        marker="o",
        markersize=6.5,
        linewidth=2.4,
        label="Mean per-case speedup",
    )
    for x, y in zip(cores, means):
        left.annotate(f"{y:.4f}", (x, y), xytext=(0, 10), textcoords="offset points", ha="center", color=PALETTE["blue"], fontsize=7.4, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.3})
    left.set_title("Mean speedup", loc="left")
    left.set_xlabel("Number of cores")
    left.set_ylabel("Speedup (x)")
    left.set_xticks(cores)
    left.set_xlim(0.75, 5.25)
    left.set_ylim(0.75, max(5.35, float(means.max()) + 0.35))
    left.grid(axis="y", color=PALETTE["grid"], linewidth=0.7)
    left.legend(loc="upper left", fontsize=6.8)

    positions = np.arange(2, 6)
    right.plot(positions, positions, linestyle=(0, (4, 3)), linewidth=1.1, color=PALETTE["neutral"], label="Ideal linear")
    box = right.boxplot(
        distributions,
        positions=positions,
        widths=0.48,
        patch_artist=True,
        showfliers=True,
        medianprops={"color": PALETTE["red"], "linewidth": 1.6},
        whiskerprops={"color": PALETTE["blue"], "linewidth": 1.1},
        capprops={"color": PALETTE["blue"], "linewidth": 1.1},
        flierprops={"marker": "o", "markersize": 3, "markerfacecolor": PALETTE["red"], "markeredgecolor": "none", "alpha": 0.6},
    )
    for patch in box["boxes"]:
        patch.set_facecolor(PALETTE["blue_light"])
        patch.set_alpha(0.27)
        patch.set_edgecolor(PALETTE["blue"])
        patch.set_linewidth(1.2)
    rng = np.random.default_rng(4404)
    for x, values in zip(positions, distributions):
        jitter = rng.uniform(-0.12, 0.12, size=len(values))
        right.scatter(x + jitter, values, s=10, color=PALETTE["blue"], alpha=0.26, linewidths=0, zorder=2)
    right.set_title("Per-case distribution", loc="left")
    right.set_xlabel("Number of cores")
    right.set_ylabel("Speedup (x)")
    right.set_xticks(positions)
    right.set_xlim(1.5, 5.5)
    right.set_ylim(0.75, max(5.35, float(max(map(np.max, distributions))) + 0.25))
    right.grid(axis="y", color=PALETTE["grid"], linewidth=0.7)
    right.legend(loc="upper left", fontsize=6.8)
    np.testing.assert_allclose(left.lines[1].get_ydata(), means, rtol=0, atol=0)
    assert len(right.collections) == 4
    for collection, values in zip(right.collections, distributions):
        np.testing.assert_allclose(collection.get_offsets()[:, 1], values, rtol=0, atol=0)
    fig.tight_layout(rect=(0, 0.01, 1, 0.97), pad=0.65, w_pad=1.1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path.with_suffix(".png"), dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


PAPER_COMMIT = "6b1fdf25649b2b5bfc8d267896428187c3469291"
SOURCE_COMMIT = "a1bb4451cd85c46b32bb928d57c81e22cfeca1a6"
SOLVER_COMMIT = "834d8c957538ee069c66aadac9509552a4cc69d7"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    source = args.input_dir
    output = args.output or source
    output.mkdir(parents=True, exist_ok=True)
    receipt = json.loads((source / "paper-source-receipt.json").read_text(encoding="utf-8"))
    assert sha256_file(source / "paper-all-results.csv") == receipt["all_results_sha256"]
    assert sha256_file(source / "board-feed.json") == receipt["sources"][0]["sha256"]
    assert receipt["sources"][0]["commit"] == SOURCE_COMMIT
    with (source / "paper-all-results.csv").open(encoding="utf-8", newline="") as f:
        paper = [r for r in csv.DictReader(f) if r["problem"] == "P1"]
    records = json.loads((source / "board-feed.json").read_text(encoding="utf-8"))["records"]
    feed = {(r["case_id"], int(r["cores"])): r for r in records}
    with (source / "old-metrics.csv").open(encoding="utf-8", newline="") as f:
        old = {(r["case"], int(r["cores"])): r for r in csv.DictReader(f)}
    assert len(paper) == len(records) == len(feed) == len(old) == 500
    payload = []
    comparisons = []
    for r in paper:
        key = (r["case_id"], int(r["cores"]))
        f = feed[key]
        previous = old[key]
        assert r["solver_commit"] == f["solver_commit"] == SOLVER_COMMIT
        assert r["source_commit"] == SOURCE_COMMIT
        assert f["status"] == "ok" and f["problem"] == "P1" and f["evaluator"]["route"] == "E0"
        baseline, makespan = int(r["baseline_cycles"]), int(r["makespan_cycles"])
        assert makespan == f["metrics"]["makespan_cycles"]
        assert baseline == int(previous["baseline_cycles"])
        assert r["graph_sha256"] == f["identity"]["graph_sha256"] == f["baseline"]["graph_sha256"]
        assert r["plan_sha256"] == f["identity"]["plan_sha256"]
        ratio = baseline / makespan
        assert np.isclose(float(r["baseline_speedup"]), ratio, rtol=1e-12)
        assert np.isclose(float(r["official_curve_speedup"]), 1 if key[1] == 1 else ratio, rtol=1e-12)
        payload.append(dict(case_id=key[0], cores=key[1], baseline=baseline, makespan=makespan,
                            speedup=ratio, attempt_id=f["attempt_id"], revision=f["revision"]))
        comparisons.append(dict(case=key[0], cores=key[1], baseline_cycles=baseline,
                                old_makespan_cycles=int(previous["makespan_cycles"]),
                                new_makespan_cycles=makespan,
                                delta_cycles=makespan-int(previous["makespan_cycles"])))
    (output / "plot-input.json").write_text(json.dumps({"P1": payload}, indent=2)+"\n", encoding="utf-8")
    rows = load_rows(output / "plot-input.json")
    summary = summarise(rows)
    quality = json.loads((source / "QUALITY_SUMMARY.json").read_text(encoding="utf-8"))
    assert quality["solver_commit"] == SOLVER_COMMIT
    for s in summary:
        np.testing.assert_allclose(s["mean_observed_speedup"], quality["by_cores"][str(s["cores"])]["mean_speedup"], rtol=1e-12)
    write_normalized_tables(output/"metrics.csv", output/"summary.csv", rows, summary)
    write_csv(output/"version-comparison.csv", comparisons, list(comparisons[0]))
    plot_figure(rows, summary, output/"fig44_p1_speedup")
    audit = dict(status="locally_verified_candidate_awaiting_user_and_captain_review",
                 paper_commit=PAPER_COMMIT, solver_commit=SOLVER_COMMIT, source_commit=SOURCE_COMMIT,
                 grid_cells=500, unique_cases=100, source_feed_and_paper_csv_match=True,
                 baseline_unchanged_from_old_figure=True, plotted_artist_values_checked=True,
                 mean_observed_speedup=[s["mean_observed_speedup"] for s in summary],
                 mean_plotted_speedup=[s["mean_speedup"] for s in summary],
                 changed_makespans=sum(c["delta_cycles"] != 0 for c in comparisons),
                 solver_calls=0, evaluator_calls=0, old_agent_acceptance_not_transferred=True,
                 limitations="No new plan legality audit, evaluator rerun or raw baseline decompression; fixed paper baselines match all old figure denominators.",
                 inputs={n: sha256_file(source/n) for n in ["paper-all-results.csv", "paper-source-receipt.json", "board-feed.json", "QUALITY_SUMMARY.json", "old-metrics.csv"]},
                 outputs={n: sha256_file(output/n) for n in ["metrics.csv", "summary.csv", "version-comparison.csv", "plot-input.json", "fig44_p1_speedup.png", "fig44_p1_speedup.svg", "fig44_p1_speedup.pdf"]},
                 environment=dict(python=platform.python_version(), matplotlib=matplotlib.__version__, numpy=np.__version__))
    (output/"alignment-audit.json").write_text(json.dumps(audit, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:audit[k] for k in ["grid_cells", "mean_plotted_speedup", "changed_makespans", "status"]}, indent=2))

if __name__ == "__main__":
    main()
