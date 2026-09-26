"""Generate the eight assigned P123 figure delivery packages.

This module is intentionally read-only with respect to benchmark inputs. It
uses the fixed full500 records and writes reproducible figure packages under
``figures/a``. Missing scientific fields become explicit blocked reports; no
proxy field is substituted for a required quantity.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "results/a/p123-full500-lyx-20260925"
PER_CASE = DATA_DIR / "per_case.json"
INPUTS = DATA_DIR / "inputs"
OUT_ROOT = ROOT / "figures/a"
PALETTE = {
    "navy": "#123B5D",
    "blue": "#2574A9",
    "cyan": "#3AA7A3",
    "green": "#4C956C",
    "orange": "#E09F3E",
    "red": "#B6465F",
    "purple": "#7057A3",
    "ink": "#25313B",
    "muted": "#687782",
    "grid": "#D8E1E7",
    "paper": "#FFFFFF",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_records(problem: str) -> list[dict[str, Any]]:
    payload = load_json(INPUTS / f"{problem}.json")
    records = payload["records"]
    if len(records) != 500:
        raise ValueError(f"{problem}: expected 500 records, got {len(records)}")
    return records


def load_per_case() -> dict[str, list[dict[str, Any]]]:
    payload = load_json(PER_CASE)
    return {key: value for key, value in payload.items() if isinstance(value, list)}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": ["DejaVu Sans", "sans-serif"],
            "font.size": 9.5,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.labelsize": 9.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 1.0,
            "axes.labelcolor": PALETTE["ink"],
            "xtick.color": PALETTE["ink"],
            "ytick.color": PALETTE["ink"],
            "legend.frameon": False,
            "svg.fonttype": "none",
            "savefig.facecolor": PALETTE["paper"],
        }
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fmt_num(value: float | int | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.6g}" if isinstance(value, float) else str(value)


def quantile_rows(rows: list[dict[str, Any]], value_key: str = "solver_wall_seconds") -> list[dict[str, Any]]:
    result = []
    for cores in range(1, 6):
        values = np.array([float(row[value_key]) for row in rows if int(row["cores"]) == cores], dtype=float)
        values = values[np.isfinite(values)]
        if not len(values):
            result.append({"cores": cores, "n": 0, "median": None, "p95": None, "max": None})
        else:
            result.append(
                {
                    "cores": cores,
                    "n": int(len(values)),
                    "median": float(np.median(values)),
                    "p95": float(np.quantile(values, 0.95)),
                    "max": float(np.max(values)),
                }
            )
    return result


def save_figure(fig: plt.Figure, out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{stem}.png", out_dir / f"{stem}.svg", out_dir / f"{stem}.pdf"]
    fig.savefig(paths[0], dpi=300, bbox_inches="tight")
    fig.savefig(paths[1], bbox_inches="tight")
    fig.savefig(paths[2], bbox_inches="tight")
    plt.close(fig)
    return paths


def base_manifest(
    figure_id: str,
    title: str,
    out_dir: Path,
    status: str,
    progress: int,
    source_paths: list[Path],
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "figure_id": figure_id,
        "title": title,
        "protocol": "p123-figure-progress-v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "git_head": git_head(),
        "task_status": status,
        "progress": progress,
        "source": {
            "paths": [str(path.relative_to(ROOT)).replace("\\", "/") for path in source_paths],
            "sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path) for path in source_paths},
            "run_id": "p123-full500-lyx-20260925",
            "cells": 500,
            "cases": 100,
        },
        "outputs": {},
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "matplotlib": matplotlib.__version__,
            "command": "uv run python src/analysis/p123_figures_lyx/plot_all.py",
        },
        "budget_boundary": "read-only parsing and plotting; 0 new solver/E0/E1/E2 calls",
        "limitations": limitations,
    }


def finish_package(
    out_dir: Path,
    manifest: dict[str, Any],
    caption: str,
    readme: str,
    self_check: str,
    extra_paths: list[Path] | None = None,
) -> None:
    (out_dir / "caption.md").write_text(caption.rstrip() + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(readme.rstrip() + "\n", encoding="utf-8")
    (out_dir / "self-check.md").write_text(self_check.rstrip() + "\n", encoding="utf-8")
    source_copy = out_dir / "plot_figures.py"
    if not source_copy.exists() or not source_copy.samefile(Path(__file__)):
        shutil.copy2(Path(__file__), source_copy)
    output_paths = [out_dir / "caption.md", out_dir / "README.md", out_dir / "self-check.md", source_copy]
    if extra_paths:
        output_paths.extend(extra_paths)
    for path in output_paths:
        manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def common_rows(records: list[dict[str, Any]], problem: str) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        metrics = record.get("metrics", {})
        rows.append(
            {
                "problem": problem,
                "case": str(record["case_id"]),
                "cores": int(record["cores"]),
                "status": record.get("status", "unknown"),
                "makespan_cycles": float(metrics.get("makespan_cycles", np.nan)),
                "solver_wall_seconds": float(metrics.get("solver_wall_seconds", np.nan)),
                "evaluation_wall_seconds": metrics.get("evaluation_wall_seconds"),
                "ddr_bytes": float(metrics.get("ddr_bytes", np.nan)),
                "extra_ddr_bytes": float(metrics.get("extra_ddr_bytes", np.nan)),
                "spill_bytes": float(metrics.get("spill_bytes", np.nan)),
                "runtime_id": record.get("runtime_id", "unknown"),
                "algorithm_id": record.get("algorithm_id", "unknown"),
                "run_id": record.get("run_id", "unknown"),
                "attempt_id": record.get("attempt_id", ""),
            }
        )
    return rows


def write_common_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(
        path,
        rows,
        [
            "problem", "case", "cores", "status", "makespan_cycles", "solver_wall_seconds",
            "evaluation_wall_seconds", "ddr_bytes", "extra_ddr_bytes", "spill_bytes",
            "runtime_id", "algorithm_id", "run_id", "attempt_id",
        ],
    )


def make_fig53() -> Path:
    out = OUT_ROOT / "p123-fig-5-3-lyx-20260926"
    rows = common_rows(load_records("P2"), "P2")
    by_core = []
    for core in range(1, 6):
        values = np.array([row["makespan_cycles"] for row in rows if row["cores"] == core], dtype=float)
        baseline = np.array([row["makespan_cycles"] for row in rows if row["cores"] == 1], dtype=float)
        base_by_case = {row["case"]: row["makespan_cycles"] for row in rows if row["cores"] == 1}
        ratios = np.array([base_by_case[row["case"]] / row["makespan_cycles"] for row in rows if row["cores"] == core], dtype=float)
        plot_values = np.ones_like(ratios) if core == 1 else ratios
        by_core.extend(
            {
                "method": "q2-adaptive-budget",
                "case": row["case"],
                "cores": core,
                "baseline_cycles": base_by_case[row["case"]],
                "makespan_cycles": row["makespan_cycles"],
                "observed_speedup": base_by_case[row["case"]] / row["makespan_cycles"],
                "plot_speedup": 1.0 if core == 1 else base_by_case[row["case"]] / row["makespan_cycles"],
            }
            for row in rows if row["cores"] == core
        )
        _ = values, baseline, plot_values
    summary = []
    for core in range(1, 6):
        vals = np.array([r["plot_speedup"] for r in by_core if r["cores"] == core], dtype=float)
        observed = np.array([r["observed_speedup"] for r in by_core if r["cores"] == core], dtype=float)
        summary.append({"method": "q2-adaptive-budget", "cores": core, "n": len(vals), "mean_speedup": float(vals.mean()), "sd_speedup": float(vals.std(ddof=1)), "mean_observed_speedup": float(observed.mean())})
    setup_style()
    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    x = np.arange(1, 6)
    means = [r["mean_speedup"] for r in summary]
    ax.plot(x, x, linestyle=(0, (4, 3)), color=PALETTE["muted"], linewidth=1.2, label="Ideal linear")
    ax.plot(x, means, marker="o", linewidth=2.6, color=PALETTE["purple"], label="q2-adaptive-budget")
    for core, value in zip(x, means):
        ax.annotate(f"{value:.2f}", (core, value), xytext=(0, 8), textcoords="offset points", ha="center", color=PALETTE["purple"])
    ax.set_title("Figure 5-3 | P2 multicore speedup", loc="left")
    ax.set_xlabel("Number of cores")
    ax.set_ylabel("Mean per-case speedup (x)")
    ax.set_xticks(x)
    ax.set_xlim(0.75, 5.25)
    ax.set_ylim(0.8, 5.25)
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.7)
    ax.legend(loc="upper left")
    ax.text(0.0, -0.18, "Only one complete P2 method is present in the fixed 500-cell batch; no historical or partial series are joined.", transform=ax.transAxes, fontsize=8, color=PALETTE["muted"])
    paths = save_figure(fig, out, "fig53_p2_speedup")
    rows_path = out / "per_case_speedup.csv"
    summary_path = out / "method_core_summary.csv"
    write_csv(rows_path, by_core, ["method", "case", "cores", "baseline_cycles", "makespan_cycles", "observed_speedup", "plot_speedup"])
    write_csv(summary_path, summary, ["method", "cores", "n", "mean_speedup", "sd_speedup", "mean_observed_speedup"])
    manifest = base_manifest("fig-5-3", "P2 multicore speedup", out, "ready_for_human_review", 100, [INPUTS / "P2.json", PER_CASE], ["Only q2-adaptive-budget has complete 100-case coverage in this source batch.", "The k=1 plot anchor is fixed to 1.0; observed k=1 ratios remain in the CSV.", "SVG/PDF were generated but not opened in a desktop reader in this session."])
    manifest["method_coverage"] = {"q2-adaptive-budget": {"cores": [1, 2, 3, 4, 5], "cases_per_core": 100}}
    manifest["outputs"].update({p.name: sha256_file(p) for p in paths + [rows_path, summary_path]})
    finish_package(out, manifest, "Figure 5-3. P2 mean per-case speedup for the complete q2-adaptive-budget method. Each speedup is computed from the common per-case single-core denominator before arithmetic averaging by core count. The prescribed k=1 display anchor is 1.0; observed single-core ratios remain in the audit table. No incomplete or historical method series is joined.", "# Figure 5-3 delivery\n\nComplete P2 method comparison from the fixed 500-cell input. The source batch contains one complete method, so the figure has one honest series rather than a synthetic multi-method comparison.\n\n- Reproduce: `uv run python src/analysis/p123_figures_lyx/plot_all.py --figure 5-3`\n- Outputs: `fig53_p2_speedup.png`, `.svg`, `.pdf`\n- Input: `results/a/p123-full500-lyx-20260925/inputs/P2.json`\n", "# Figure 5-3 self-check\n\n- [x] 500 P2 records and 100 cases x 5 cores.\n- [x] Common per-case single-core denominator.\n- [x] Mean is arithmetic mean of per-case ratios.\n- [x] Only complete method is plotted; no historical splice.\n- [ ] Desktop SVG/PDF inspection: not performed.\n- [ ] yuanzhifang scientific acceptance: pending.\n", [rows_path, summary_path])
    return out


def make_fig63() -> Path:
    out = OUT_ROOT / "p123-fig-6-3-lyx-20260926"
    pairs = load_per_case()["P3_verified_cache_pairs"]
    base_by_case = {str(row["case_id"]): float(row["baseline"]) for row in pairs if int(row["cores"]) == 1}
    rows = []
    for row in pairs:
        case = str(row["case_id"])
        core = int(row["cores"])
        baseline = base_by_case[case]
        cache = float(row["cache"])
        no_cache = float(row["no_cache"])
        rows.append({"case": case, "cores": core, "baseline_cycles": baseline, "cache_cycles": cache, "no_cache_cycles": no_cache, "cache_speedup": baseline / cache, "no_cache_speedup": baseline / no_cache, "cache_gain": no_cache / cache, "attempt_id": row.get("attempt_id", ""), "revision": row.get("revision", 0)})
    summary = []
    for core in range(1, 6):
        subset = [r for r in rows if r["cores"] == core]
        summary.append({"cores": core, "n": len(subset), "cache_mean_speedup": float(np.mean([r["cache_speedup"] for r in subset])), "no_cache_mean_speedup": float(np.mean([r["no_cache_speedup"] for r in subset])), "cache_gain_mean": float(np.mean([r["cache_gain"] for r in subset]))})
    setup_style()
    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    x = np.arange(1, 6)
    ax.plot(x, [r["no_cache_mean_speedup"] for r in summary], marker="o", linewidth=2.5, color=PALETTE["orange"], label="Same-plan no L2")
    ax.plot(x, [r["cache_mean_speedup"] for r in summary], marker="o", linewidth=2.5, color=PALETTE["cyan"], label="Same-plan read-only Cache")
    ax.set_title("Figure 6-3 | P3 cache configuration comparison", loc="left")
    ax.set_xlabel("Number of cores")
    ax.set_ylabel("Mean speedup vs common single-core baseline (x)")
    ax.set_xticks(x)
    ax.set_xlim(0.75, 5.25)
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.7)
    ax.legend(loc="upper left")
    ax.text(0.0, -0.17, "Each point averages 100 same-case pairs; the two curves are not reconstructed from CacheGain.", transform=ax.transAxes, fontsize=8, color=PALETTE["muted"])
    paths = save_figure(fig, out, "fig63_p3_cache_comparison")
    rows_path = out / "paired_500.csv"
    summary_path = out / "core_summary.csv"
    write_csv(rows_path, rows, ["case", "cores", "baseline_cycles", "cache_cycles", "no_cache_cycles", "cache_speedup", "no_cache_speedup", "cache_gain", "attempt_id", "revision"])
    write_csv(summary_path, summary, ["cores", "n", "cache_mean_speedup", "no_cache_mean_speedup", "cache_gain_mean"])
    manifest = base_manifest("fig-6-3", "P3 no-L2 versus read-only Cache", out, "ready_for_human_review", 100, [PER_CASE, INPUTS / "P3.json"], ["The per_case table is the fixed same-plan cache-pair source.", "Plan hashes are preserved in the P3 input records; byte hit/miss fields are not needed for this comparison.", "SVG/PDF were generated but not opened in a desktop reader in this session."])
    manifest["pairing"] = {"expected": 500, "actual": len(rows), "cases_per_core": {str(core): sum(r["cores"] == core for r in rows) for core in range(1, 6)}}
    manifest["outputs"].update({p.name: sha256_file(p) for p in paths + [rows_path, summary_path]})
    finish_package(out, manifest, "Figure 6-3. P3 same-plan comparison of no-L2 and read-only Cache configurations. For each case and core count, both makespans are divided by the same fixed single-core baseline, then averaged across 100 cases. The pair table retains the per-case values and cache gain for reuse by Figure 6-4.", "# Figure 6-3 delivery\n\nThis package compares the actual 500 same-case/cache pairs. No CacheGain inversion is used to create the no-L2 curve.\n", "# Figure 6-3 self-check\n\n- [x] 500 paired rows, 100 per core count.\n- [x] Common single-core denominator per case.\n- [x] Both curves use directly recorded cache/no-cache makespans.\n- [ ] Independent plan-hash audit from raw plan files: not repeated here; source hashes retained in input records.\n- [ ] Desktop SVG/PDF inspection: not performed.\n- [ ] yuanzhifang acceptance: pending.\n", [rows_path, summary_path])
    return out


def make_fig64() -> Path:
    out = OUT_ROOT / "p123-fig-6-4-lyx-20260926"
    pairs = load_per_case()["P3_verified_cache_pairs"]
    rows = [{"case": str(r["case_id"]), "cores": int(r["cores"]), "cache_gain": float(r["cache_gain"]), "cache_cycles": float(r["cache"]), "no_cache_cycles": float(r["no_cache"]), "hit_bytes": "NA", "miss_bytes": "NA", "byte_hit_rate": "NA"} for r in pairs]
    summary = []
    for core in range(1, 6):
        vals = np.array([r["cache_gain"] for r in rows if r["cores"] == core], dtype=float)
        summary.append({"cores": core, "n": len(vals), "mean_cache_gain": float(vals.mean()), "sd_cache_gain": float(vals.std(ddof=1)), "median_cache_gain": float(np.median(vals)), "min_cache_gain": float(vals.min()), "max_cache_gain": float(vals.max()), "negative_n": int(np.sum(vals < 1.0))})
    negative = [r for r in rows if r["cache_gain"] < 1.0]
    setup_style()
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.8), gridspec_kw={"width_ratios": [1.0, 1.25, 1.05]})
    x = np.arange(1, 6)
    axes[0].plot(x, [r["mean_cache_gain"] for r in summary], marker="o", linewidth=2.4, color=PALETTE["cyan"])
    axes[0].axhline(1.0, linestyle=(0, (4, 3)), color=PALETTE["muted"], linewidth=1.0)
    axes[0].set_title("Mean CacheGain", loc="left")
    axes[0].set_xlabel("Cores")
    axes[0].set_ylabel("No L2 / Cache")
    axes[0].set_xticks(x)
    axes[0].grid(axis="y", color=PALETTE["grid"], linewidth=0.7)
    distributions = [np.array([r["cache_gain"] for r in rows if r["cores"] == core]) for core in range(1, 6)]
    box = axes[1].boxplot(distributions, positions=x, patch_artist=True, widths=0.55, showfliers=True, medianprops={"color": PALETTE["red"], "linewidth": 1.5}, whiskerprops={"color": PALETTE["navy"]}, capprops={"color": PALETTE["navy"]}, flierprops={"marker": "o", "markersize": 2.5, "markerfacecolor": PALETTE["red"], "markeredgecolor": "none", "alpha": 0.5})
    for patch in box["boxes"]:
        patch.set_facecolor(PALETTE["cyan"])
        patch.set_alpha(0.28)
        patch.set_edgecolor(PALETTE["cyan"])
    axes[1].axhline(1.0, linestyle=(0, (4, 3)), color=PALETTE["muted"], linewidth=1.0)
    axes[1].set_title("Per-case distribution", loc="left")
    axes[1].set_xlabel("Cores")
    axes[1].set_ylabel("CacheGain")
    axes[1].set_xticks(x)
    axes[1].grid(axis="y", color=PALETTE["grid"], linewidth=0.7)
    axes[2].axis("off")
    axes[2].text(0.02, 0.96, "Byte-hit relation", transform=axes[2].transAxes, va="top", fontsize=11, fontweight="bold", color=PALETTE["ink"])
    axes[2].text(0.02, 0.82, "BLOCKED: required fields absent", transform=axes[2].transAxes, va="top", color=PALETTE["red"], fontweight="bold")
    axes[2].text(0.02, 0.67, "hit_bytes and miss_bytes are not\npresent in the fixed P3 records.\n\ncache_hit_rate is available in\nsource inputs, but the task\nrequires byte-based hit rate;\nit is not used as a proxy.", transform=axes[2].transAxes, va="top", linespacing=1.5, color=PALETTE["muted"])
    fig.suptitle("Figure 6-4 | Cache gain and byte-hit-rate relation", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    paths = save_figure(fig, out, "fig64_p3_cache_gain")
    rows_path = out / "cache_gain_rows.csv"
    summary_path = out / "cache_gain_summary.csv"
    negative_path = out / "negative_cache_gain.csv"
    write_csv(rows_path, rows, ["case", "cores", "cache_gain", "cache_cycles", "no_cache_cycles", "hit_bytes", "miss_bytes", "byte_hit_rate"])
    write_csv(summary_path, summary, ["cores", "n", "mean_cache_gain", "sd_cache_gain", "median_cache_gain", "min_cache_gain", "max_cache_gain", "negative_n"])
    write_csv(negative_path, negative, ["case", "cores", "cache_gain", "cache_cycles", "no_cache_cycles", "hit_bytes", "miss_bytes", "byte_hit_rate"])
    manifest = base_manifest("fig-6-4", "P3 CacheGain and byte hit rate", out, "blocked_data", 65, [PER_CASE, INPUTS / "P3.json"], ["hit_bytes and miss_bytes are absent from the fixed source records.", "The third relation panel is an explicit data-gap panel; no cache_hit_rate or access count is substituted.", "SVG/PDF were generated but not opened in a desktop reader in this session."])
    manifest["missing_fields"] = ["hit_bytes", "miss_bytes"]
    manifest["available_partial"] = ["CacheGain mean and distribution", "negative CacheGain list"]
    manifest["negative_count"] = len(negative)
    manifest["outputs"].update({p.name: sha256_file(p) for p in paths + [rows_path, summary_path, negative_path]})
    finish_package(out, manifest, "Figure 6-4. The first two panels report directly computed CacheGain = no-L2 makespan / read-only Cache makespan, retaining all negative gains. The required byte-hit-rate relation is intentionally blocked because the fixed source has no hit_bytes or miss_bytes fields; cache_hit_rate is not a byte-rate substitute.", "# Figure 6-4 delivery\n\nThe CacheGain panels are complete from the fixed 500 paired records. The byte-hit-rate relation remains blocked until the required byte fields are published.\n", "# Figure 6-4 self-check\n\n- [x] CacheGain recomputed from paired makespans.\n- [x] All 500 rows retained, including negative gains.\n- [x] Negative-gain list exported.\n- [x] Missing `hit_bytes` and `miss_bytes` recorded explicitly.\n- [x] No proxy field used for byte hit rate.\n- [ ] Byte-hit relation: blocked by source data gap.\n- [ ] yuanzhifang acceptance: pending.\n", [rows_path, summary_path, negative_path])
    return out


def make_fig45() -> Path:
    out = OUT_ROOT / "p123-fig-4-5-lyx-20260926"
    rows = common_rows(load_records("P1"), "P1")
    stats = quantile_rows(rows)
    setup_style()
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.8), gridspec_kw={"width_ratios": [1.1, 1.0, 1.1]})
    for core in range(1, 6):
        subset = [r for r in rows if r["cores"] == core]
        axes[0].scatter([r["solver_wall_seconds"] for r in subset], [r["makespan_cycles"] for r in subset], s=12, alpha=0.38, color=plt.cm.viridis((core - 1) / 4), label=f"k={core}")
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_title("Quality versus solver cost", loc="left")
    axes[0].set_xlabel("Solver wall (s, log)")
    axes[0].set_ylabel("Official Makespan (cycles, log)")
    axes[0].grid(True, which="both", color=PALETTE["grid"], linewidth=0.55)
    axes[0].legend(ncol=2, fontsize=8)
    values = [np.array([r["solver_wall_seconds"] for r in rows if r["cores"] == core]) for core in range(1, 6)]
    axes[1].boxplot(values, positions=np.arange(1, 6), patch_artist=True, widths=0.55, showfliers=True, medianprops={"color": PALETTE["red"], "linewidth": 1.4}, boxprops={"facecolor": PALETTE["blue"], "alpha": 0.22})
    axes[1].set_yscale("log")
    axes[1].set_title("Solver wall distribution", loc="left")
    axes[1].set_xlabel("Cores")
    axes[1].set_ylabel("Solver wall (s, log)")
    axes[1].set_xticks(np.arange(1, 6))
    axes[1].grid(axis="y", which="both", color=PALETTE["grid"], linewidth=0.6)
    ddr_means = [np.mean([r["ddr_bytes"] for r in rows if r["cores"] == core]) for core in range(1, 6)]
    extra_means = [np.mean([r["extra_ddr_bytes"] for r in rows if r["cores"] == core]) for core in range(1, 6)]
    axes[2].plot(np.arange(1, 6), np.array(ddr_means) / 2**20, marker="o", color=PALETTE["navy"], linewidth=2.2, label="DDR bytes")
    axes[2].plot(np.arange(1, 6), np.array(extra_means) / 2**20, marker="o", color=PALETTE["orange"], linewidth=2.2, label="Extra DDR bytes")
    axes[2].set_title("搬运代价 (mean)", loc="left")
    axes[2].set_xlabel("Cores")
    axes[2].set_ylabel("MiB per cell")
    axes[2].set_xticks(np.arange(1, 6))
    axes[2].grid(axis="y", color=PALETTE["grid"], linewidth=0.7)
    axes[2].legend(fontsize=8)
    fig.suptitle("Figure 4-5 | P1 quality, transfer cost and solver wall", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    paths = save_figure(fig, out, "fig45_p1_quality_cost")
    rows_path = out / "p1_quality_cost_rows.csv"
    stats_path = out / "solver_wall_quantiles.csv"
    write_common_rows(rows_path, rows)
    write_csv(stats_path, stats, ["cores", "n", "median", "p95", "max"])
    manifest = base_manifest("fig-4-5", "P1 quality, transfer cost and solver cost", out, "ready_for_human_review", 100, [INPUTS / "P1.json"], ["solver wall is the recorded solver scope; independent E0 timing is retained separately in the input records.", "DDR values are reported in MiB only for display; source tables retain bytes.", "A cross-case cloud is descriptive, not a Pareto claim.", "SVG/PDF were generated but not opened in a desktop reader in this session."])
    manifest["outputs"].update({p.name: sha256_file(p) for p in paths + [rows_path, stats_path]})
    finish_package(out, manifest, "Figure 4-5. P1 official Makespan, solver wall and DDR transfer cost from the same per-cell records. The left panel is a descriptive log-scale quality/cost cloud, the middle panel shows per-core solver-wall distributions, and the right panel reports mean DDR and extra DDR bytes. Solver wall includes online preparation and E1 where recorded; independent E0 timing remains a separate source field.", "# Figure 4-5 delivery\n\nThree panels connect P1 official quality, solver wall and transfer cost without declaring a cross-case Pareto frontier.\n", "# Figure 4-5 self-check\n\n- [x] 500 P1 records retained.\n- [x] Makespan, solver wall and DDR fields are bound to each record.\n- [x] Median/P95/max table generated from per-cell wall times.\n- [x] DDR display uses MiB while source CSV keeps bytes.\n- [ ] Desktop SVG/PDF inspection: not performed.\n- [ ] yuanzhifang acceptance: pending.\n", [rows_path, stats_path])
    return out


def make_efficiency_figure(problem: str, figure_id: str, figure_no: str, title: str) -> Path:
    out = OUT_ROOT / f"p123-fig-{figure_no}-lyx-20260926"
    rows = common_rows(load_records(problem), problem)
    stats = quantile_rows(rows)
    setup_style()
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.9), gridspec_kw={"width_ratios": [1.12, 1.0]})
    colors = [plt.cm.viridis((core - 1) / 4) for core in range(1, 6)]
    for core, color in zip(range(1, 6), colors):
        subset = [r for r in rows if r["cores"] == core]
        axes[0].scatter([r["solver_wall_seconds"] for r in subset], [r["makespan_cycles"] for r in subset], s=13, alpha=0.42, color=color, label=f"k={core}")
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_title("Quality versus solver wall", loc="left")
    axes[0].set_xlabel("Solver wall (s, log)")
    axes[0].set_ylabel("Official Makespan (cycles, log)")
    axes[0].grid(True, which="both", color=PALETTE["grid"], linewidth=0.55)
    axes[0].legend(ncol=2, fontsize=8)
    for core, color in zip(range(1, 6), colors):
        vals = np.sort(np.array([r["solver_wall_seconds"] for r in rows if r["cores"] == core], dtype=float))
        y = np.arange(1, len(vals) + 1) / len(vals)
        axes[1].step(vals, y, where="post", color=color, linewidth=1.8, label=f"k={core}")
    axes[1].set_xscale("log")
    axes[1].set_ylim(0, 1.02)
    axes[1].set_title("Solver-wall ECDF", loc="left")
    axes[1].set_xlabel("Solver wall (s, log)")
    axes[1].set_ylabel("Cumulative fraction")
    axes[1].grid(True, which="both", color=PALETTE["grid"], linewidth=0.55)
    axes[1].legend(fontsize=8)
    p95 = max((row["p95"] for row in stats if row["p95"] is not None), default=0.0)
    axes[1].axvline(p95, linestyle=(0, (4, 3)), color=PALETTE["red"], linewidth=1.0, label="largest per-core P95")
    fig.suptitle(f"Figure {figure_no} | {title}", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    paths = save_figure(fig, out, f"fig{figure_no.replace('-', '')}_{problem.lower()}_quality_cost")
    rows_path = out / f"{problem.lower()}_quality_cost_rows.csv"
    stats_path = out / "solver_wall_quantiles.csv"
    write_common_rows(rows_path, rows)
    write_csv(stats_path, stats, ["cores", "n", "median", "p95", "max"])
    source = INPUTS / f"{problem}.json"
    timing_note = "Online E0 is included in the recorded P3 solver wall." if problem == "P3" else "P2 solver wall is recorded separately from its final external E0 evaluation."
    manifest = base_manifest(figure_id, title, out, "ready_for_human_review", 100, [source], [timing_note, "No strict cold-start interpretation is made because OS cache state is not controlled.", "SVG/PDF were generated but not opened in a desktop reader in this session."])
    manifest["outputs"].update({p.name: sha256_file(p) for p in paths + [rows_path, stats_path]})
    finish_package(out, manifest, f"Figure {figure_no}. {title}. Each point pairs official Makespan with the solver wall from the same input record; the right panel is an empirical CDF of the 100 per-core wall times. Median, P95 and maximum are recomputed from the raw per-cell records. {timing_note}", f"# Figure {figure_no} delivery\n\nThis package contains a quality-versus-solver-wall cloud and per-core ECDF from the fixed {problem} 500-cell feed.\n", f"# Figure {figure_no} self-check\n\n- [x] 500 source records retained.\n- [x] Makespan and solver wall remain paired by case/core.\n- [x] Per-core median/P95/max recomputed from raw rows.\n- [x] No cold-start label or cross-platform speedup claim.\n- [ ] Desktop SVG/PDF inspection: not performed.\n- [ ] yuanzhifang acceptance: pending.\n", [rows_path, stats_path])
    return out


def make_fig67_forest() -> Path:
    out = OUT_ROOT / "p123-fig-6-7-lyx-20260926"
    forest_path = ROOT / "forest-revision2-offline/P3-forest-revision2.json"
    feed_dir = forest_path.parent / "feeds"
    feed_paths = sorted(feed_dir.glob("board-feed-s*-revision2.json"))
    if len(feed_paths) != 10:
        raise ValueError(f"expected 10 fixed forest feeds, found {len(feed_paths)}")
    payload = load_json(forest_path)
    records = payload.get("records", [])
    expected = {(f"{case:03d}", core) for case in range(1, 101) for core in range(1, 6)}
    actual = {(str(row["case_id"]), int(row["cores"])) for row in records}
    if len(records) != 500 or actual != expected:
        raise ValueError("forest revision2 input must contain exactly 500 unique case/core cells")
    if payload.get("source_commit") != "19bebf35205d23fdd832781540f8879da52eeb62":
        raise ValueError("unexpected forest source commit")
    if payload.get("solver_commit") != "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1":
        raise ValueError("unexpected forest solver commit")
    rows = []
    for record in records:
        env = record["provenance"]["environment"]
        params = record["parameters"]
        timing = record["timing"]
        metrics = record["metrics"]
        rows.append(
            {
                "case": str(record["case_id"]),
                "cores": int(record["cores"]),
                "status": record["status"],
                "makespan": int(metrics["makespan_cycles"]),
                "extra_ddr": int(metrics["extra_ddr_bytes"]),
                "solver_wall": float(metrics["solver_wall_seconds"]),
                "evaluation_wall_seconds": metrics.get("evaluation_wall_seconds"),
                "platform": str(env["os"]),
                "cpu": str(env["cpu"]),
                "workers": int(env["workers"]),
                "global_max_workers": int(params["global_max_workers"]),
                "timing_scope": str(record["provenance"]["measurement"]["solver_scope"]),
                "timing_includes_evaluation": bool(timing["solver_includes_evaluation"]),
                "attempt_id": record["attempt_id"],
                "revision": int(record["revision"]),
                "run_id": record["run_id"],
                "algorithm_id": record["algorithm_id"],
                "solver_commit": record["solver_commit"],
                "graph_sha256": record["identity"]["graph_sha256"],
                "config_sha256": record["identity"]["config_sha256"],
                "plan_sha256": record["identity"]["plan_sha256"],
                "source_result_path": record["artifacts"]["result"]["path"],
            }
        )
    if any(row["status"] != "ok" for row in rows):
        raise ValueError("forest feed contains a non-ok record")
    metrics_path = out / "p3_quality_cost_rows.csv"
    summary_path = out / "solver_wall_quantiles.csv"
    fields = [
        "case", "cores", "status", "makespan", "extra_ddr", "solver_wall",
        "evaluation_wall_seconds", "platform", "cpu", "workers", "global_max_workers",
        "timing_scope", "timing_includes_evaluation", "attempt_id", "revision", "run_id",
        "algorithm_id", "solver_commit", "graph_sha256", "config_sha256", "plan_sha256",
        "source_result_path",
    ]
    write_csv(metrics_path, rows, fields)
    summary = []
    groups = {}
    for row in rows:
        key = (row["cores"], row["platform"], row["workers"], row["timing_scope"])
        groups.setdefault(key, []).append(row)
    for (cores, platform_name, workers, timing_scope), group in sorted(groups.items()):
        values = np.array([row["solver_wall"] for row in group], dtype=float)
        summary.append(
            {
                "cores": cores,
                "platform": platform_name,
                "workers": workers,
                "timing_scope": timing_scope,
                "n": len(values),
                "median": float(np.median(values)),
                "p95": float(np.quantile(values, 0.95)),
                "max": float(np.max(values)),
            }
        )
    write_csv(summary_path, summary, ["cores", "platform", "workers", "timing_scope", "n", "median", "p95", "max"])
    setup_style()
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 4.7), gridspec_kw={"width_ratios": [1.12, 1.0]})
    colors = [PALETTE["blue"], PALETTE["green"], PALETTE["orange"], PALETTE["red"], PALETTE["purple"]]
    markers = ["o", "s", "^", "D", "P"]
    linestyles = ["-", "--", "-.", ":", (0, (5, 1, 1, 1))]
    for core, color, marker in zip(range(1, 6), colors, markers):
        subset = [row for row in rows if row["cores"] == core]
        axes[0].scatter(
            [row["solver_wall"] for row in subset],
            [row["makespan"] for row in subset],
            s=11,
            alpha=0.48,
            color=color,
            marker=marker,
            edgecolors="none",
            label=f"k={core}",
        )
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_title("Quality versus solver wall", loc="left")
    axes[0].set_xlabel("Solver wall (s, log)")
    axes[0].set_ylabel("Official Makespan (cycles, log)")
    axes[0].grid(True, which="both", color=PALETTE["grid"], linewidth=0.5)
    axes[0].legend(ncol=2, fontsize=7.5, handletextpad=0.35, columnspacing=0.7)
    largest_p95 = max(item["p95"] for item in summary)
    for core, color, style in zip(range(1, 6), colors, linestyles):
        values = np.sort(np.array([row["solver_wall"] for row in rows if row["cores"] == core], dtype=float))
        y = np.arange(1, len(values) + 1) / len(values)
        axes[1].step(values, y, where="post", color=color, linestyle=style, linewidth=1.55, label=f"k={core}")
    axes[1].axvline(
        largest_p95,
        linestyle=(0, (4, 2)),
        color=PALETTE["ink"],
        linewidth=1.0,
        label=f"largest per-core P95 = {largest_p95:.2f} s",
    )
    axes[1].set_xscale("log")
    axes[1].set_ylim(0, 1.02)
    axes[1].set_title("Solver-wall ECDF", loc="left")
    axes[1].set_xlabel("Solver wall (s, log)")
    axes[1].set_ylabel("Cumulative fraction")
    axes[1].grid(True, which="both", color=PALETTE["grid"], linewidth=0.5)
    axes[1].legend(fontsize=7.0, loc="lower right", frameon=False)
    fig.suptitle("Figure 6-7 | P3 quality, solver cost and tail latency", fontsize=11.5, fontweight="bold", y=0.995)
    fig.text(0.01, 0.012, "Forest revision 2; online E0 is included in solver wall; no standalone external E0 timer.", fontsize=7.2, color=PALETTE["muted"])
    fig.tight_layout(rect=[0, 0.055, 1, 0.95])
    paths = save_figure(fig, out, "fig67_p3_quality_cost")
    manifest = base_manifest(
        "fig-6-7",
        "P3 quality, solver cost and tail latency",
        out,
        "ready_for_human_review",
        100,
        [forest_path, *feed_paths],
        [
            "Forest revision 2 records are pinned to the stated source and solver commits.",
            "Online E0 is included in solver wall; evaluation_wall_seconds is null because no standalone external timer was recorded.",
            "The vertical line is the largest of the five per-core P95 values, not an overall P95.",
            "SVG/PDF were generated but not opened in a desktop reader in this session.",
        ],
    )
    manifest["source"].update(
        {
            "commit": payload["source_commit"],
            "solver_commit": payload["solver_commit"],
            "repository_path": "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/board-feed-s01..s10-revision2.json",
            "feed_count": len(feed_paths),
            "cells": len(rows),
            "run_id": rows[0]["run_id"],
            "algorithm_id": rows[0]["algorithm_id"],
        }
    )
    manifest["environment"]["command"] = "python figures/a/p123-fig-5-6-lyx-20260926/plot_figures.py --figure 6-7"
    manifest["outputs"].update({p.name: sha256_file(p) for p in paths + [metrics_path, summary_path]})
    finish_package(
        out,
        manifest,
        "Figure 6-7. P3 official Makespan versus the end-to-end solver wall from forest revision 2. The solver wall includes child startup, input reading, construction, integrated online E0 selection/verification, evidence writes and cleanup; no standalone external final-evaluation timer was recorded. The vertical marker is the largest per-core P95 and is not an overall P95 or a quality threshold.",
        "# Figure 6-7 delivery\n\nThis package uses the fixed forest revision-2 feed (500 unique case/core cells) and keeps quality and wall-clock values from the same record.\n\n- Source commit: `19bebf35205d23fdd832781540f8879da52eeb62`\n- Solver commit: `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`\n- Reproduce: `python figures/a/p123-fig-5-6-lyx-20260926/plot_figures.py --figure 6-7`\n- Outputs: `fig67_p3_quality_cost.png`, `.svg`, `.pdf`, `p3_quality_cost_rows.csv`, `solver_wall_quantiles.csv`\n- Budget: read-only parsing and plotting; no new solver or evaluator calls.\n",
        "# Figure 6-7 self-check\n\n- [x] 500 forest revision-2 records, 100 cases x 5 cores.\n- [x] Makespan, extra DDR and solver wall remain paired by case/core.\n- [x] Resource fields retain platform, CPU, per-shard workers and global batch worker cap.\n- [x] Solver-wall median/P95/max use linear interpolation over the five 100-cell groups.\n- [x] Vertical marker is labeled as the largest per-core P95.\n- [x] PNG inspected locally; no desktop SVG/PDF reader inspection claimed.\n- [ ] yuanzhifang scientific acceptance: pending.\n",
        [metrics_path, summary_path],
    )
    audit_files = paths + [metrics_path, summary_path, out / "caption.md", out / "README.md", out / "self-check.md", out / "plot_figures.py", out / "manifest.json"]
    audit = {
        "schema": "figure-auto-review-v1",
        "figure_id": "fig-6-7",
        "primary": "fig67_p3_quality_cost.svg",
        "files": [{"name": path.name, "role": "svg" if path.suffix == ".svg" else "png" if path.suffix == ".png" else "pdf" if path.suffix == ".pdf" else "source" if path.name == "plot_figures.py" else "input" if path.suffix == ".csv" else "notes", "sha256": sha256_file(path), "size": path.stat().st_size} for path in audit_files],
        "command": "python figures/a/p123-fig-5-6-lyx-20260926/plot_figures.py --figure 6-7",
        "sources": [{"path": "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/board-feed-s01..s10-revision2.json", "commit": payload["source_commit"], "working_copy_sha256": sha256_file(forest_path), "feed_sha256": {path.name: sha256_file(path) for path in feed_paths}}],
        "units": {"makespan": "cycles", "wall": "s", "bytes": "B"},
        "panels": [{"id": "quality_cost", "title": "Quality versus solver wall"}, {"id": "ecdf", "title": "Solver-wall ECDF"}],
        "tables": {"metrics": metrics_path.name, "summary": summary_path.name},
        "coverage": {"cases": 100, "cores": [1, 2, 3, 4, 5], "cells": 500},
        "visual_check": {"png_opened": True, "svg_opened": False, "pdf_opened": False, "paper_width_preview": False},
        "status": "submitted_for_review",
        "notes": ["No solver/E0/E1/E2 calls were made by the plotting command.", "evaluation_wall_seconds is null in the fixed feed and is not filled with zero.", "audit.json is excluded from manifest.outputs to avoid self-reference."],
    }
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def recursive_keys(value: Any, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.add(path)
            keys.update(recursive_keys(child, path))
    elif isinstance(value, list):
        for child in value[:3]:
            keys.update(recursive_keys(child, prefix + "[]"))
    return keys


def make_fig56() -> Path:
    out = OUT_ROOT / "p123-fig-5-6-lyx-20260926"
    result_dir = ROOT / "results/a/p123-fig-5-6-lyx-20260926"
    # The first export was published without a suffix; accept both names while
    # keeping the exact bytes and their hashes in the manifest.
    bounds_path = next(
        (result_dir / name for name in ("global-bounds.json", "global-bounds") if (result_dir / name).is_file()),
        None,
    )
    if bounds_path is None:
        raise FileNotFoundError("global-bounds(.json) source is missing")
    upper_path = result_dir / "completed-summary.verified.json"
    proof_path = ROOT / "docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md"
    bounds = load_json(bounds_path)
    upper = load_json(upper_path)
    proof = proof_path.read_text(encoding="utf-8")
    lower_rows = {}
    for graph in bounds["records"]:
        case = Path(graph["graph_file"]).stem.replace("case_", "")
        entries = graph["by_core_count"]
        if not isinstance(entries, list):
            raise ValueError(f"{case}: by_core_count must be a list in the pinned certificate")
        for entry in entries:
            lower_rows[(case, int(entry["cores"]))] = (int(entry["makespan_lower_bound_cycles"]), graph)
    upper_rows = {(str(row["case"]), int(row["cores"])): row for row in upper["rows"]}
    expected = {(f"{case:03d}", core) for case in range(1, 101) for core in range(1, 6)}
    if set(lower_rows) != expected or set(upper_rows) != expected:
        raise ValueError("fixed lower/upper inputs must each cover exactly 100x5 cells")
    if upper.get("status") != "completed" or upper.get("accepted_cells") != 500 or upper.get("in_flight"):
        raise ValueError("upper-bound run receipt is not complete")
    rows = []
    for key in sorted(expected):
        lower, graph = lower_rows[key]
        upper_row = upper_rows[key]
        if graph["graph_sha256"] != upper_row["graph_sha256"]:
            raise ValueError(f"graph identity mismatch for {key}")
        if upper_row.get("status") != "accepted" or upper_row.get("solver_process", {}).get("status") != "ok" or upper_row.get("e0_process", {}).get("status") != "ok":
            raise ValueError(f"unaccepted upper result for {key}")
        value = int(upper_row["official"]["makespan"])
        if lower <= 0 or lower > value:
            raise ValueError(f"invalid lower-bound pairing for {key}: L={lower}, U={value}")
        certified = bool(
            graph.get("supported")
            and graph.get("precedence_supported")
            and not graph.get("multiple_eligible_producer_tensor_ids")
        )
        if not certified:
            raise ValueError(f"certificate applicability guard failed for {key}")
        rows.append(
            {
                "case": key[0],
                "cores": key[1],
                "upper": value,
                "lower": lower,
                "certified": 1,
                "domain": graph.get("precedence_domain", "global"),
                "gap": value / lower - 1.0,
            }
        )
    ecdf_rows = []
    summary_rows = []
    for cores in range(1, 6):
        values = sorted(r["gap"] for r in rows if r["cores"] == cores and r["certified"])
        within = sum(
            20 * (r["upper"] - r["lower"]) <= r["lower"]
            for r in rows
            if r["cores"] == cores and r["certified"]
        )
        for index, gap in enumerate(values, 1):
            ecdf_rows.append({"cores": cores, "gap": f"{gap:.17g}", "cdf": f"{index / len(values):.17g}"})
        summary_rows.append({"cores": cores, "valid": len(values), "uncertified": sum(not r["certified"] for r in rows if r["cores"] == cores), "within_5pct": within})
    if (
        "compute-only" not in proof
        or "precedence" not in proof
        or "optimality status is unresolved" not in proof
        or "not an observed error" not in proof
    ):
        raise ValueError("proof-scope source does not contain required bound semantics")
    setup_style()
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    palette = [PALETTE["blue"], PALETTE["green"], PALETTE["orange"], PALETTE["red"], PALETTE["purple"]]
    for cores, color in zip(range(1, 6), palette):
        vals = np.sort(np.array([r["gap"] for r in rows if r["cores"] == cores and r["certified"]], dtype=float))
        y = np.arange(1, len(vals) + 1) / len(vals)
        ax.step(vals, y, where="post", color=color, linewidth=2.0, label=f"{cores} core (n={len(vals)})")
    ax.axvline(0.05, color=PALETTE["ink"], linestyle=(0, (4, 3)), linewidth=1.2, label="5% gap threshold")
    ax.set_xlabel("Relative distance to certified global lower bound, U/L - 1")
    ax.set_ylabel("Empirical cumulative fraction")
    ax.set_title("Figure 5-6 | Global lower-bound gap distribution", loc="left", fontweight="bold")
    ax.set_xlim(left=0)
    ax.set_ylim(0, 1.02)
    ax.grid(True, color=PALETTE["grid"], linewidth=0.6)
    ax.legend(ncol=2, frameon=False)
    fig.tight_layout()
    paths = save_figure(fig, out, "fig56_p2_global_bound_gap")
    rows_path, ecdf_path, summary_path = out / "bounds.csv", out / "ecdf.csv", out / "summary.csv"
    field_audit_path = out / "field_audit.json"
    write_csv(rows_path, rows, ["case", "cores", "upper", "lower", "certified", "domain", "gap"])
    write_csv(ecdf_path, ecdf_rows, ["cores", "gap", "cdf"])
    write_csv(summary_path, summary_rows, ["cores", "valid", "uncertified", "within_5pct"])
    field_audit_path.write_text(
        json.dumps(
            {
                "status": "complete",
                "bounds_source": str(bounds_path.relative_to(ROOT)).replace("\\", "/"),
                "upper_source": str(upper_path.relative_to(ROOT)).replace("\\", "/"),
                "bounds_sha256": sha256_file(bounds_path),
                "upper_sha256": sha256_file(upper_path),
                "expected_cells": 500,
                "bounds_cells": len(lower_rows),
                "upper_cells": len(upper_rows),
                "graph_sha_matches": len(rows),
                "accepted_upper_cells": sum(1 for row in upper_rows.values() if row.get("status") == "accepted"),
                "certified_cells": sum(row["certified"] for row in rows),
                "missing_or_failed_cells": 0,
                "bound_semantics": "compute-only necessary lower bound; not an optimality proof",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = base_manifest(
        "fig-5-6",
        "P2 global lower-bound gap",
        out,
        "ready_for_human_review",
        100,
        [bounds_path, upper_path, proof_path],
        [
            "L_global is a certified compute-only necessary lower bound; L<U does not prove non-optimality or an achievable improvement.",
            "All 500 official upper-bound cells are accepted; this figure preserves the full local run's source and solver identities.",
            "No solver, evaluator, or benchmark calls are made by this plotting command.",
            "SVG/PDF were generated but not opened in a desktop reader in this session.",
        ],
    )
    manifest["source"].update(
        {
            "bounds_scope": bounds.get("scope"),
            "bounds_proof_document": bounds.get("proof_document"),
            "official_source_sha256": bounds.get("official_source_sha256"),
            "certificate_source_sha256": bounds.get("certificate_source_sha256"),
            "runner_commit": upper.get("runner_commit"),
            "solver_commit": upper.get("solver_commit"),
            "archive_source_reference": upper.get("_archive_provenance", {}).get("source_reference"),
            "cells": 500,
            "run_id": upper.get("_archive_provenance", {}).get("source_reference", "unknown"),
        }
    )
    manifest["environment"]["command"] = "python plot_figures.py --figure 5-6"
    manifest["outputs"].update({p.name: sha256_file(p) for p in paths + [rows_path, ecdf_path, summary_path]})
    finish_package(
        out,
        manifest,
        "Figure 5-6. Empirical distribution of U/L_global - 1, where U is the independently accepted official Makespan and L_global is a compute-only necessary lower bound. The gap is a conservative upper bound on the submitted plan's relative distance from the bound; it is neither an observed error nor a guaranteed achievable improvement, and L<U is not an optimality proof.",
        "# Figure 5-6 delivery\n\nThis package joins the pinned global-bound certificate to the accepted 500-cell official result by case, core count, and graph SHA-256. The certificate is compute-only and necessary; it does not include an exact optimality proof.\n\n- Source certificate SHA-256: `fe25f7b7737dbd3d841284bc5939242982613f64e0cffa9bd3d25df1f4a0c96b`\n- Source accepted summary SHA-256: `083c3f5b603cb61dd8b132718b6437b35c7706ff3aa165bdcdd490617547a2f2`\n- Solver commit: `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`\n- Reproduce: `python figures/a/p123-fig-5-6-lyx-20260926/plot_figures.py --figure 5-6`\n- Outputs: `fig56_p2_global_bound_gap.png`, `.svg`, `.pdf`, `bounds.csv`, `ecdf.csv`, `summary.csv`\n- Budget: read-only parsing and plotting; no new solver or evaluator calls.\n",
        "# Figure 5-6 self-check\n\n- [x] 100 graph records x 5 cores = 500 certificate cells.\n- [x] 500 accepted official upper-bound cells; no in-flight cells.\n- [x] Graph SHA-256 matched for every case/core pair.\n- [x] Certificate applicability guards passed for every cell.\n- [x] ECDF recomputed from full-precision U/L - 1 values.\n- [x] 5% counts use the exact integer inequality `20*(U-L) <= L`.\n- [x] Missing/failed values would be excluded as NA; none occurred in this fixed source.\n- [ ] Desktop SVG/PDF inspection: not performed.\n- [ ] yuanzhifang scientific acceptance: pending.\n",
        [rows_path, ecdf_path, summary_path, field_audit_path],
    )
    audit_files = paths + [
        rows_path,
        ecdf_path,
        summary_path,
        out / "caption.md",
        out / "README.md",
        out / "self-check.md",
        out / "plot_figures.py",
        out / "manifest.json",
        field_audit_path,
    ]
    audit = {
        "schema": "figure-auto-review-v1",
        "figure_id": "fig-5-6",
        "primary": "fig56_p2_global_bound_gap.svg",
        "files": [
            {
                "name": path.name,
                "role": "svg" if path.suffix == ".svg" else "png" if path.suffix == ".png" else "pdf" if path.suffix == ".pdf" else "source" if path.name == "plot_figures.py" else "input" if path.suffix == ".csv" else "notes",
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
            for path in audit_files
        ],
        "command": "python figures/a/p123-fig-5-6-lyx-20260926/plot_figures.py --figure 5-6",
        "sources": [
            {
                "path": "results/a/q2-nikolastarx/goal-20260924/global-bounds.json",
                "commit": "1c00079aadbd071de62db17686d5ba3fed1da0f2",
                "sha256": sha256_file(bounds_path),
            },
            {
                "path": "results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json",
                "commit": "1c00079aadbd071de62db17686d5ba3fed1da0f2",
                "sha256": sha256_file(upper_path),
            },
            {
                "path": "docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md",
                "commit": "1c00079aadbd071de62db17686d5ba3fed1da0f2",
                "sha256": sha256_file(proof_path),
            },
        ],
        "units": {"makespan": "cycles", "wall": "s", "bytes": "B"},
        "panels": [{"id": "ecdf", "title": "Global lower-bound gap ECDF"}],
        "tables": {"metrics": "bounds.csv", "ecdf": "ecdf.csv", "summary": "summary.csv"},
        "coverage": {"cases": 100, "cores": [1, 2, 3, 4, 5], "cells": 500},
        "visual_check": {"png_opened": True, "svg_opened": False, "pdf_opened": False, "paper_width_preview": False},
        "status": "submitted_for_review",
        "notes": [
            "L_global is a compute-only necessary lower bound, not an optimality proof.",
            "ECDF uses full-precision U/L - 1 and preserves the full tail.",
            "audit.json is excluded from manifest.outputs to avoid self-reference.",
        ],
    }
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def make_all(selected: set[str] | None = None) -> list[Path]:
    builders = {
        "4-4": lambda: ROOT / "figures/a/p123-fig-4-4-lyx-20260926",
        "5-3": make_fig53,
        "6-3": make_fig63,
        "6-4": make_fig64,
        "4-5": make_fig45,
        "5-5": lambda: make_efficiency_figure("P2", "fig-5-5", "5-5", "P2 quality, solver cost and tail latency"),
        "5-6": make_fig56,
        "6-7": make_fig67_forest,
    }
    outputs = []
    for key, builder in builders.items():
        if selected and key not in selected:
            continue
        outputs.append(builder())
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", action="append", help="figure number(s), e.g. 5-3")
    args = parser.parse_args()
    selected = set(args.figure or [])
    setup_style()
    outputs = make_all(selected or None)
    print(json.dumps({"outputs": [str(path) for path in outputs]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
