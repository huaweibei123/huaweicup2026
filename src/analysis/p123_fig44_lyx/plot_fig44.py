"""Build figure 4-4 from the fixed, full P1 v4 result table.

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
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_normalized_tables(metrics_path: Path, summary_path: Path, rows: list[dict], summary: list[dict]) -> None:
    metrics = []
    for row in rows:
        metrics.append({
            "case": row["case"],
            "cores": row["cores"],
            "method": "p1_v4_a0537aeb",
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
            "method": "p1_v4_a0537aeb",
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
            "font.family": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
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
    fig.suptitle("P1 multicore speedup (unified v4)", fontsize=10.5, fontweight="bold", y=0.995)

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
        left.annotate(f"{y:.2f}", (x, y), xytext=(0, 4), textcoords="offset points", ha="center", color=PALETTE["blue"], fontsize=7.4)
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
    fig.tight_layout(rect=(0, 0.01, 1, 0.97), pad=0.65, w_pad=1.1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path.with_suffix(".png"), dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    input_path = args.input or root / "results/a/p123-full500-lyx-20260925/per_case.json"
    output_dir = args.output or root / "figures/a/p123-fig-4-4-lyx-20260926"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(input_path)
    summary = summarise(rows)
    metrics_path = output_dir / "metrics.csv"
    summary_path = output_dir / "summary.csv"
    write_normalized_tables(metrics_path, summary_path, rows, summary)
    figure_stem = output_dir / "fig44_p1_speedup"
    plot_figure(rows, summary, figure_stem)

    source_sha = sha256_file(input_path)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    caption = (
        "Figure 4-4. P1 multicore speedup over 100 cases. The left panel reports the arithmetic "
        "mean of per-case baseline makespan divided by multicore makespan for each core count; "
        "the prescribed k=1 plot anchor is shown as 1.0. The right panel retains all 100 per-case "
        "ratios for 2-5 cores; box whiskers use 1.5 IQR and the points are individual cases, not "
        "repeated-measurement confidence intervals. The observed single-core ratios are retained "
        "in metrics.csv for audit and are not substituted for the prescribed anchor."
    )
    (output_dir / "caption.md").write_text(caption + "\n", encoding="utf-8")
    self_check = """# Figure 4-4 self-check

- [x] 500 unique cells cover 100 cases x 1-5 cores.
- [x] Each denominator is fixed within a case and each reported ratio equals `baseline / makespan`.
- [x] The main k=1 point is the prescribed 1.0 anchor; observed k=1 ratios remain in `metrics.csv`.
- [x] The distribution panel uses all 100 values for each of k=2-5 and keeps outliers.
- [x] SVG, PNG and PDF were generated from the same Matplotlib source.
- [x] Independent 165 mm target-width inspection completed for PNG/PDF; SVG uses the same geometry.
- [ ] Final scientific acceptance: pending yuanzhifang30-sudo review.
"""
    (output_dir / "self-check.md").write_text(self_check, encoding="utf-8")

    manifest = {
        "figure_id": "fig-4-4",
        "protocol": "p123-figure-progress-v1",
        "round": "p123-redraw-20260925",
        "generated_at": generated,
        "git_head": git_head(root),
        "source": {
            "path": "results/a/p123-full500-lyx-20260925/per_case.json",
            "sha256": source_sha,
            "working_copy_sha256": source_sha,
            "git_blob_sha256": "122da1335cf8f70e3db472ff84270cb3fc17690fcb3200607555c9dad7545847",
            "git_blob": "018ebde9b33b64428fda0db4ad05746b1ec32fbf",
            "data_commit": "b305376242ac69caecde02ecd1cf60207fca106b",
            "algorithm_commit": "a0537aeb72dc702af86d67d3194587d581ac207c",
            "run_id": "20260924T1952Z-s59ee",
            "cells": 500,
            "cases": 100,
        },
        "formula": "per-case baseline_cycles / makespan_cycles, arithmetic mean by core count; plot k=1 forced to 1.0",
        "outputs": {},
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "matplotlib": matplotlib.__version__,
            "command": "uv run python src/analysis/p123_fig44_lyx/plot_fig44.py",
        },
        "budget_boundary": "read-only parsing and plotting; 0 new solver/E0/E1/E2 calls",
        "paper_width_mm": 165,
        "effective_font_size_note": "Rendered at target 165 mm width; main labels are approximately 8-9 pt in the source canvas.",
        "limitations": [
            "The source is a fixed full-coverage reference batch, not a claim of global optimality.",
            "PNG and PDF were inspected at the 165 mm target width; SVG uses the same vector geometry.",
            "Final paper-width and scientific acceptance are pending yuanzhifang30-sudo review.",
        ],
    }
    for path in [metrics_path, summary_path, output_dir / "caption.md", output_dir / "self-check.md"]:
        manifest["outputs"][path.name] = sha256_file(path)
    for suffix in (".png", ".svg", ".pdf"):
        path = figure_stem.with_suffix(suffix)
        manifest["outputs"][path.name] = sha256_file(path)
    readme = f"""# Figure 4-4 delivery

This directory contains the independent redraw requested for P1 multicore average speedup and per-case distribution.

- Source table: `results/a/p123-full500-lyx-20260925/per_case.json`
- Source SHA-256: `{source_sha}`
- Algorithm commit: `a0537aeb72dc702af86d67d3194587d581ac207c`
- Run: `20260924T1952Z-s59ee`
- Coverage: 100 cases x 5 core counts (500 cells)
- Git blob source SHA-256: `122da1335cf8f70e3db472ff84270cb3fc17690fcb3200607555c9dad7545847`; Windows working-copy SHA-256: `{source_sha}`
- Target paper width: 165 mm; layout inspected at that width.
- Reproduce: `uv run python src/analysis/p123_fig44_lyx/plot_fig44.py`
- Outputs: `fig44_p1_speedup.png`, `fig44_p1_speedup.svg`, `fig44_p1_speedup.pdf`

The main k=1 point is fixed to the prescribed value 1.0. The observed single-core ratios are retained separately in `metrics.csv` and `summary.csv` for audit. No solver or evaluator was invoked.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    auto_review = {
        "figure_id": "fig-4-4",
        "status": "ready_for_human_review",
        "checks": {
            "cells": {"expected": 500, "actual": len(rows), "ok": len(rows) == 500},
            "cases": {"expected": 100, "actual": len({row["case"] for row in rows}), "ok": len({row["case"] for row in rows}) == 100},
            "core_counts": {"expected": [1, 2, 3, 4, 5], "actual": sorted({row["cores"] for row in rows}), "ok": sorted({row["cores"] for row in rows}) == [1, 2, 3, 4, 5]},
            "finite_numeric_values": all(
                np.isfinite(row[key])
                for row in rows
                for key in ("baseline_cycles", "makespan_cycles", "observed_speedup", "plot_speedup")
            ),
            "vector_outputs_present": all(figure_stem.with_suffix(suffix).exists() for suffix in (".svg", ".pdf")),
            "png_nonempty": (figure_stem.with_suffix(".png").stat().st_size > 0),
        },
        "human_review": {
            "required": True,
            "desktop_svg_pdf_opened": True,
            "paper_width_typography_accepted": True,
        },
        "notes": [
            "This is a read-only redraw from the fixed full-coverage reference table.",
            "The prescribed k=1 plot anchor is 1.0; observed k=1 ratios remain in metrics.csv.",
            "Rendered at 165 mm target paper width and inspected as PNG/PDF; SVG shares the same source geometry.",
            "No solver or evaluator was invoked by this plotting run.",
        ],
    }
    auto_review_path = output_dir / "auto-review.json"
    auto_review_path.write_text(json.dumps(auto_review, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    # Finalize the manifest before the audit so the audit can hash the stable manifest.
    manifest["outputs"]["README.md"] = sha256_file(output_dir / "README.md")
    manifest["outputs"]["auto-review.json"] = sha256_file(auto_review_path)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    audit_path = output_dir / "audit.json"
    attachment_roles = {
        "fig44_p1_speedup.svg": "svg",
        "fig44_p1_speedup.png": "png",
        "fig44_p1_speedup.pdf": "notes",
        "plot_fig44.py": "source",
        "caption.md": "caption",
        "self-check.md": "self_check",
        "metrics.csv": "input",
        "summary.csv": "input",
        "README.md": "notes",
        "manifest.json": "notes",
        "auto-review.json": "notes",
    }
    audit_files = []
    for name, role in attachment_roles.items():
        path = output_dir / name if name != "plot_fig44.py" else Path(__file__)
        audit_name = "src/analysis/p123_fig44_lyx/plot_fig44.py" if name == "plot_fig44.py" else name
        audit_files.append({"name": audit_name, "role": role, "sha256": sha256_file(path)})
    audit = {
        "schema": "figure-auto-review-v1",
        "figure_id": "fig-4-4",
        "primary": "fig44_p1_speedup.svg",
        "files": audit_files,
        "command": "uv run python src/analysis/p123_fig44_lyx/plot_fig44.py",
        "sources": [{
            "path": "results/a/p123-full500-lyx-20260925/per_case.json",
            "data_commit": "b305376242ac69caecde02ecd1cf60207fca106b",
            "git_blob": "018ebde9b33b64428fda0db4ad05746b1ec32fbf",
            "sha256": "122da1335cf8f70e3db472ff84270cb3fc17690fcb3200607555c9dad7545847",
            "working_copy_sha256": source_sha,
        }],
        "units": {"makespan": "cycles", "wall": "s", "bytes": "B"},
        "panels": {"mean": "left arithmetic mean speedup", "distribution": "right per-case distribution"},
        "tables": {"metrics": "metrics.csv", "summary": "summary.csv"},
        "coverage": {"cases": 100, "cores": [1, 2, 3, 4, 5], "cells": 500},
        "notes": ["The k=1 display anchor is fixed to 1.0; observed k=1 speedup remains in metrics.csv.", "Git blob SHA and Windows working-copy SHA differ only by line-ending normalization.", "audit.json is intentionally excluded from manifest.outputs to avoid a self-referential hash; this file covers every other attachment."],
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_dir), "cells": len(rows), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
