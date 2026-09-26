#!/usr/bin/env python3
"""Render the frozen-v7 P2 speedup-bound figure; no solver or evaluator calls."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt, font_manager
from PIL import Image


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v7-source", type=Path, required=True,
                        help="Frozen v7/source directory (read only)")
    args = parser.parse_args()
    source = args.v7_source.resolve()
    out = Path(__file__).resolve().parent
    audit_path = source / "data/figure-inputs/p2-audit.json.gz"
    summary_path = source / "data/summary.json"
    audit = json.loads(gzip.decompress(audit_path.read_bytes()))
    summary = json.loads(summary_path.read_bytes())
    cells = audit["core_comparison"]
    ks = list(range(1, 6))
    lower = [cells[str(k)]["new_mean_B_over_M"] for k in ks]
    upper = [cells[str(k)]["relaxation_ceiling_mean_B_over_LB"] for k in ks]
    for k, lo, hi in zip(ks, lower, upper):
        assert cells[str(k)]["n"] == summary["P2"]["cores"][str(k)]["count"] == 100
        assert abs(lo - summary["P2"]["cores"][str(k)]["mean_baseline_speedup"]) < 1e-12
        assert 0 < lo <= hi

    font_dir = source.parents[3] / "template-2026/fonts"
    for filename in ("SimSun.ttf", "Times.TTF", "Timesbd.TTF"):
        if (font_dir / filename).exists():
            font_manager.fontManager.addfont(font_dir / filename)
    plt.rcParams.update({
        "font.family": ["Times New Roman", "SimSun", "DejaVu Serif"],
        "font.size": 11, "axes.labelsize": 11, "xtick.labelsize": 10,
        "ytick.labelsize": 10, "legend.fontsize": 10,
        "axes.unicode_minus": False, "pdf.fonttype": 42, "svg.fonttype": "none",
        "axes.spines.top": False, "axes.spines.right": False,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })
    fig, ax = plt.subplots(figsize=(160 / 25.4, 3.65))
    fig.subplots_adjust(left=0.135, right=0.98, bottom=0.18, top=0.955)
    ax.fill_between(ks, lower, upper, color="#E7EBEF", zorder=1)
    ax.plot(ks, lower, "s-", color="#345F86", linewidth=1.8, markersize=5,
            label="当前方案 mean(B/U)", zorder=3)
    ax.plot(ks, upper, "o--", color="#52606D", linewidth=1.6, markersize=5,
            label="加速比上界 mean(B/L)", zorder=2)
    ax.set_xticks(ks)
    ax.set_xlim(0.85, 5.15)
    ax.set_ylim(0, 6.55)
    ax.set_xlabel("核心数 K")
    ax.set_ylabel("平均加速比（无量纲）")
    ax.grid(axis="y", color="#DDE3E8", linewidth=0.65)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, handlelength=2.7)
    for ext in ("pdf", "svg", "png"):
        kw = {"dpi": 300} if ext == "png" else {}
        if ext == "pdf":
            kw["metadata"] = {"Creator": "Frozen-v7 source-bound figure", "CreationDate": None}
        if ext == "svg":
            kw["metadata"] = {"Date": None}
        fig.savefig(out / f"fig-bound-gap-v4.{ext}", **kw)
    svg = out / "fig-bound-gap-v4.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)
    with Image.open(out / "fig-bound-gap-v4.png") as im:
        im.save(out / "preview-160mm.png", dpi=(300, 300))
    provenance = {
        "source_files": {"data/figure-inputs/p2-audit.json.gz": sha256(audit_path),
                         "data/summary.json": sha256(summary_path)},
        "source_fields": {"actual": "core_comparison[k].new_mean_B_over_M",
                          "ceiling": "core_comparison[k].relaxation_ceiling_mean_B_over_LB"},
        "n_per_core": 100, "cores": ks,
        "actual_mean_B_over_U": lower, "relaxation_mean_B_over_L": upper,
        "audit_solver_commit": audit.get("solver_commit"),
        "audit_runner_commit": audit.get("runner_commit"),
    }
    (out / "source-record.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (out / "SHA256SUMS").write_text(
        "".join(f"{sha256(p)}  {p.name}\n" for p in files), encoding="utf-8")
    print("Rendered frozen-v7 figure; no solver/evaluator calls.")


if __name__ == "__main__":
    main()
