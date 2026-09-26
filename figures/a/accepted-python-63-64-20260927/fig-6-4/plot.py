# -*- coding: utf-8 -*-
"""图 6-4｜Cache 收益与字节命中率关系（forest311322b 完整 500 格同计划配对）。

绘图只读交付包内三张 CSV（pair_metrics / per_core_summary / negative_cases），
不读取包外文件；CSV 由 extract_pairs.py 从 fetch_pair_inputs.py 的
verified-pairs.json（500 格全部经 plan 字节相同断言 + 两端 gzip SHA + 核数与
Makespan 核对）构建。数据版本：forest solver 311322b 的 revision2 同计划配对
（476 条复用旧配对 + 24 条已完成补算），非旧 witness、非汇总反推。

面板 1：五核数平均 CacheGain 折线（y=1 参考线）。
面板 2：逐例分布（按核数分组散点 + 箱线；负收益点红色高亮，全部保留）。
面板 3：字节命中率与 CacheGain 关系散点（y=1 参考线；无访问样本单独列于左侧；
不以此散点相关性证明命中率决定总体加速）。

运行（工作目录=仓库根）：
  .venv/Scripts/python.exe figures/a/jia-fig6-4-20260926/plot.py
"""
import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
C_TXT = "#2C3E50"
C_POS = "#2E86AB"
C_NEG = "#C0392B"
C_PARITY = "#BDC3C7"
C_REF = "#7F8C8D"

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 8


def read_csv(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


rows = read_csv("pair_metrics.csv")
summary = read_csv("per_core_summary.csv")
neg = read_csv("negative_cases.csv")

# ---- 断言：500 格、口径一致 ----
assert len(rows) == 500
assert len(neg) == sum(1 for r in rows if r["category"] == "negative")
for r in rows:
    g = float(r["cache_gain"])
    assert abs(g - int(r["no_l2_makespan"]) / int(r["cache_makespan"])) < 1e-12
    assert (r["category"] == "negative") == (g < 1)
    if r["byte_hit_rate"] != "":
        h, m = int(r["hit_bytes"]), int(r["miss_bytes"])
        assert abs(float(r["byte_hit_rate"]) - h / (h + m)) < 1e-12
    else:
        assert int(r["hit_bytes"]) + int(r["miss_bytes"]) == 0

means = {int(s["cores"]): float(s["mean_cache_gain"]) for s in summary}
pooled = {int(s["cores"]): s["pooled_byte_hit_rate"] for s in summary}
noaccess = {int(s["cores"]): int(s["no_access_cells"]) for s in summary}

# ================= 绘图 =================
fig = plt.figure(figsize=(6.5, 9.0))
gs = fig.add_gridspec(3, 1, height_ratios=[0.85, 1.15, 1.0],
                      hspace=0.5, left=0.105, right=0.96, top=0.945, bottom=0.06)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])

# ---- 面板 1：五核数平均 CacheGain 折线 ----
ks = sorted(means)
ax1.plot(ks, [means[k] for k in ks], color=C_POS, lw=1.4, marker="o", markersize=5, zorder=3)
for k in ks:
    ax1.annotate("%.5f" % means[k], (k, means[k]), textcoords="offset points",
                 xytext=(0, 8), ha="center", fontsize=7.5, color=C_TXT)
ax1.axhline(1.0, color=C_REF, lw=1.0, ls="--", zorder=2)
ax1.text(5.35, 1.0, "y=1", va="center", fontsize=7.5, color=C_REF)
ax1.set_xticks(ks)
ax1.set_xlim(0.6, 5.6)
ax1.set_ylabel("平均 CacheGain", fontsize=8)
ax1.set_title("面板 1｜五核数平均 CacheGain（同核数无 L2 Makespan / Cache Makespan；500 格）",
              fontsize=8, color=C_TXT, pad=4, loc="left")
ax1.tick_params(labelsize=8)

# ---- 面板 2：逐例分布（散点 + 箱线，负收益红色）----
groups = defaultdict(list)
for r in rows:
    groups[int(r["cores"])].append(r)
import random
random.seed(20260927)
for k in ks:
    grp = groups[k]
    ys = [float(r["cache_gain"]) for r in grp]
    xs = [k + random.uniform(-0.16, 0.16) for _ in grp]
    negx = [x for x, r in zip(xs, grp) if r["category"] == "negative"]
    negy = [y for y, r in zip(ys, grp) if r["category"] == "negative"]
    posx = [x for x, r in zip(xs, grp) if r["category"] != "negative"]
    posy = [y for y, r in zip(ys, grp) if r["category"] != "negative"]
    ax2.scatter(posx, posy, s=9, color=C_POS, alpha=0.55, linewidths=0, zorder=3)
    ax2.scatter(negx, negy, s=16, color=C_NEG, marker="v", alpha=0.9, linewidths=0, zorder=4)
    bp = ax2.boxplot([ys], positions=[k], widths=0.32, showfliers=False,
                     medianprops=dict(color=C_TXT, lw=1.0),
                     boxprops=dict(color=C_TXT, lw=0.8),
                     whiskerprops=dict(color=C_TXT, lw=0.8),
                     capprops=dict(color=C_TXT, lw=0.8), zorder=2)
ax2.axhline(1.0, color=C_REF, lw=1.0, ls="--", zorder=1)
ax2.set_xticks(ks)
ax2.set_xlim(0.6, 5.6)
ax2.set_ylabel("CacheGain（逐例）", fontsize=8)
ax2.set_title("面板 2｜逐例分布（散点=逐格，箱线=四分位；红▼=负收益 CacheGain<1，全部保留）",
              fontsize=8, color=C_TXT, pad=4, loc="left")
ax2.tick_params(labelsize=8)
ax2.legend(handles=[Line2D([0], [0], color=C_NEG, marker="v", ls="", markersize=6,
                           label="负收益格（CacheGain<1）")],
           fontsize=7.5, loc="upper left", frameon=False)

# ---- 面板 3：字节命中率与 CacheGain 散点（无访问样本单独列于左侧）----
NEG_X = -0.045
for r in rows:
    k = int(r["cores"])
    g = float(r["cache_gain"])
    if r["byte_hit_rate"] != "":
        x = float(r["byte_hit_rate"])
        col = C_NEG if r["category"] == "negative" else C_POS
        ax3.scatter([x], [g], s=9, color=col, alpha=0.5, linewidths=0, zorder=3)
    else:
        ax3.scatter([NEG_X], [g], s=16, color=C_PARITY, marker="s",
                    edgecolors=C_TXT, linewidths=0.5, zorder=3)
ax3.axhline(1.0, color=C_REF, lw=1.0, ls="--", zorder=1)
ax3.axvline(0, color="#D5D8DC", lw=0.6, zorder=1)
ax3.set_xlim(-0.09, 1.02)
ax3.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax3.set_xticklabels(["0", "0.2", "0.4", "0.6", "0.8", "1.0"])
ax3.set_xlabel("字节命中率 hit_bytes/(hit_bytes+miss_bytes)（无访问样本单独列于左侧 □，共 %d 格）"
               % sum(1 for r in rows if r["byte_hit_rate"] == ""), fontsize=8)
ax3.set_ylabel("CacheGain（逐例）", fontsize=8)
ax3.set_title("面板 3｜字节命中率与 CacheGain 关系（散点仅展示分布，不构成命中率决定总体加速的证据）",
              fontsize=8, color=C_TXT, pad=4, loc="left")
ax3.tick_params(labelsize=8)
ax3.legend(handles=[
    Line2D([0], [0], color=C_POS, marker="o", ls="", markersize=5, label="正收益/持平格"),
    Line2D([0], [0], color=C_NEG, marker="v", ls="", markersize=6, label="负收益格"),
    Line2D([0], [0], color=C_PARITY, marker="s", ls="", markersize=6,
           label="无访问样本（hit+miss=0，命中率留空）")],
    fontsize=7.5, loc="lower right", frameon=False)

svg_path = os.path.join(HERE, "figure.svg")
png_path = os.path.join(HERE, "figure.png")
fig.savefig(svg_path, format="svg")
fig.savefig(png_path, format="png", dpi=300)
print("figure.svg / figure.png written")
print("panel1 mean per core:", {k: round(means[k], 6) for k in ks})
print("negative cells:", len(neg), "| no-access cells:",
      sum(1 for r in rows if r["byte_hit_rate"] == ""))
