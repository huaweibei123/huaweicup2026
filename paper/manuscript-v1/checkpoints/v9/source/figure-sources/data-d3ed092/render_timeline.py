"""Split Fang's fixed same-plan timeline into full and close-up vector figures."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
PIPES = ["PIPE_MTE2", "PIPE_M", "PIPE_V", "PIPE_MTE3"]
COLORS = {"PIPE_MTE2": "#23759b", "PIPE_M": "#74519a",
          "PIPE_V": "#d17929", "PIPE_MTE3": "#56a3b5"}


def load() -> list[dict[str, str]]:
    path = HERE / "inputs" / "fig-6-6" / "aligned_ops.csv"
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    entry = next(x for x in manifest["sources"] if x["source_path"].endswith("fig-6-6/aligned_ops.csv"))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    with path.open(encoding="utf-8", newline="") as handle:
        data = list(csv.DictReader(handle))
    assert len(data) == 8881
    assert all(int(row["source_core_id"]) == int(row["core"])-1 for row in data)
    assert {int(row["core"]) for row in data} == {1, 2, 3}
    return data


def axes_style(ax: plt.Axes, keys: list[tuple[int, str]]) -> None:
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([f"Core {core-1} {pipe[5:]}" for core, pipe in keys], fontsize=7.5)
    ax.set_ylim(len(keys)-.5, -.5)
    ax.tick_params(axis="x", labelsize=7.5)
    ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#ddd", lw=.45)
    ax.set_axisbelow(True)


def save(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf")
    plt.close(fig)


def full(data: list[dict[str, str]]) -> None:
    fig = plt.figure(figsize=(6.5, 5.8))
    axes = [fig.add_axes([.16, y, .81, .28]) for y in (.58, .15)]
    keys = [(core, pipe) for core in (1, 2, 3) for pipe in PIPES]
    for ax, variant, end in zip(axes, ("p2", "p3"), (2140720, 2140863)):
        for index, (core, pipe) in enumerate(keys):
            subset = [row for row in data if int(row["core"]) == core and row["pipe"] == pipe]
            intervals = [(int(row[f"{variant}_start"]),
                          int(row[f"{variant}_end"])-int(row[f"{variant}_start"])) for row in subset]
            ax.broken_barh(intervals, (index-.36, .72), facecolors=COLORS[pipe], linewidth=0)
        for index in (3.5, 7.5):
            ax.axhline(index, color="#ccc", lw=.5)
        ax.axvline(end, ls=":", color="#aa3333", lw=.9)
        ax.set_xlim(0, 2180000)
        axes_style(ax, keys)
    fig.text(.16, .96, "(a) 无 L2 缓存：2,140,720 时钟周期", fontsize=9, weight="bold")
    fig.legend([Patch(color=COLORS[p]) for p in PIPES],
               ["MTE2 搬入", "M 矩阵乘", "V 向量计算", "MTE3 搬出"],
               loc="upper left", bbox_to_anchor=(.16, .94), ncol=4,
               frameon=False, fontsize=7.5, handlelength=1, columnspacing=1)
    fig.text(.16, .53, "(b) 只读缓存：2,140,863 时钟周期", fontsize=9, weight="bold")
    fig.text(.5, .055, "绝对时间（时钟周期）", ha="center", fontsize=8)
    save(fig, "cache-counterexample-full")


def zoom(data: list[dict[str, str]]) -> None:
    fig = plt.figure(figsize=(6.5, 5.5))
    axes = [fig.add_axes([.16, y, .81, .27]) for y in (.59, .16)]
    windows = [(3, (4900, 7000)), (1, (443050, 443250))]
    for ax, (core, window) in zip(axes, windows):
        keys = [(core, pipe) for pipe in PIPES]
        for index, (_, pipe) in enumerate(keys):
            for row in data:
                if int(row["core"]) != core or row["pipe"] != pipe:
                    continue
                for variant, offset, color in (("p2", -.38, "#77838e"),
                                               ("p3", .04, "#db812d")):
                    start, end = int(row[f"{variant}_start"]), int(row[f"{variant}_end"])
                    if end <= window[0] or start >= window[1]:
                        continue
                    if variant == "p3" and row["op_id"] == "1000004905":
                        color = "#25925d"
                    ax.broken_barh([(start, end-start)], (index+offset, .34),
                                   facecolors=color, linewidth=.25, edgecolors="white")
        ax.set_xlim(*window)
        axes_style(ax, keys)
    fig.text(.16, .96, "(a) Core 2：4,900–7,000 时钟周期", fontsize=9, weight="bold")
    fig.legend([Patch(color="#77838e"), Patch(color="#db812d"), Patch(color="#25925d")],
               ["无 L2 缓存", "只读缓存", "所标记的命中操作"],
               loc="upper left", bbox_to_anchor=(.16, .94), ncol=3,
               frameon=False, fontsize=7.5, handlelength=1, columnspacing=1)
    axes[0].annotate("操作 1000004905", xy=(4973, .2), xytext=(5180, -.2),
                     fontsize=7, color="#156943",
                     arrowprops=dict(arrowstyle="->", color="#156943", lw=.7))
    fig.text(.16, .53, "(b) Core 0：443,050–443,250 时钟周期", fontsize=9, weight="bold")
    fig.text(.5, .055, "绝对时间（时钟周期）", ha="center", fontsize=8)
    save(fig, "cache-counterexample-zoom")


def main() -> None:
    plt.rcParams.update({"font.family": "PingFang SC", "font.size": 8,
                         "axes.unicode_minus": False, "svg.fonttype": "none",
                         "savefig.facecolor": "white"})
    data = load()
    full(data)
    zoom(data)


if __name__ == "__main__":
    main()
