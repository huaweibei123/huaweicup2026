#!/usr/bin/env python3
"""Replot the frozen-v7 100-graph dataset without changing any source value."""
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt, font_manager
from PIL import Image

HERE = Path(__file__).resolve().parent
DATA = HERE / "dataset-v7.json.gz"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    records = json.loads(gzip.decompress(DATA.read_bytes()))
    assert len(records) == 100
    assert len({row["case_id"] for row in records}) == 100
    for row in records:
        assert row["ops"] > 0 and row["tensor_bytes"] > 0
        assert row["matrix_cycles"] >= 0 and row["vector_cycles"] >= 0
    ratios = sorted(row["matrix_cycles"] /
                    max(1, row["matrix_cycles"] + row["vector_cycles"])
                    for row in records)
    assert 0 <= ratios[0] <= ratios[-1] <= 1

    fonts = HERE.parents[2] / "paper/template-2026/fonts"
    for name in ("SimSun.ttf", "Times.TTF", "Timesbd.TTF"):
        if (fonts / name).exists():
            font_manager.fontManager.addfont(fonts / name)
    plt.rcParams.update({
        "font.family": ["Times New Roman", "SimSun", "DejaVu Serif"],
        "font.size": 10, "axes.labelsize": 10,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "axes.unicode_minus": False, "pdf.fonttype": 42, "svg.fonttype": "none",
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "savefig.facecolor": "white",
    })
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(160 / 25.4, 4.92))
    fig.subplots_adjust(left=.155, right=.965, bottom=.115, top=.925, hspace=.68)
    top.scatter([row["ops"] for row in records],
                [row["tensor_bytes"] / 2**20 for row in records],
                s=17, color="#345F86", alpha=.70, linewidths=0)
    top.set_xscale("log")
    top.set_yscale("log")
    top.set_title("（a）100 张原始图的规模与张量大小", loc="left", pad=6)
    top.set_xlabel("非 COPY 计算操作数量（对数刻度）")
    top.set_ylabel("张量大小总和 / MiB")
    top.grid(color="#E1E7EB", linewidth=.55, alpha=.85)
    top.set_axisbelow(True)

    ranks = range(1, 101)
    bottom.plot(ranks, ratios, color="#345F86", linewidth=1.75)
    bottom.fill_between(ranks, ratios, color="#E7EBEF")
    bottom.set_xlim(1, 100)
    bottom.set_ylim(0, 1)
    bottom.set_xticks([1, 25, 50, 75, 100])
    bottom.set_title("（b）矩阵类操作的标称时长占比", loc="left", pad=6)
    bottom.set_xlabel("按该占比从小到大排列的计算图序号")
    bottom.set_ylabel("矩阵标称时长占比")
    bottom.grid(axis="y", color="#E1E7EB", linewidth=.55)
    bottom.set_axisbelow(True)

    for ext in ("pdf", "svg", "png"):
        kwargs = {"dpi": 300} if ext == "png" else {}
        if ext == "pdf":
            kwargs["metadata"] = {"Creator": "Frozen-v7 source-bound figure",
                                  "CreationDate": None}
        if ext == "svg":
            kwargs["metadata"] = {"Date": None}
        fig.savefig(HERE / f"fig-dataset-v4.{ext}", **kwargs)
    svg = HERE / "fig-dataset-v4.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)
    with Image.open(HERE / "fig-dataset-v4.png") as preview:
        preview.save(HERE / "preview-160mm.png", dpi=(300, 300))
    record = {
        "source": "v7/source/data/figure-inputs/dataset.json.gz",
        "source_sha256": sha256(DATA),
        "number_of_graphs": 100,
        "matrix_fraction": "matrix_cycles/(matrix_cycles+vector_cycles), with max(1, denominator) as in frozen source",
        "sorted_min": ratios[0], "sorted_max": ratios[-1],
        "values_changed": False,
    }
    (HERE / "source-record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Rendered 100-graph dataset; no solver/evaluator calls.")


if __name__ == "__main__":
    main()
