# -*- coding: utf-8 -*-
"""图 5-2｜张量生命周期与容量约束（P2 初稿 5.5.1，式 5-12/5-13）。

数据：手算可核的小型结构示例（派发单授权路径；物理张量按身份去重，
闭区间 f(t)<=i<=l(t)，同一步输入与输出共同驻留）。占用覆盖完整范围
i=0..max(last)+1（区间之外占用为 0，全部释放可见）。容量取固定配置
表 5-1：L1=524288 B，UB=131072 B。静态闭区间峰值，非实际并行峰值；
无官方 spill 记录，不绘制 spill 事件。
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))

C_L1 = "#2E86AB"   # L1 蓝
C_UB = "#D35400"   # UB 橙
C_CAP = "#C0392B"  # 容量线红
C_TXT = "#2C3E50"
from pathlib import Path
from matplotlib import font_manager
paper_font = Path(__file__).resolve().parents[5] / "template-2026/fonts/SimSun.ttf"
font_manager.fontManager.addfont(str(paper_font))
plt.rcParams["font.family"] = [font_manager.FontProperties(fname=str(paper_font)).get_name(), "DejaVu Sans"]
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["axes.unicode_minus"] = False


def read_csv(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


life = read_csv("lifetimes.csv")
occ = read_csv("occupancy.csv")
cap = {r["space"]: int(r["bytes"]) for r in read_csv("capacity.csv")}
hand = read_csv("handcheck.csv")

steps = sorted({int(r["step"]) for r in occ})
pools = ["L1", "UB"]

# ---- 复核 1：占用覆盖完整范围 i=0..max(last)+1，且由 lifetimes 闭区间重算一致 ----
last_all = max(int(r["last"]) for r in life)
full_steps = list(range(0, last_all + 2))          # 0..max(last)+1
assert steps == full_steps, (steps, full_steps)
assert len(occ) == len(full_steps) * len(pools), len(occ)   # 16 个唯一 (step,space)
assert len({(int(r["step"]), r["space"]) for r in occ}) == len(occ)
recomputed = {p: {i: 0 for i in steps} for p in pools}
for r in life:
    b, p = int(r["bytes"]), r["space"]
    for i in range(int(r["start"]), int(r["last"]) + 1):
        recomputed[p][i] += b
occ_map = {(int(r["step"]), r["space"]): int(r["bytes"]) for r in occ}
for p in pools:
    for i in steps:
        assert recomputed[p][i] == occ_map[(i, p)], (p, i, recomputed[p][i], occ_map[(i, p)])

# ---- 复核 2：handcheck 三个位置与曲线数值一致 ----
for r in hand:
    key = (int(r["step"]), r["space"])
    assert occ_map[key] == int(r["bytes"]), (key, occ_map[key], r["bytes"])

# ---- 复核 3：命题 2 静态条件（max_i H_p(i) <= C_p，两池均成立）----
for p in pools:
    assert max(recomputed[p].values()) <= cap[p], (p, max(recomputed[p].values()), cap[p])

print("self-consistency OK: occupancy==recomputed, handcheck==curve, max<=capacity both pools")
for p in pools:
    peak_step = max(steps, key=lambda i: recomputed[p][i])
    print(f"  {p}: peak {recomputed[p][peak_step]} B at step {peak_step}, capacity {cap[p]} B")

# ---- 绘图：上=生命周期区间；下=L1/UB 占用阶梯+容量线 ----
fig, axes = plt.subplots(
    3, 1, figsize=(6.5, 6.9), sharex=True,
    gridspec_kw={"height_ratios": [1.55, 1.0, 1.0], "hspace": 0.30},
)
ax_life, ax_l1, ax_ub = axes

# 面板 1：生命周期（闭区间 [f, l] 画成 [f-0.5, l+0.5]，覆盖全部被触碰步）
life_sorted = sorted(life, key=lambda r: (r["space"], r["tensor"]))
ypos, ylabels = [], []
for k, r in enumerate(life_sorted):
    y = len(life_sorted) - 1 - k
    s, l = int(r["start"]), int(r["last"])
    color = C_L1 if r["space"] == "L1" else C_UB
    ax_life.broken_barh([(s - 0.5, l - s + 1)], (y - 0.33, 0.66),
                        facecolors=color, edgecolor="white", linewidth=0.6, alpha=0.92)
    mid = (s - 0.5 + l + 0.5) / 2
    tag = r["tensor"].split("-")[0]
    ax_life.text(mid, y, f"{tag} {int(r['bytes'])/1024:g} KiB",
                 ha="center", va="center", fontsize=6.3, color="white", fontweight="bold")
    ypos.append(y)
    ylabels.append(r["tensor"])
ax_life.set_yticks(ypos)
ax_life.set_yticklabels(ylabels, fontsize=6.5)
ax_life.set_ylim(-0.8, len(life_sorted) - 0.2)
ax_life.set_title("物理张量生命周期（闭区间 f(t)≤i≤ℓ(t)，按身份去重）", fontsize=8.5, color=C_TXT, pad=4)
for i in steps:
    ax_life.axvline(i, color="#BDC3C7", linewidth=0.4, zorder=0)

# 面板 2/3：占用阶梯 + 容量线
def draw_occ(ax, pool, color, title, cores_step, cores_txt):
    xs = steps
    ys = [recomputed[pool][i] / 1024 for i in xs]
    ax.stairs(ys, [x - 0.5 for x in xs] + [xs[-1] + 0.5], baseline=0,
              fill=True, facecolor=color, alpha=0.30, edgecolor="none")
    # 每步 i 覆盖 [i-0.5, i+0.5]：线与填充必须同相位
    ax.plot([xs[0] - 0.5] + [x + 0.5 for x in xs],
            ys + [ys[-1]], drawstyle="steps-post", color=color, linewidth=1.3)
    # 共同驻留步：紫色竖带（同一步的输入与输出在容量检查中同时存在）
    ax.axvspan(cores_step - 0.5, cores_step + 0.5, color="#8E44AD", alpha=0.10, zorder=0)
    cores_y = cap[pool] / 1024 * 0.52 if pool == "L1" else cap[pool] / 1024 * 1.10
    ax.text(cores_step, cores_y, cores_txt,
            ha="center", va="center", fontsize=6.2, color="#6C3483")
    ax.axhline(cap[pool] / 1024, color=C_CAP, linestyle="--", linewidth=1.2)
    ax.text(xs[-1] + 0.42, cap[pool] / 1024, f"{pool} 容量 {cap[pool]/1024:g} KiB",
            ha="right", va="bottom", fontsize=6.5, color=C_CAP)
    # 手算核对三点：峰值前 / 峰值处 / 部分释放后（步 7 全部释放为 0）
    hc = [(int(r["step"]), int(r["bytes"])) for r in hand if r["space"] == pool]
    peak_step = max(hc, key=lambda t: t[1])[0]
    for s, b in hc:
        ax.plot(s, b / 1024, "o", color="#1A2530", markersize=3.4, zorder=5)
        if s == peak_step:
            ax.annotate(f"峰值处 {b/1024:g}", xy=(s, b/1024), xytext=(s+(0.55 if pool=="L1" else 0.18), b/1024 + cap[pool]/1024*0.015),
                        fontsize=6.2, color="#1A2530", ha="left")
            continue
        elif s == min(t[0] for t in hc):
            lab = f"峰值前 {b/1024:g}"
        else:
            lab = f"部分释放后 {b/1024:g}"
        ax.annotate(lab, xy=(s, b / 1024), xytext=(s - 0.05, b / 1024 + cap[pool] / 1024 * 0.07),
                    fontsize=6.2, color="#1A2530", ha="center")
    # 全部释放位置：占用在 max(last)+1 步回落到 0
    ax.annotate("全部释放 0", xy=(xs[-1], 0), xytext=(xs[-1] - 0.1, cap[pool] / 1024 * 0.05),
                fontsize=6.2, color="#1A2530", ha="center")
    ax.set_title(title, fontsize=8.5, color=C_TXT, pad=4)
    ax.set_ylabel("驻留字节（KiB）", fontsize=7.5)
    ax.set_ylim(0, cap[pool] / 1024 * 1.16)
    ax.tick_params(labelsize=7)

draw_occ(ax_l1, "L1", C_L1, "L1 占用 H_L1(i)（闭区间累加）", 2, "共同驻留：T3 输入×T4 输出")
draw_occ(ax_ub, "UB", C_UB, "UB 占用 H_UB(i)", 4, "共同驻留：U1 输入×U3 输出")
ax_ub.set_xlabel("Step2 操作序号 i（执行序，非时间）", fontsize=7.5)
ax_ub.set_xticks(steps)

legend_items = [
    Patch(facecolor=C_L1, alpha=0.85, label="L1 池张量"),
    Patch(facecolor=C_UB, alpha=0.85, label="UB 池张量"),
    Line2D([0], [0], color=C_CAP, linestyle="--", label="固定配置容量线"),
    Line2D([0], [0], marker="o", color="#1A2530", linestyle="", markersize=3.4, label="手算核对位置"),
]
axes[0].legend(handles=legend_items, loc="upper right", fontsize=6.2, framealpha=0.9)

fig.suptitle("张量生命周期与闭区间容量条件（手算示例；静态估计，非实际并行峰值）",
             fontsize=9.5, color=C_TXT, y=0.985)
fig.text(0.5, 0.006,
         "结构示例（手算可核）：末触步仍计入占用，下一步释放；T6=[5,6]、U3=[4,6] 即两端闭合例证。"
         "无官方 spill 记录，未绘制 spill 事件。",
         ha="center", fontsize=6.2, color="#5D6D7E")

fig.savefig(os.path.join(HERE, "figure.svg"), format="svg", bbox_inches="tight")
fig.savefig(os.path.join(HERE, "figure.png"), format="png", dpi=300, bbox_inches="tight")
print("figure.svg / figure.png written")

fig.savefig(os.path.join(HERE, "figure.pdf"), format="pdf", bbox_inches="tight")
