"""Render real P1/P2/P3 benchmark CSV; never import or run a solver.

Usage: python -B src/benchmarks/p123_plot.py --csv results/run/results.csv
       --output-dir figures/run
Every expected case (001..100) remains visible, including absent/failed cases.
The output directory must be new, so earlier figures/evidence are not replaced.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
from matplotlib import colors, font_manager, ft2font, pyplot as plt
import numpy as np


CASES = tuple(f"{number:03d}" for number in range(1, 101))
PROBLEMS = ("P1", "P2", "P3")
FIELDS = (
    "case", "problem", "cores", "algorithm", "status", "makespan_cycles",
    "singlecore_cycles", "multicore_speedup", "solver_wall_seconds",
    "e0_wall_seconds", "data_movement_bytes", "cache_hit_rate",
    "no_cache_makespan_cycles", "cache_speedup", "error", "source_commit",
    "result_path",
)
LABELS = {
    "multicore": ("多核加速比", "Multicore speedup"),
    "cache": ("同核同计划 Cache 收益", "Cache benefit: same plan and core count"),
    "extension": ("扩展指标", "extension metric"),
    "cores": ("核数", "Core count"),
    "case": ("用例", "Case"),
    "mean": ("逐用例加速比的算术平均", "Arithmetic mean of per-case speedups"),
    "count": ("有效 / 预期用例", "Valid / expected cases"),
    "missing": ("灰色 NA：缺失、未完成、失败或指标不可用", "Gray NA: absent, incomplete, failed, or unavailable metric"),
    "p3": ("P3 官方主对照为同核数无 Cache / Cache；多核图为扩展指标。",
           "P3 official comparison: no Cache / Cache at equal cores; multicore is an extension."),
    "formula": ("单核 Makespan / 多核 Makespan（周期比；不是程序墙钟提速）",
                "Single-core / multicore Makespan (cycle ratio, not solver wall-clock speedup)"),
    "cache_formula": ("同核同计划无 Cache Makespan / Cache Makespan（周期比）",
                      "Same-plan, same-core no-Cache Makespan / Cache Makespan (cycle ratio)"),
    "coverage": ("完整逐组计数见 mean_comparison.csv 与 summary_statistics.csv",
                 "Full group counts: mean_comparison.csv and summary_statistics.csv"),
    "baseline": ("通用基线", "generic baseline"),
    "valid_cells": ("有效比值 / 计划比值", "Valid / planned ratios"),
    "p1_method": ("默认 32 候选预算", "Default budget: 32 candidates"),
    "anchors": ("P1/P2 的 1 核点共用官方单核基准；本批实际求解为 2–5 核。",
                "P1/P2 core-1 points share the official baseline; actual solver runs cover cores 2–5."),
}


def configure_font():
    """Use an installed font whose character map covers all Chinese labels."""
    required = {ord(char) for pair in LABELS.values() for char in pair[0] if ord(char) > 127}
    names = {entry.name for entry in font_manager.fontManager.ttflist}
    preferred = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC",
                 "PingFang SC", "WenQuanYi Micro Hei", "SimSun", "Arial Unicode MS")
    for name in preferred:
        if name not in names:
            continue
        try:
            path = font_manager.findfont(name, fallback_to_default=False)
            if not required <= set(ft2font.FT2Font(path).get_charmap()):
                continue
        except (OSError, ValueError, RuntimeError):
            continue
        plt.rcParams["font.family"] = [name]
        return name, True
    plt.rcParams["font.family"] = ["DejaVu Sans"]
    return "DejaVu Sans", False


def finite(value, *, positive=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or (number <= 0 if positive else number < 0):
        return None
    return number


def read_rows(path, raw_bytes=None):
    rows = {}
    raw_bytes = path.read_bytes() if raw_bytes is None else raw_bytes
    with io.StringIO(raw_bytes.decode("utf-8-sig"), newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV lacks required columns: {sorted(missing)}")
        for line, row in enumerate(reader, 2):
            case = row["case"].strip()
            if case.isascii() and case.isdecimal():
                case = f"{int(case):03d}"
            problem = row["problem"].strip()
            try:
                core = int(row["cores"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"CSV line {line}: invalid core count") from error
            if case not in CASES or problem not in PROBLEMS or core not in range(1, 6):
                raise ValueError(f"CSV line {line}: expected case 001..100, P1/P2/P3, cores 1..5")
            key = (problem, case, core)
            if key in rows:
                raise ValueError(f"Duplicate cell {key}; select one algorithm/result per cell upstream")
            row.update(case=case, problem=problem, cores=core, status=row["status"].strip())
            rows[key] = row
    if not rows:
        raise ValueError("The input CSV contains no records")
    return rows


def metric_value(row, metric):
    return finite(row.get(metric), positive=True) if row and row["status"] == "ok" else None


def matrix(rows, problem, cores, metric):
    values = np.full((len(CASES), len(cores)), np.nan)
    for i, case in enumerate(CASES):
        for j, core in enumerate(cores):
            number = metric_value(rows.get((problem, case, core)), metric)
            if number is not None:
                values[i, j] = number
    return values


def scale(matrices):
    present = np.concatenate([value[np.isfinite(value)] for value in matrices])
    if not len(present):
        return colors.Normalize(1.0, 1.0), dict(vmin=None, vmax=None, valid_cells=0)
    lower, upper = min(1.0, float(present.min())), float(present.max())
    return colors.Normalize(lower, upper), dict(vmin=lower, vmax=upper, valid_cells=int(len(present)))


def save_figure(fig, output, name):
    for extension in ("pdf", "svg", "png"):
        fig.savefig(output / f"{name}.{extension}", dpi=250, facecolor="white")
    plt.close(fig)


def heatmap(values, cores, problem, norm, limits, output, text, *, cache=False, snapshot_label=""):
    title = f"{problem} | {text('cache' if cache else 'multicore')}"
    if problem == "P3" and not cache:
        title += f" ({text('extension')})"
    if problem == "P2":
        title += f" ({text('baseline')})"
    fig = plt.figure(figsize=(10.8, 14.2))
    grid = fig.add_gridspec(1, 2, left=.08, right=.86, bottom=.095, top=.915, wspace=.30)
    cmap = matplotlib.colormaps["YlGnBu"].copy()
    cmap.set_bad("#dedede")
    for half in range(2):
        ax = fig.add_subplot(grid[0, half])
        block = values[half * 50:(half + 1) * 50]
        image = ax.imshow(np.ma.masked_invalid(block), cmap=cmap, norm=norm,
                          aspect="auto", interpolation="nearest")
        ax.set_xticks(range(len(cores)), [str(core) for core in cores])
        ax.set_yticks(range(50), CASES[half * 50:(half + 1) * 50], fontsize=8)
        ax.xaxis.tick_top()
        ax.xaxis.set_label_position("top")
        ax.set_xlabel(text("cores"), fontsize=10, labelpad=9)
        ax.set_ylabel(text("case"), fontsize=10)
        ax.set_xticks(np.arange(-.5, len(cores), 1), minor=True)
        ax.set_yticks(np.arange(-.5, 50, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=.4)
        ax.tick_params(which="both", length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for (i, j), number in np.ndenumerate(block):
            if not np.isfinite(number):
                label, color = "NA", "#666666"
            else:
                rgb = cmap(norm(number))[:3]
                luminance = sum(component * weight for component, weight in zip(rgb, (.2126, .7152, .0722)))
                label = f"{number:.3f}" if cache else f"{number:.2f}"
                color = "white" if luminance < .44 else "#16252c"
            ax.text(j, i, label, ha="center", va="center", fontsize=8, color=color)
    # A uniform/all-missing grid has no varying scale; avoid colorbar expanding
    # the shared Normalize in place and changing later figures' color mapping.
    if limits["valid_cells"] and norm.vmin < norm.vmax:
        bar = fig.colorbar(image, cax=fig.add_axes((.89, .21, .018, .60)))
        bar.set_label(text("cache" if cache else "multicore"), fontsize=10)
        bar.ax.tick_params(labelsize=9)
    else:
        label = "NA" if not limits["valid_cells"] else f"{norm.vmin:.2f}"
        fig.text(.91, .50, label, ha="center", fontsize=11)
    fig.suptitle(title, fontsize=17, y=.979)
    coverage = f"{text('valid_cells')}: {int(np.isfinite(values).sum())}/{values.size}"
    if problem == "P1":
        coverage += " | " + text("p1_method")
    fig.text(.5, .954, coverage, ha="center", fontsize=9, color="#555555")
    if snapshot_label:
        fig.text(.5, .074, snapshot_label, ha="center", fontsize=8, color="#555555")
    fig.text(.5, .052, text("cache_formula" if cache else "formula"), ha="center", fontsize=9)
    fig.text(.5, .033, text("missing"), ha="center", fontsize=9, color="#555555")
    if problem == "P3":
        fig.text(.5, .014, text("p3"), ha="center", fontsize=8, color="#555555")
    save_figure(fig, output, "p3_cache_benefit" if cache else f"{problem.lower()}_multicore_speedup")


def summary(rows, problem, core, metric):
    group = [rows.get((problem, case, core)) for case in CASES]
    values = [value for row in group if (value := metric_value(row, metric)) is not None]
    missing_states = {"missing", "not_run", "unrun"}
    incomplete_states = {"incomplete", "running", "running_unconfirmed", "pending"}
    failed_states = {"error", "failed", "timeout", "cancelled", "fatal", "fatal_cleanup", "unsupported"}
    for row in group:
        if row is not None and row["status"] not in (
                missing_states | incomplete_states | failed_states | {"ok"}):
            raise ValueError(f"Unrecognized result status: {row['status']!r}")
    result = dict(problem=problem, cores=core, metric=metric, n=len(values), expected=len(CASES),
                  failed=sum(row is not None and row["status"] in failed_states for row in group),
                  missing=sum(row is None or row["status"] in missing_states for row in group),
                  incomplete=sum(row is not None and row["status"] in incomplete_states for row in group),
                  unavailable=sum(row is not None and row["status"] == "ok"
                                  and metric_value(row, metric) is None for row in group))
    assert sum(result[key] for key in ("n", "failed", "missing", "incomplete", "unavailable")) == len(CASES)
    result.update(mean=statistics.fmean(values) if values else None,
                  median=statistics.median(values) if values else None,
                  min=min(values) if values else None, max=max(values) if values else None)
    # Wall-clock measurements are summarized separately, never divided to
    # produce a Makespan speedup or pooled across incompatible units.
    for field in ("solver_wall_seconds", "e0_wall_seconds"):
        times = [value for row in group if row is not None and row["status"] == "ok"
                 and (value := finite(row.get(field))) is not None]
        result[f"{field}_n"] = len(times)
        for name, function in (("mean", statistics.fmean), ("median", statistics.median),
                               ("min", min), ("max", max)):
            result[f"{field}_{name}"] = function(times) if times else None
    return result


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def comparison(summaries, output, text, snapshot_label=""):
    groups = {(row["problem"], row["cores"]): row for row in summaries
              if row["metric"] == "multicore_speedup"}
    wide, markdown = [], ["# Mean per-case Makespan speedup", "",
        "Arithmetic mean of each valid case's singlecore_cycles / makespan_cycles; not a ratio of sums.",
        "P3 is an extension metric; its official primary comparison is same-core no Cache / Cache.",
        "NA values are excluded, and valid / expected counts are retained. Unequal coverage is not a paired comparison.",
        "P1/P2 core-1 points reuse the same official singlecore anchors, not separate solver executions; actual P1/P2 runs cover cores 2–5.",
        "", "| Cores | P1 mean (n/100) | P2 mean (n/100) | P3 extension mean (n/100) |",
        "| --- | --- | --- | --- |"]
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    styles = (("#147a6c", "o", "-"), ("#285f9b", "s", "--"), ("#765394", "^", "-."))
    for core in range(1, 6):
        row, cells = {"cores": core}, []
        for problem in PROBLEMS:
            entry = groups[problem, core]
            row.update({f"{problem}_{field}": entry[field] for field in
                        ("mean", "n", "expected", "failed", "missing", "incomplete", "unavailable")})
            cells.append(f"{entry['mean']:.3f} ({entry['n']}/100)" if entry["mean"] is not None else "NA (0/100)")
        wide.append(row)
        markdown.append(f"| {core} | " + " | ".join(cells) + " |")
    for index, (problem, (color, marker, line)) in enumerate(zip(PROBLEMS, styles)):
        values = [groups[problem, core]["mean"] for core in range(1, 6)]
        y = [np.nan if value is None else value for value in values]
        label = problem + (f" ({text('extension')})" if problem == "P3" else "")
        if problem == "P2":
            label += f" ({text('baseline')})"
        ax.plot(range(1, 6), y, color=color, marker=marker, linestyle=line, linewidth=1.8, label=label)
        for core, value in enumerate(y, 1):
            if math.isfinite(value):
                if core == 1 and problem == "P2":
                    continue  # The shared P1/P2 official anchor is labelled once.
                label = f"{groups[problem, core]['n']}/100"
                if core == 1 and problem == "P1":
                    label = "P1/P2: " + label
                ax.annotate(label, (core, value),
                            xytext=(0, 11 if problem == "P3" else -17), textcoords="offset points",
                            ha="center", color=color, fontsize=8)
    ax.axhline(1, color="#808080", linewidth=.8, linestyle=":")
    ax.set_xticks(range(1, 6))
    ax.set_xlabel(text("cores"))
    ax.set_ylabel(text("mean"))
    ax.set_title(text("mean"), fontsize=14, pad=14)
    upper = max([1.0] + [entry["mean"] for entry in groups.values() if entry["mean"] is not None])
    ax.set_ylim(0, upper * 1.24)  # Space for all three n/100 annotations.
    ax.grid(axis="y", color="#dddddd", linewidth=.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="best")
    fig.subplots_adjust(left=.10, right=.97, top=.87, bottom=.26)
    if snapshot_label:
        fig.text(.5, .145, snapshot_label, ha="center", fontsize=8, color="#555555")
    fig.text(.5, .095, text("formula"), ha="center", fontsize=9)
    fig.text(.5, .06, text("count") + " = n/100; " + text("coverage"), ha="center", fontsize=8)
    fig.text(.5, .025, text("p3"), ha="center", fontsize=8)
    fig.text(.5, .006, text("anchors"), ha="center", fontsize=7.5)
    save_figure(fig, output, "mean_multicore_comparison")
    write_csv(output / "mean_comparison.csv", wide)
    (output / "mean_comparison.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")


def matched_comparison(rows, output):
    """Supplementary comparison on one identical case set for all 15 groups."""
    common = [case for case in CASES if all(
        metric_value(rows.get((problem, case, core)), "multicore_speedup") is not None
        for problem in PROBLEMS for core in range(1, 6))]
    table = []
    for core in range(1, 6):
        row = dict(cores=core, common_n=len(common), expected=100)
        for problem in PROBLEMS:
            values = [metric_value(rows[problem, case, core], "multicore_speedup") for case in common]
            row[problem + "_mean"] = statistics.fmean(values) if values else None
        table.append(row)
    write_csv(output / "matched_mean_comparison.csv", table)
    return {"cases": common, "n": len(common), "expected": 100,
            "selection": "Identical subset with a valid multicore ratio for every P1/P2/P3 core count 1..5",
            "limitation": "Supplementary complete-case subset, not the full 100-case result; P3 remains an extension metric"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--snapshot-label", default="", help="Visible provenance/status caption for this snapshot")
    args = parser.parse_args()
    raw_csv = args.csv.read_bytes()
    rows = read_rows(args.csv, raw_csv)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "input_comparison.csv").write_bytes(raw_csv)
    plt.rcParams.update({"pdf.fonttype": 42, "svg.fonttype": "none", "axes.unicode_minus": False})
    font, chinese = configure_font()
    text = lambda name: LABELS[name][0 if chinese else 1]
    grids = [matrix(rows, problem, (2, 3, 4, 5), "multicore_speedup") for problem in PROBLEMS]
    norm, limits = scale(grids)
    for problem, values in zip(PROBLEMS, grids):
        heatmap(values, (2, 3, 4, 5), problem, norm, limits, args.output_dir, text,
                snapshot_label=args.snapshot_label)
    cache = matrix(rows, "P3", (1, 2, 3, 4, 5), "cache_speedup")
    cache_norm, cache_limits = scale([cache])
    heatmap(cache, (1, 2, 3, 4, 5), "P3", cache_norm, cache_limits, args.output_dir, text,
            cache=True, snapshot_label=args.snapshot_label)
    summaries = [summary(rows, problem, core, "multicore_speedup")
                 for problem in PROBLEMS for core in range(1, 6)]
    summaries += [summary(rows, "P3", core, "cache_speedup") for core in range(1, 6)]
    write_csv(args.output_dir / "summary_statistics.csv", summaries)
    comparison(summaries, args.output_dir, text, args.snapshot_label)
    matched = matched_comparison(rows, args.output_dir)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=Path(__file__).resolve().parents[2], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    metadata = dict(input_csv=args.csv.name, saved_input_csv="input_comparison.csv",
                    input_sha256=hashlib.sha256(raw_csv).hexdigest(),
                    plot_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    plot_checkout_head=commit, source_commits=sorted({row["source_commit"] for row in rows.values()}),
                    algorithms={problem: sorted({row["algorithm"] for row in rows.values()
                                                 if row["problem"] == problem}) for problem in PROBLEMS},
                    python=platform.python_version(), platform=platform.platform(),
                    matplotlib=matplotlib.__version__, numpy=np.__version__, font=font,
                    label_language="zh" if chinese else "en: no installed font covers Chinese labels",
                    command=["python", "src/benchmarks/p123_plot.py", "--csv", args.csv.name,
                             "--output-dir", args.output_dir.name],
                    expected_cases=list(CASES), multicore_shared_scale=limits, cache_separate_scale=cache_limits,
                    averaging="mean_i(singlecore_cycles_i / makespan_cycles_i), status=ok with positive finite ratio",
                    cache_metric="same-plan same-core no_cache_makespan_cycles / makespan_cycles, P3 only",
                    timing_units="seconds; solver and external E0 times are separate from simulated cycle ratios",
                    limitations=["P3 multicore speedup is an extension metric",
                                 "P1/P2 core-1 points are shared official anchors, not actual P1/P2 solver runs",
                                 "Coverage may differ across groups; inspect n/100 before comparison",
                                 "Ratios and same-plan provenance are supplied by the benchmark CSV producer",
                                 "Export completed; visual inspection by the caller is still required"],
                    summaries=summaries)
    metadata["matched_multicore_subset"] = matched
    metadata["snapshot_label"] = args.snapshot_label
    if args.snapshot_label:
        metadata["command"] += ["--snapshot-label", args.snapshot_label]
    (args.output_dir / "plot_summary.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "font": font,
                      "input_rows": len(rows), "summary_groups": len(summaries),
                      "figures": 5, "visual_inspection": "pending"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
