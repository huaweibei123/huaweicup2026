"""Plot published observations only; never import evaluators or run solvers.

Run from any directory with the project's locked Python environment.
Styling follows the project scientific-figures guidance; plotting code is original.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, ft2font, pyplot as plt
from matplotlib.patches import Patch
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
BLUE, RED, GRAY, AMBER = "#126B85", "#C45943", "#E6EBEF", "#E6B955"
INK, MUTED = "#162D3A", "#596D78"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/a/p123-captain-snapshot-20260924")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    data = json.loads((args.input / "snapshot.json").read_text())
    costs = json.loads((args.input / "costs-source.json").read_text())
    for name, expected in data["source_sha256"].items():
        assert hashlib.sha256((args.input / name).read_bytes()).hexdigest() == expected

    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next(n for n in ("PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", "Arial Unicode MS") if n in available)
    assert ord("图") in ft2font.FT2Font(font_manager.findfont(font)).get_charmap()
    plt.rcParams.update({"font.family": font, "font.size": 11, "axes.unicode_minus": False,
                         "svg.fonttype": "none", "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": MUTED, "ytick.color": INK})
    fig = plt.figure(figsize=(15.8, 10.3), facecolor="white")
    fig.text(.055, .945, "三问题评测：当前能从公开数据看出什么？", fontsize=23, weight="bold")
    fig.text(.055, .909, "局部快照 · 不是全量结论   |   方案质量用模拟周期衡量；程序耗时另算", color=MUTED, fontsize=12)
    grid = fig.add_gridspec(2, 2, left=.16, right=.94, top=.83, bottom=.19,
                           height_ratios=[1, 1.13], wspace=.49, hspace=.65)

    first, second = data["samples"]
    ax = fig.add_subplot(grid[0, 0])
    ratios = [first["singlecore_cycles"] / first[p] for p in ("P1", "P2", "P3")]
    ax.barh(range(3), ratios, color=[BLUE, RED, RED], height=.53)
    ax.axvline(1, color=MUTED, linestyle="--", linewidth=1)
    ax.set_yticks(range(3), ["P1 · 搜索", "P2 · 通用基线", "P3 · 结构选择"])
    ax.invert_yaxis()
    ax.set_xlim(0, 2.08)
    ax.set_xlabel("官方单核 / 多核 Makespan（倍）")
    ax.set_title("A   case002 · 双核", loc="left", fontsize=15, pad=20)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    for y, v in enumerate(ratios):
        ax.text(v + .055, y, f"{v:.3f}×", va="center", fontsize=12, weight="bold")
    ax.text(1, -.45, "1×：与官方单核相同", ha="center", fontsize=9, color=MUTED)
    ax.text(0, -.38, "P3 此项为补充指标；不同问题的硬件语义不同。", transform=ax.transAxes, fontsize=9, color=MUTED)

    ax = fig.add_subplot(grid[0, 1])
    vals = [second[p] / 1e6 for p in ("P2", "P3")]
    ax.barh(range(2), vals, color=["#536A9D", "#607C73"], height=.48)
    ax.set_yticks(range(2), ["P2 · 通用基线", "P3 · 结构选择"])
    ax.invert_yaxis()
    ax.set_xlim(0, 5.5)
    ax.set_xlabel("Makespan（百万模拟周期；越低越好）")
    ax.set_title("B   case014 · 五核", loc="left", fontsize=15, pad=20)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    for y, p in enumerate(("P2", "P3")):
        ax.text(vals[y] + .12, y, f"{second[p]:,}", va="center", fontsize=11)
    ax.text(0, -.38, "单核超时（180 秒），P1 无官方确认方案。\n没有分母，不能计算加速比；两条计划不是 Cache 配对。", transform=ax.transAxes, fontsize=9, color=MUTED)

    ax = fig.add_subplot(grid[1, :])
    names = ["官方单核", "P1", "P2", "P3"]
    planned = [100, 400, 400, 500]
    groups = [costs["outcomes"][n] for n in ("singlecore", "P1", "P2", "P3")]
    ok = [g.get("ok", 0) for g in groups]
    failed = [g.get("timeout", 0) + g.get("error", 0) for g in groups]
    partial = [g.get("receipt_missing", 0) for g in groups]
    unreported = [n-o-f-p for n,o,f,p in zip(planned,ok,failed,partial)]
    assert all(n >= 0 for n in unreported)
    left = np.zeros(4)
    for counts, color, hatch in [(ok,BLUE,None),(failed,RED,None),(partial,AMBER,"///"),(unreported,GRAY,None)]:
        widths = np.array(counts) / np.array(planned) * 100
        ax.barh(range(4), widths, left=left, color=color, height=.55, hatch=hatch, linewidth=0)
        left += widths
    ax.set_yticks(range(4), names)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([0,25,50,75,100], ["0%","25%","50%","75%","100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("占各组计划单元的比例（评价覆盖率，不是性能）")
    for y, (o, f, p, n) in enumerate(zip(ok, failed, partial, planned)):
        label=f"成功 {o}/{n}"
        if f: label+=f" · 失败/超时 {f}"
        if p: label+=f" · 未收尾 {p}"
        ax.text(101.5, y, label, va="center", fontsize=10, clip_on=False)
    ax.set_title("C   全量测试覆盖快照 · 2026-09-24 18:24:51 台北", loc="left", fontsize=15, pad=20)
    ax.legend(handles=[Patch(color=BLUE,label="成功"),Patch(color=RED,label="失败 / 超时"),
                       Patch(facecolor=AMBER,hatch="///",label="尚未收尾"),Patch(color=GRAY,label="尚无收据（含未开始或在途）")],
              ncol=4, frameon=False, loc="upper left", bbox_to_anchor=(0,1.075), fontsize=9)
    # Leave room for labels at the right of the chart without truncating the bars.
    box = ax.get_position(); ax.set_position([box.x0,box.y0,box.width*.77,box.height])

    fig.text(.055, .114, "Q3 的关键对照", fontsize=12, weight="bold", color=BLUE)
    fig.text(.195, .114, "case002 双核：同一计划的 P2 / P3 = 1.000×，这个样本未显示 Cache 收益。", fontsize=11)
    fig.text(.055, .070, "A/B：LYX 17:41 预检回报；C：PR78 b6d9dbf 的固定成本快照。均为作者报告，队长未重跑评估器。", fontsize=9, color=MUTED)
    fig.text(.055, .047, "单个用例不能代表 100 图；暂缺逐格成绩表，不能可靠制作全量收益热力图或完整求解耗时分布。", fontsize=9, color=MUTED)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(args.output / f"overview.{ext}", dpi=180, facecolor="white")
    svg = args.output / "overview.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)

    with (args.output / "preflight_metrics.csv").open("w", newline="") as f:
        writer=csv.writer(f, lineterminator="\n");writer.writerow(["case","cores","problem","makespan_cycles","singlecore_cycles","multicore_ratio","note"])
        for sample in data["samples"]:
            for problem in ("P1","P2","P3"):
                cycles=sample[problem];base=sample["singlecore_cycles"]
                writer.writerow([sample["case"],sample["cores"],problem,cycles,base,base/cycles if cycles and base else None,"member-reported; P3 ratio supplementary"])
    receipt={"source_commit":data["source_commit"],"inputs":{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in args.input.iterdir() if x.is_file()},
             "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "environment":{"python":platform.python_version(),"matplotlib":matplotlib.__version__,"numpy":np.__version__,"font":font},
             "new_evaluator_or_solver_calls":0,"limits":data["evidence"],
             "artifacts":{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in args.output.iterdir() if x.is_file()}}
    (args.output / "render-receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps({"output":str(args.output),"ratios_case002":ratios,"successful_solver_cells":sum(ok[1:]),"planned_solver_cells":sum(planned[1:])}))


if __name__ == "__main__":
    main()
