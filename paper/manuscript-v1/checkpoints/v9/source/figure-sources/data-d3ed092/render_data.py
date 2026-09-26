"""Replot fixed Fang data tables with short chart labels and no baked-in footnotes.

Only reads the pinned CSV copies in inputs/. It never calls a solver or evaluator.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
COLORS = ["#286a96", "#b34e32", "#33846c", "#84559b", "#866323"]
MARKERS = ["o", "s", "^", "D", "x"]
STYLES = ["-", "--", "-.", ":", (0, (5, 1, 1, 1))]


def rows(figure: str, filename: str) -> list[dict[str, str]]:
    path = HERE / "inputs" / figure / filename
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    entry = next(e for e in manifest["sources"] if Path(e["local_path"]).parts[-2:] == (figure, filename))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], filename
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def style() -> None:
    plt.rcParams.update({
        "font.family": "PingFang SC",
        "font.size": 9,
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    })


def save(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf")
    plt.close(fig)


def quality_cost(figure: str, stem: str) -> None:
    table = rows(figure, "metrics.csv" if figure == "fig-5-5" else "p3_quality_cost_rows.csv")
    assert len(table) == 500
    assert Counter(int(r["cores"]) for r in table) == {k: 100 for k in range(1, 6)}
    fig, axes = plt.subplots(2, 1, figsize=(6.5, 6.6))
    fig.subplots_adjust(left=.15, right=.97, top=.88, bottom=.10, hspace=.56)
    for core in range(1, 6):
        selected = [r for r in table if int(r["cores"]) == core]
        wall = np.array([float(r["solver_wall"]) for r in selected])
        makespan = np.array([int(r["makespan"]) for r in selected])
        axes[0].scatter(wall, makespan, color=COLORS[core-1], marker=MARKERS[core-1],
                        s=20, alpha=.6, linewidths=.5, label=f"{core} 核")
        ordered = np.sort(wall)
        axes[1].step(ordered, np.arange(1, 101)/100, where="post", color=COLORS[core-1],
                     ls=STYLES[core-1], lw=1.4)
        axes[1].plot(ordered[::10], np.arange(1, 101)[::10]/100, ls="none",
                     marker=MARKERS[core-1], ms=3, color=COLORS[core-1])
    axes[0].set(xscale="log", yscale="log",
                xlabel="求解程序端到端墙钟时间（秒，对数刻度）",
                ylabel="官方模拟总完成时间（时钟周期，对数刻度）")
    axes[0].set_title("(a) 方案总完成时间与求解耗时", loc="left", fontsize=10, weight="bold")
    axes[1].set(xscale="log", xlabel="求解程序端到端墙钟时间（秒，对数刻度）",
                ylabel="经验累积比例", ylim=(0, 1.03),
                yticks=[0, .25, .5, .75, 1], yticklabels=["0%", "25%", "50%", "75%", "100%"])
    axes[1].set_title("(b) 求解耗时分布（每组 100 张计算图）", loc="left", fontsize=10, weight="bold")
    for ax in axes:
        ax.grid(axis="y", which="major", color="#ddd", lw=.6)
        ax.xaxis.set_minor_locator(NullLocator())
        ax.yaxis.set_minor_locator(NullLocator())
        ax.tick_params(labelsize=8)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center",
               bbox_to_anchor=(.55, .97), ncol=5, frameon=False, fontsize=8.5)
    save(fig, stem)


def bound_distribution() -> None:
    table = rows("fig-5-6", "ecdf-normalized.csv")
    assert len(table) == 500
    assert Counter(int(r["cores"]) for r in table) == {k: 100 for k in range(1, 6)}
    fig, ax = plt.subplots(figsize=(6.5, 3.9))
    fig.subplots_adjust(left=.12, right=.98, top=.96, bottom=.20)
    for core, color in zip(range(1, 6), ["#2574A9", "#4C956C", "#E09F3E", "#B6465F", "#7057A3"]):
        selected = [r for r in table if int(r["cores"]) == core]
        ax.step([float(r["gap"]) for r in selected], [float(r["cdf"]) for r in selected],
                where="post", color=color, linewidth=1.7, label=f"{core} 核（n=100）")
    ax.axvline(.05, color="#25313B", linestyle=(0, (4, 3)), linewidth=1.1, label="5% 参考线")
    ax.set(xlabel="相对理论全局下界间隙 U/L − 1", ylabel="经验累积比例", xlim=(0, None), ylim=(0, 1.02))
    ax.grid(True, color="#D8E1E7", linewidth=.6)
    ax.legend(ncol=2, frameon=False, fontsize=8, loc="lower right")
    ax.tick_params(labelsize=8)
    save(fig, "p2-bound-distribution")


def cache_comparison() -> None:
    table = rows("fig-6-3", "summary.csv")
    assert len(table) == 5 and [int(r["cores"]) for r in table] == list(range(1, 6))
    assert all(int(r["n"]) == 100 for r in table)
    fig, ax = plt.subplots(figsize=(6.5, 3.75))
    fig.subplots_adjust(left=.13, right=.97, top=.95, bottom=.19)
    x = [int(r["cores"]) for r in table]
    ax.plot(x, [float(r["mean_no_cache_speedup"]) for r in table], "--s",
            color="#b34e32", markerfacecolor="white", lw=1.5, ms=4, label="同计划无 L2 缓存")
    ax.plot(x, [float(r["mean_cache_speedup"]) for r in table], "-o",
            color="#214b9a", lw=1.7, ms=4, label="同计划只读缓存")
    ax.set(xlabel="NPU 核心数", ylabel="平均加速比（倍）", xticks=x, xlim=(.85, 5.15))
    ax.grid(axis="y", color="#e6eaf0", lw=.6)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    save(fig, "p3-cache-comparison")


def cache_gain() -> None:
    table = rows("fig-6-4", "pair_metrics.csv")
    summary = rows("fig-6-4", "per_core_summary.csv")
    negatives = rows("fig-6-4", "negative_cases.csv")
    assert len(table) == 500 and len(summary) == 5
    assert Counter(int(r["cores"]) for r in table) == {k: 100 for k in range(1, 6)}
    assert len(negatives) == sum(r["category"] == "negative" for r in table)
    means = {int(r["cores"]): float(r["mean_cache_gain"]) for r in summary}
    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in table:
        gain = float(row["cache_gain"])
        assert abs(gain-int(row["no_l2_makespan"])/int(row["cache_makespan"])) < 1e-12
        assert (row["category"] == "negative") == (gain < 1)
        groups[int(row["cores"])].append(row)
    fig = plt.figure(figsize=(6.5, 7.1))
    grid = fig.add_gridspec(3, 1, height_ratios=[.8, 1.1, 1.0], hspace=.56,
                           left=.12, right=.97, top=.96, bottom=.09)
    a, b, c = [fig.add_subplot(grid[i]) for i in range(3)]
    cores = range(1, 6)
    a.plot(list(cores), [means[k] for k in cores], color="#2E86AB", lw=1.4, marker="o", ms=5)
    for k in cores:
        a.annotate(f"{means[k]:.5f}", (k, means[k]), textcoords="offset points",
                   xytext=(0, 7), ha="center", fontsize=7)
    a.axhline(1, color="#7F8C8D", ls="--", lw=1)
    a.set(xlim=(.6, 5.6), xticks=list(cores), ylabel="平均缓存收益比")
    a.set_title("(a) 各核心数的平均收益比", loc="left", fontsize=9, weight="bold")
    rng = random.Random(20260927)
    for k in cores:
        grp = groups[k]
        values = [float(r["cache_gain"]) for r in grp]
        xs = [k+rng.uniform(-.16, .16) for _ in grp]
        b.scatter([x for x, r in zip(xs, grp) if r["category"] != "negative"],
                  [y for y, r in zip(values, grp) if r["category"] != "negative"],
                  s=9, color="#2E86AB", alpha=.55, linewidths=0)
        b.scatter([x for x, r in zip(xs, grp) if r["category"] == "negative"],
                  [y for y, r in zip(values, grp) if r["category"] == "negative"],
                  s=16, color="#C0392B", marker="v", alpha=.9, linewidths=0)
        b.boxplot([values], positions=[k], widths=.32, showfliers=False,
                  medianprops=dict(color="#2C3E50", lw=1),
                  boxprops=dict(color="#2C3E50", lw=.8),
                  whiskerprops=dict(color="#2C3E50", lw=.8),
                  capprops=dict(color="#2C3E50", lw=.8))
    b.axhline(1, color="#7F8C8D", ls="--", lw=1)
    b.set(xlim=(.6, 5.6), xticks=list(cores), ylabel="逐例缓存收益比")
    b.set_title("(b) 逐例收益比分布", loc="left", fontsize=9, weight="bold")
    b.legend(handles=[Line2D([0], [0], marker="v", ls="", color="#C0392B",
                             markersize=6, label="负收益")], frameon=False, fontsize=7.5)
    no_access = 0
    for row in table:
        gain = float(row["cache_gain"])
        if row["byte_hit_rate"]:
            x = float(row["byte_hit_rate"])
            c.scatter([x], [gain], s=9, color="#C0392B" if row["category"] == "negative" else "#2E86AB",
                      alpha=.5, linewidths=0)
        else:
            no_access += 1
            c.scatter([-.045], [gain], s=16, color="#BDC3C7", marker="s",
                      edgecolors="#2C3E50", linewidths=.5)
    c.axhline(1, color="#7F8C8D", ls="--", lw=1)
    c.axvline(0, color="#D5D8DC", lw=.6)
    c.set(xlim=(-.09, 1.02), xticks=[0, .2, .4, .6, .8, 1],
          xlabel="字节命中率", ylabel="逐例缓存收益比")
    c.set_title("(c) 字节命中率与逐例收益比", loc="left", fontsize=9, weight="bold")
    c.legend(handles=[Line2D([0], [0], marker="o", ls="", color="#2E86AB", markersize=5, label="非负收益"),
                      Line2D([0], [0], marker="v", ls="", color="#C0392B", markersize=5, label="负收益"),
                      Line2D([0], [0], marker="s", ls="", color="#BDC3C7", markersize=5,
                             label=f"无访问（{no_access} 例）")], frameon=False, fontsize=7, loc="upper right")
    for ax in (a, b, c):
        ax.tick_params(labelsize=8)
    save(fig, "p3-cache-gain")


def main() -> None:
    style()
    quality_cost("fig-5-5", "p2-quality-cost")
    bound_distribution()
    quality_cost("fig-6-7", "p3-quality-cost")
    cache_comparison()
    cache_gain()


if __name__ == "__main__":
    main()
