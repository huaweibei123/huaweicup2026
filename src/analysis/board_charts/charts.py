"""图表函数集：每个函数产出一种图（PNG/SVG/PDF 三格式）。

所有图从统一长表（loader.load_all）驱动；数据替换后重跑 make_all 即全量重绘。
诚实原则：NA/missing/timeout 显式区分色；部分数据标 PARTIAL 与有效 n。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .style import (BATCH_COLORS, CMAP_SPEEDUP, MISSING_COLOR, NA_COLOR,
                    PROBLEM_COLORS, setup_style)

EXTERNAL_REFERENCE = {
    "P1": {2: 1.87, 3: 2.57, 4: 3.14, 5: 3.57},
    "P2": {2: 2.26, 3: 3.18, 4: 3.96, 5: 4.53},
    "P3": {2: 2.28, 3: 3.23, 4: 4.09, 5: 4.76},
}
CORES = [2, 3, 4, 5]


def _save(fig, out: Path):
    plt = setup_style()
    out.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".svg", ".pdf"):
        fig.savefig(out.with_suffix(suffix), bbox_inches="tight")
    plt.close(fig)


def _cell_matrix(df, problem, batch, cores=CORES):
    """返回 100×len(cores) speedup 矩阵 + 状态矩阵。"""
    sub = df[(df.problem == problem) & (df.batch == batch) & (df.cores.isin(cores))]
    cases = sorted(sub.case_id.unique(), key=lambda x: int(x))
    sp = np.full((len(cases), len(cores)), np.nan)
    st = np.empty((len(cases), len(cores)), dtype=object)
    st[:] = "missing"
    idx = {c: i for i, c in enumerate(cases)}
    for _, r in sub.iterrows():
        i, j = idx[r.case_id], cores.index(int(r.cores))
        st[i, j] = r.status
        if r.status == "ok" and pd.notna(r.speedup):
            sp[i, j] = r.speedup
    return cases, cores, sp, st


def plot_heatmap(df, problem, batch, out: Path, title=None):
    """100×4 加速比热图：ok=色阶；timeout/error=深灰；missing=浅灰。"""
    plt = setup_style()
    cases, cores, sp, st = _cell_matrix(df, problem, batch)
    fig, ax = plt.subplots(figsize=(4.6, max(4.5, 0.145 * len(cases) + 1.4)))
    from matplotlib.colors import ListedColormap
    cmap = plt.get_cmap(CMAP_SPEEDUP).copy()
    cmap.set_bad(MISSING_COLOR)
    masked = np.ma.masked_invalid(sp)
    vmax = np.nanmax(sp) if np.isfinite(np.nanmax(sp)) and np.nanmax(sp) > 0 else 1.0
    im = ax.pcolormesh(np.arange(len(cores) + 1), np.arange(len(cases) + 1), masked,
                       cmap=cmap, vmin=0, vmax=np.ceil(vmax * 2) / 2,
                       edgecolors="white", linewidth=0.25)
    # 非 ok 格覆盖灰/斜纹
    for i in range(len(cases)):
        for j in range(len(cores)):
            if st[i, j] == "missing":
                ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=MISSING_COLOR,
                                           edgecolor="white", linewidth=0.25))
            elif st[i, j] in ("timeout", "failed", "error"):
                ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor="#BFBFBF",
                                           hatch="///", edgecolor="white", linewidth=0.25))
    fig.colorbar(im, ax=ax, label="加速比 B(G)/M（官方单核分母）", pad=0.02)
    ax.set_yticks(np.arange(len(cases)) + 0.5)
    ax.set_yticklabels(cases, fontsize=4.5)
    ax.set_xticks([j + 0.5 for j in range(len(cores))])
    ax.set_xticklabels([f"{k}核" for k in cores])
    ax.set_ylabel("算例（按编号）")
    ax.invert_yaxis()
    n_ok = int(np.isfinite(sp).sum())
    ax.set_title(title or f"{problem} 多核加速比热图（ok {n_ok}/{len(cases) * len(cores)} 格；灰格=超时/失败，浅格=未覆盖）",
                 fontsize=10)
    _save(fig, out)


def plot_mean_curve(df, problem, batches, out: Path, title=None, external=True):
    """均值曲线（逐 case 比值算术平均 ± IQR 带），多批次并列 + 外部参考虚线。"""
    plt = setup_style()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for batch in batches:
        sub = df[(df.problem == problem) & (df.batch == batch) & (df.cores.isin(CORES)) & (df.status == "ok")]
        xs, means, q1s, q3s, ns = [], [], [], [], []
        for k in CORES:
            v = sub[sub.cores == k].speedup.dropna()
            if len(v) == 0:
                continue
            xs.append(k); means.append(v.mean()); ns.append(len(v))
            q1s.append(v.quantile(0.25)); q3s.append(v.quantile(0.75))
        if not xs:
            continue
        color = PROBLEM_COLORS.get(problem, "#2E86AB") if len(batches) == 1 else BATCH_COLORS.get(batch)
        ax.plot(xs, means, "o-", color=color, lw=2, ms=6,
                label=f"{batch.split('-')[0]} 均值（逐格比值算术平均）")
        ax.fill_between(xs, q1s, q3s, color=color, alpha=0.15)
        for x, m, n in zip(xs, means, ns):
            ax.annotate(f"n={n}", (x, m), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=8, color=color)
    if external and problem in EXTERNAL_REFERENCE:
        ref = EXTERNAL_REFERENCE[problem]
        ax.plot(list(ref), list(ref.values()), "s--", color="#777777", ms=5,
                label="外部参考（用户截图，可比性待核）")
    ax.set_xticks(CORES)
    ax.set_xticklabels([f"{k}核" for k in CORES])
    ax.set_xlabel("核数")
    ax.set_ylabel("平均加速比 B(G)/M")
    ax.set_title(title or f"{problem} 平均加速比 vs 核数（带 = 四分位距；n=有效格数）", fontsize=11)
    ax.legend(loc="upper left")
    _save(fig, out)


def plot_violin(df, problem, batch, out: Path, title=None):
    """各核数加速比分布（小提琴+散点）。"""
    plt = setup_style()
    sub = df[(df.problem == problem) & (df.batch == batch) & (df.cores.isin(CORES)) & (df.status == "ok")]
    data = [sub[sub.cores == k].speedup.dropna().values for k in CORES]
    pos = [k for k, v in zip(CORES, data) if len(v)]
    data = [v for v in data if len(v)]
    if not data:
        return
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    try:
        vp = ax.violinplot(data, positions=pos, widths=0.7, showmeans=True, showextrema=False)
        for body in vp["bodies"]:
            body.set_facecolor(PROBLEM_COLORS.get(problem, "#2E86AB")); body.set_alpha(0.35)
    except (AttributeError, ValueError, np.linalg.LinAlgError):
        # 零方差等退化数据：KDE 失败 → 退化为箱线
        ax.boxplot(data, positions=pos, widths=0.5, showmeans=True,
                   patch_artist=True,
                   boxprops=dict(facecolor=PROBLEM_COLORS.get(problem, "#2E86AB"), alpha=0.35),
                   medianprops=dict(color="#C1666B"))
    rng = np.random.default_rng(7)
    for x, v in zip(pos, data):
        ax.scatter(np.full(len(v), x) + rng.uniform(-0.12, 0.12, len(v)), v,
                   s=6, color="#333333", alpha=0.45, zorder=3)
    ax.set_xticks(CORES); ax.set_xticklabels([f"{k}核" for k in CORES])
    ax.set_xlabel("核数"); ax.set_ylabel("逐格加速比 B(G)/M")
    ax.set_title(title or f"{problem} 逐格加速比分布（小提琴=分布，点=格，横线=均值）", fontsize=11)
    _save(fig, out)


def plot_status_overview(df, out: Path, title=None):
    """三批次状态构成堆叠条（覆盖率总览）。"""
    plt = setup_style()
    groups = [("A-farmer-q1-v3", "P1"), ("B-lyx-p123-multicore", "P1"),
              ("B-lyx-p123-multicore", "P2"), ("B-lyx-p123-multicore", "P3"),
              ("C-official-singlecore", "P1")]
    labels, okc, failc, missc = [], [], [], []
    for batch, problem in groups:
        sub = df[(df.batch == batch) & (df.problem == problem)]
        if len(sub) == 0:
            continue
        labels.append(f"{batch.split('-')[0]}\n{problem}")
        okc.append((sub.status == "ok").sum())
        failc.append(sub.status.isin(["timeout", "failed", "error"]).sum())
        missc.append(sub.status.isin(["missing", "not_run", "running_unconfirmed"]).sum())
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.barh(y, okc, color="#4C9F70", label="ok")
    ax.barh(y, failc, left=okc, color="#C1666B", label="timeout/failed/error")
    ax.barh(y, missc, left=np.array(okc) + np.array(failc), color="#D8D8D8", label="missing/not_run")
    for yi, (o, f_, m) in enumerate(zip(okc, failc, missc)):
        ax.text(o + f_ + m + 6, yi, f"{o + f_ + m}", va="center", fontsize=9, color="#555555")
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("记录数（含 k1 分母行）")
    ax.set_title(title or "三批次覆盖与状态构成（快照时点）", fontsize=11)
    ax.legend(loc="lower right")
    _save(fig, out)


def plot_algo_scatter(df, out: Path, title=None):
    """P1 双算法并列对比：LYX q1_search vs farmer propose（同格散点 + 对角线）。"""
    plt = setup_style()
    a = df[(df.batch == "A-farmer-q1-v3") & (df.problem == "P1") & (df.cores.isin(CORES)) & (df.status == "ok")]
    b = df[(df.batch == "B-lyx-p123-multicore") & (df.problem == "P1") & (df.cores.isin(CORES)) & (df.status == "ok")]
    amap = {(r.case_id, int(r.cores)): r.speedup for _, r in a.iterrows() if pd.notna(r.speedup)}
    xs, ys, ks = [], [], []
    for _, r in b.iterrows():
        k = (r.case_id, int(r.cores))
        if k in amap and pd.notna(r.speedup):
            xs.append(r.speedup); ys.append(amap[k]); ks.append(int(r.cores))
    if not xs:
        return
    fig, ax = plt.subplots(figsize=(5.6, 5.4))
    sc = ax.scatter(xs, ys, c=ks, cmap="viridis", s=26, alpha=0.75, edgecolors="white", linewidths=0.4)
    lim = max(max(xs), max(ys)) * 1.08
    ax.plot([0, lim], [0, lim], "--", color="#999999", lw=1, label="y = x（两法相同）")
    fig.colorbar(sc, ax=ax, label="核数", ticks=CORES)
    ax.set_xlabel("LYX q1_search_32_seed0 加速比")
    ax.set_ylabel("farmer propose-e0 加速比")
    n = len(xs)
    both_above = sum(1 for x, y in zip(xs, ys) if y > x)
    ax.set_title(title or f"P1 双算法同格并列（n={n}；对角线上方=propose 更优 {both_above} 格）", fontsize=11)
    ax.legend(loc="lower right")
    _save(fig, out)


def plot_cache_gain(df, out: Path, title=None):
    """P3 同计划 Cache 收益：cache_speedup 分布（>1 即 Cache 有益）。"""
    plt = setup_style()
    sub = df[(df.problem == "P3") & (df.batch == "B-lyx-p123-multicore") & pd.notna(df.cache_speedup)]
    if len(sub) == 0:
        return
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for k in CORES:
        v = sub[sub.cores == k].cache_speedup.dropna()
        if len(v) == 0:
            continue
        ax.scatter(np.full(len(v), k) + np.random.default_rng(3).uniform(-0.1, 0.1, len(v)),
                   v, s=18, alpha=0.6, color=PROBLEM_COLORS["P3"], edgecolors="white", linewidths=0.3)
    ax.axhline(1.0, color="#C1666B", ls="--", lw=1.2, label="cache_gain = 1（无收益线）")
    ax.set_xticks(CORES); ax.set_xticklabels([f"{k}核" for k in CORES])
    ax.set_xlabel("核数"); ax.set_ylabel("Cache 收益 = P2(无Cache)/P3（同计划同核）")
    n = len(sub)
    above = int((sub.cache_speedup > 1).sum())
    ax.set_title(title or f"P3 同计划 Cache 收益（n={n} 对；>1 共 {above} 对）", fontsize=11)
    ax.legend()
    _save(fig, out)


def plot_wall_vs_speedup(df, problem, batch, out: Path, title=None):
    """求解墙钟 vs 加速比散点（效率视角，对数 x）。"""
    plt = setup_style()
    sub = df[(df.problem == problem) & (df.batch == batch) & (df.cores.isin(CORES)) &
             (df.status == "ok") & pd.notna(df.speedup) & pd.notna(df.solver_wall_seconds) &
             (df.solver_wall_seconds > 0)]
    if len(sub) == 0:
        return
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    sc = ax.scatter(sub.solver_wall_seconds, sub.speedup, c=sub.cores, cmap="viridis",
                    s=22, alpha=0.75, edgecolors="white", linewidths=0.3)
    ax.set_xscale("log")
    fig.colorbar(sc, ax=ax, label="核数", ticks=CORES)
    ax.set_xlabel("solver 端到端墙钟（s，含内部评价，对数轴）")
    ax.set_ylabel("逐格加速比 B(G)/M")
    ax.set_title(title or f"{problem} 求解耗时 vs 加速比（{len(sub)} 格）", fontsize=11)
    _save(fig, out)


def plot_baseline_wall(progress_csv_or_df, out: Path, title=None):
    """官方单核分母：逐例墙钟分布（100/100）。"""
    plt = setup_style()
    dfb = progress_csv_or_df
    dfb = dfb[(dfb.status == "ok") & pd.notna(dfb.evaluation_wall_seconds) & (dfb.evaluation_wall_seconds > 0)]
    if len(dfb) == 0:
        return
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    v = dfb.evaluation_wall_seconds.astype(float)
    ax.hist(v, bins=24, color=BATCH_COLORS["C-official-singlecore"], alpha=0.85,
            edgecolor="white")
    ax.axvline(v.median(), color="#C1666B", ls="--", lw=1.4,
               label=f"中位数 {v.median():.2f}s")
    ax.axvline(30, color="#888888", ls=":", lw=1.2, label="30s（本方 v3 曾用上限）")
    ax.axvline(180, color="#444444", ls=":", lw=1.2, label="180s（LYX 上限）")
    ax.set_xlabel("官方单核评价墙钟（s）"); ax.set_ylabel("图数")
    ax.set_title(title or f"官方单核分母逐例墙钟分布（n={len(v)}/100，Batch C）", fontsize=11)
    ax.legend()
    _save(fig, out)
