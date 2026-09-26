# -*- coding: utf-8 -*-
"""图 6-6｜启用 Cache 前后的事件差异（case021 / 3 核，同计划非单调反例）。

绘图只读交付包内三张 CSV（aligned_ops / key_events / summary_metrics），
不读取包外文件；CSV 由 extract_inputs.py 从四项固定来源生成并核对哈希
（f26704ed 的 021 审计 e50a97d7…、19bebf35 的 P2 result e7b6d54d…、
130dfe4c 的 P3 result f6e460a7… 与 plan 13362774…）。

面板 1/2：P2（无 L2）与 P3（只读 Cache）两个配置的全量时间线，
3 核 × 4 管道（PIPE_MTE2 搬入 / PIPE_M MATMUL / PIPE_V ADD / PIPE_MTE3 搬出）
共 12 行、行序完全一致；事件按真实 start/end 绘制（条宽=持续时间），不平移。
面板 3/4：同一绝对范围的局部放大——窗口 1（首次命中相关变化，[4,900, 7,000]）、
窗口 2（后续 DDR 读取变化，[443,050, 443,250]）；每行上半为 P2、下半为 P3，
关键操作以文字标注。全局负收益（+143 cycles，CacheGain 0.99993）在标题保留；
图注只写"事件观察"，不做因果认定。

运行（工作目录=仓库根）：
  .venv/Scripts/python.exe figures/a/jia-fig6-6-20260926/plot.py
"""
import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
C_TXT = "#2C3E50"
C_P2 = "#7F8C8D"        # 放大面板中 P2 条色
C_P3 = "#E67E22"        # 放大面板中 P3 条色
C_PIPE = {"PIPE_MTE2": "#2E86AB", "PIPE_M": "#8E44AD",
          "PIPE_V": "#E67E22", "PIPE_MTE3": "#5DA7CC"}
C_HIT = "#27AE60"

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 8

MK_P2, MK_P3 = 2140720, 2140863
WIN1 = (4900, 7000)
WIN2 = (443050, 443250)
PIPES_TOPDOWN = ["PIPE_MTE2", "PIPE_M", "PIPE_V", "PIPE_MTE3"]   # 数据流顺序
PIPES = PIPES_TOPDOWN[::-1]                                       # 绘图自块底向块顶
PIPE_SHORT = {"PIPE_MTE2": "MTE2", "PIPE_M": "M", "PIPE_V": "V", "PIPE_MTE3": "MTE3"}
OP_OF_PIPE = {"PIPE_MTE2": "COPY_IN 搬入", "PIPE_M": "MATMUL 计算",
              "PIPE_V": "ADD 计算", "PIPE_MTE3": "COPY_OUT 搬出"}


def read_csv(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


ops = read_csv("aligned_ops.csv")
key_events = {r["event"]: r for r in read_csv("key_events.csv")}
sm = {r["metric"]: r["value"] for r in read_csv("summary_metrics.csv")}

# ---- 断言：官方值与对齐完整性 ----
assert len(ops) == 8881
assert int(sm["makespan_p2_cycles"]) == MK_P2 and int(sm["makespan_p3_cycles"]) == MK_P3
assert int(sm["increase_cycles"]) == 143
for r in ops:
    assert 0 <= int(r["p2_start"]) <= int(r["p2_end"]) <= MK_P2
    assert 0 <= int(r["p3_start"]) <= int(r["p3_end"]) <= MK_P3
for cid in (0, 1, 2):
    for p in ("PIPE_MTE2", "PIPE_M", "PIPE_V", "PIPE_MTE3"):
        n = sum(1 for r in ops if int(r["source_core_id"]) == cid and r["pipe"] == p)
        assert n > 0

fct = key_events["first_completion_gain"]        # 首次完成时间差异（命中 17cy）
fst = key_events["first_start_change"]           # 首次开始时间差异
fss = key_events["first_same_start_slower_copy_in"]  # 同起点变慢（走 DDR）
FCT_ID, FST_ID, FSS_ID = fct["op_id"], fst["op_id"], fss["op_id"]
by_id = {r["op_id"]: r for r in ops}

# ---- 全量面板数据收集：(left, width) ----
p2_by_row = defaultdict(list)
p3_by_row = defaultdict(list)
for r in ops:
    row = (int(r["source_core_id"]), r["pipe"])
    p2_by_row[row].append((int(r["p2_start"]), int(r["p2_end"]) - int(r["p2_start"])))
    p3_by_row[row].append((int(r["p3_start"]), int(r["p3_end"]) - int(r["p3_start"])))
for row, segs in p2_by_row.items():
    assert max(s + w for s, w in segs) <= MK_P2
for row, segs in p3_by_row.items():
    assert max(s + w for s, w in segs) <= MK_P3

ROW_KEYS = [(c, p) for c in (0, 1, 2) for p in PIPES]
ROW_Y = {rc: len(ROW_KEYS) - 1 - i for i, rc in enumerate(ROW_KEYS)}
ROW_LABEL = ["核%d %s" % (c + 1, PIPE_SHORT[p]) for (c, p) in ROW_KEYS]

# ================= 绘图 =================
fig = plt.figure(figsize=(6.5, 9.6))
gs = fig.add_gridspec(4, 1, height_ratios=[1.2, 1.2, 1.15, 1.15],
                      hspace=0.62, left=0.135, right=0.96, top=0.945, bottom=0.06)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])
ax4 = fig.add_subplot(gs[3])

# ---- 面板 1/2：两配置全量时间线（同核/Pipe 行序）----
for ax, by_row, mk, name, extra in (
        (ax1, p2_by_row, MK_P2, "P2（无 L2，模拟周期 2,140,720）", ""),
        (ax2, p3_by_row, MK_P3, "P3（只读 Cache，模拟周期 2,140,863）",
         "：比 P2 +143 cycles，CacheGain 0.99993（非单调）")):
    for (c, p), y in ROW_Y.items():
        segs = by_row[(c, p)]
        ax.broken_barh(segs, (y - 0.38, 0.76), color=C_PIPE[p], linewidth=0, zorder=3)
    ax.axvline(mk, color="#C0392B", lw=1.0, ls=":", zorder=4)
    ax.set_yticks([ROW_Y[k] for k in ROW_KEYS])
    ax.set_yticklabels(ROW_LABEL, fontsize=7)
    ax.set_xlim(0, MK_P3 * 1.02)
    ax.set_ylim(-0.7, len(ROW_KEYS) + 1.3)   # 顶部留白放图例
    ax.set_title("面板 1｜%s%s" % (name, extra) if ax is ax1 else
                 "面板 2｜%s%s" % (name, extra),
                 fontsize=8, color=C_TXT, pad=3, loc="left")
    ax.tick_params(labelsize=7.5)
    for yy in (2.5, 5.5):
        ax.axhline(yy, color="#D5D8DC", lw=0.6, zorder=1)
ax2.set_xlabel("时间（cycles，绝对时间；两端行序一致，事件不平移）", fontsize=8)
ax1.set_xlabel("时间（cycles，绝对时间）", fontsize=8)
ax1.legend(handles=[Patch(color=C_PIPE[p], label="%s（%s）" % (p, OP_OF_PIPE[p]))
                    for p in PIPES_TOPDOWN] +
                   [Line2D([0], [0], color="#C0392B", lw=1.0, ls=":", label="官方 makespan 端点")],
           fontsize=7, loc="upper left", ncol=2, frameon=False,
           handlelength=1.2, columnspacing=0.9)

# ---- 面板 3/4：局部放大（同轴上 P2 / 下 P3，同一绝对范围）----
def draw_zoom(ax, lo, hi, title, highlights):
    for (c, p), y in ROW_Y.items():
        for r in ops:
            if int(r["source_core_id"]) != c or r["pipe"] != p:
                continue
            s2, e2 = int(r["p2_start"]), int(r["p2_end"])
            s3, e3 = int(r["p3_start"]), int(r["p3_end"])
            if e2 > lo and s2 < hi:
                ax.broken_barh([(s2, e2 - s2)], (y + 0.04, 0.40),
                               color=C_P2, linewidth=0, zorder=3)
            if e3 > lo and s3 < hi:
                col = C_HIT if r["op_id"] == FCT_ID and r["p3_cache_hit"] == "True" else C_P3
                ax.broken_barh([(s3, e3 - s3)], (y - 0.44, 0.40),
                               color=col, linewidth=0, zorder=3)
    ax.set_yticks([ROW_Y[k] for k in ROW_KEYS])
    ax.set_yticklabels(ROW_LABEL, fontsize=7)
    ax.set_xlim(lo, hi)
    ax.set_ylim(-0.75, len(ROW_KEYS) + 4.5)   # 顶部三层：图例(14.2+)、标注(<=13.2)、数据(<=12)
    ax.set_title(title, fontsize=8, color=C_TXT, pad=3, loc="left")
    ax.tick_params(labelsize=7.5)
    ax.legend(handles=[Patch(color=C_P2, label="P2（无 L2，行上半）"),
                       Patch(color=C_P3, label="P3（只读 Cache，行下半）"),
                       Patch(color=C_HIT, label="P3 Cache 命中操作")],
              fontsize=7, loc="upper right", ncol=1, frameon=False,
              handlelength=1.2, columnspacing=1.0)
    # 标注放图例下方的独立留白层（图例占 14.2..16.5，标注 <=13.2），引线指向真实事件
    slot = len(ROW_KEYS) + 0.9
    for oid, label in highlights:
        r = by_id[oid]
        y = ROW_Y[(int(r["source_core_id"]), r["pipe"])]
        x3 = int(r["p3_end"])
        ax.annotate(label, xy=(x3, y), xytext=(lo + (hi - lo) * 0.01, slot),
                    fontsize=7, color=C_TXT, ha="left", va="center",
                    arrowprops=dict(arrowstyle="->", color=C_TXT, lw=0.7))
        slot += 1.15

draw_zoom(ax3, *WIN1,
          "面板 3｜窗口 1（同一绝对范围 4,900–7,000 cycles）：首次命中相关变化（核3 task2）",
          [(FCT_ID, "1000004905：P2 207cy → P3 命中 17cy"),
           (FST_ID, "1000006255：起点 5,163 → 4,973")])
draw_zoom(ax4, *WIN2,
          "面板 4｜窗口 2（同一绝对范围 443,050–443,250 cycles）：后续 DDR 读取变化（核1 task0）",
          [(FSS_ID, "1000006089：同起点 443,077，P2 69cy → P3 138cy（走 DDR）")])
ax4.set_xlabel("时间（cycles，绝对时间；两端不平移，同一窗口范围）", fontsize=8)

svg_path = os.path.join(HERE, "figure.svg")
png_path = os.path.join(HERE, "figure.png")
fig.savefig(svg_path, format="svg")
fig.savefig(png_path, format="png", dpi=300)
print("figure.svg / figure.png written")
print("full timelines: 12 rows x2 configs, 17762 segments; zoom windows: same absolute ranges",
      WIN1, WIN2)
