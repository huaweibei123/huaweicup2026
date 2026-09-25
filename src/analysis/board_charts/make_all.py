"""一键重绘全部图表：数据目录 → figures 目录。

用法（数据替换后重跑同一命令即可全量重绘）：
    python -m src.analysis.board_charts.make_all \
        --data results/a/p123-report-farmer/board-charts-data \
        --out  figures/a/board-charts-20260925
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import charts
from .loader import load_all


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="board-charts-data 数据目录")
    ap.add_argument("--out", required=True, help="figures 输出目录")
    ap.add_argument("--tag", default="", help="输出文件名前缀（可选）")
    args = ap.parse_args(argv)

    df = load_all(Path(args.data))
    out = Path(args.out)
    tag = f"{args.tag}-" if args.tag else ""
    made = []

    def emit(name, fn, *a, **kw):
        fn(*a, **kw)
        made.append(name)

    # —— 每题热图（Batch B 优先：全矩阵；P1 另出 Batch A 版本）——
    for problem in ("P1", "P2", "P3"):
        emit(f"{tag}{problem.lower()}-heatmap-lyx",
             charts.plot_heatmap, df, problem, "B-lyx-p123-multicore",
             out / f"{tag}{problem.lower()}-heatmap-lyx",
             title=f"{problem} 加速比热图 — Batch B lyx-p123-multicore（12:17Z 快照，灰斜纹=超时/失败，浅格=未覆盖）")
    emit(f"{tag}p1-heatmap-farmer", charts.plot_heatmap, df, "P1", "A-farmer-q1-v3",
         out / f"{tag}p1-heatmap-farmer",
         title="P1 加速比热图 — Batch A farmer-q1-v3（官方单核分母；斜纹=超时/失败）")

    # —— 均值曲线 ——
    emit(f"{tag}p1-mean-curve", charts.plot_mean_curve, df, "P1",
         ["A-farmer-q1-v3", "B-lyx-p123-multicore"], out / f"{tag}p1-mean-curve",
         title="P1 平均加速比 vs 核数 — 两批次并列（不混格）")
    for problem in ("P2", "P3"):
        emit(f"{tag}{problem.lower()}-mean-curve", charts.plot_mean_curve, df, problem,
             ["B-lyx-p123-multicore"], out / f"{tag}{problem.lower()}-mean-curve",
             title=f"{problem} 平均加速比 vs 核数（Batch B）")

    # —— 分布 / 散点 / 收益 / 效率 / 覆盖 ——
    emit(f"{tag}p1-violin", charts.plot_violin, df, "P1", "A-farmer-q1-v3",
         out / f"{tag}p1-violin")
    emit(f"{tag}p3-violin", charts.plot_violin, df, "P3", "B-lyx-p123-multicore",
         out / f"{tag}p3-violin")
    emit(f"{tag}p1-algo-scatter", charts.plot_algo_scatter, df, out / f"{tag}p1-algo-scatter")
    emit(f"{tag}p3-cache-gain", charts.plot_cache_gain, df, out / f"{tag}p3-cache-gain")
    emit(f"{tag}p1-wall-vs-speedup", charts.plot_wall_vs_speedup, df, "P1",
         "A-farmer-q1-v3", out / f"{tag}p1-wall-vs-speedup")
    emit(f"{tag}p2-wall-vs-speedup", charts.plot_wall_vs_speedup, df, "P2",
         "B-lyx-p123-multicore", out / f"{tag}p2-wall-vs-speedup")
    emit(f"{tag}status-overview", charts.plot_status_overview, df, out / f"{tag}status-overview")

    # —— 官方分母墙钟（Batch C）——
    c = df[(df.batch == "C-official-singlecore")]
    if len(c):
        emit(f"{tag}baseline-wall-hist", charts.plot_baseline_wall, c,
             out / f"{tag}baseline-wall-hist")

    # 统一长表副本（图-表对应）
    df.to_csv(out / "combined-long-table.csv", index=False, encoding="utf-8")
    print(f"figures written to {out}:")
    for name in made:
        print("  -", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
