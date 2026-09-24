"""Validate saved pilot evidence and generate tables/figures; zero evaluator calls."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from .construct import ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("figures", type=Path)
    args = parser.parse_args()
    run = json.loads((args.run / "run.json").read_text())
    assert run["status"] == "complete"
    for name, digest in run["sha256"].items():
        assert sha(ROOT / name) == digest, name
    for r in run["records"]:
        assert sha(args.run / r["plan"]) == r["plan_sha256"]
        assert sha(args.run / r["result"]) == r["result_sha256"]
        result = json.loads(gzip.decompress((args.run / r["result"]).read_bytes()))
        assert result["makespan"] == r["makespan"]
        assert result["data_movement_bytes"] == r["data_movement_bytes"]
        assert result.get("cache_stats") == r["cache_stats"]
    rows, controls = [], []
    for case in ("008", "044", "080"):
        records = [r for r in run["records"] if r["case"] == case and not r["repeat"]]
        plans = [json.loads((args.run / r["plan"]).read_text()) for r in records]
        maps = [list(p["node_to_subgraph"].items()) for p in plans]
        owners = [{sg: c for c, ss in enumerate(p["core_schedules"]) for sg in ss} for p in plans]
        assert all(m == maps[0] for m in maps)
        assert all(o == owners[0] for o in owners)
        controls.append({"case": case, "same_ordered_mapping": True, "same_op_core": True})
        for p3 in [r for r in records if r["problem"] == 3]:
            p2 = next(r for r in records if r["problem"] == 2 and r["strategy"] == p3["strategy"])
            assert p2["plan_sha256"] == p3["plan_sha256"]
            assert p2["data_movement_bytes"] == p3["data_movement_bytes"]
            c = next(c for c in run["constructors"] if c["case"] == case and c["strategy"] == p3["strategy"])
            rows.append({"case": case, "strategy": p3["strategy"],
                         "p2_makespan_cycles": p2["makespan"], "p3_makespan_cycles": p3["makespan"],
                         "p3_hit_rate_bytes": p3["cache_stats"]["hit_rate"],
                         "p3_hit_bytes": p3["cache_stats"]["hit_bytes"],
                         "p3_miss_bytes": p3["cache_stats"]["miss_bytes"],
                         "scheduled_copy_bytes": p3["data_movement_bytes"]["scheduled_copy_bytes"],
                         "partition_added_copy_bytes": p3["data_movement_bytes"]["partition_added_copy_bytes"],
                         "spill_added_copy_bytes": p3["data_movement_bytes"]["spill_added_copy_bytes"],
                         "constructor_process_wall_seconds": c["process_wall_seconds"],
                         "p3_external_evaluation_wall_seconds": p3["child_wall_seconds"],
                         "p3_evaluator_peak_rss_bytes": p3["max_rss_bytes"]})
    with (args.run / "metrics.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (args.run / "controls.json").write_text(json.dumps({"controls": controls,
        "complete_source_and_result_hashes_checked": True,
        "p2_p3_same_plan_and_movement": True, "new_evaluator_calls": 0}, indent=2) + "\n")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.9), sharey=True)
    labels = {"component": "Component", "affine_eighth": "Affine 1/8", "resource_word": "M-V-M word"}
    for ax, case in zip(axes, ("008", "044", "080")):
        subset = [r for r in rows if r["case"] == case]
        x = np.arange(len(subset))
        for key, delta, label, color, hatch in (
                ("p2_makespan_cycles", -.18, "P2: no Cache", "#777777", "//"),
                ("p3_makespan_cycles", .18, "P3: FIFO Cache", "#0072B2", None)):
            values = [r[key] / 1000 for r in subset]
            bars = ax.bar(x + delta, values, .34, color=color, hatch=hatch, label=label)
            ax.bar_label(bars, labels=[f"{v:.1f}" for v in values], fontsize=8, padding=3)
        ax.set_title(f"case {case} · 4 cores", pad=10)
        ax.set_xticks(x, [labels[r["strategy"]] for r in subset], rotation=20, ha="right")
        ax.set_ylim(0, 143)
        ax.grid(axis="y", alpha=.18)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Makespan (thousand cycles; lower is better)")
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="upper center", ncol=2, frameon=False)
    fig.subplots_adjust(top=.81, bottom=.25, left=.07, right=.99, wspace=.22)
    fig.text(.07, .035, "Frozen official E0 · same operation/core mapping · 3 public pilot cases, not full-suite acceptance", fontsize=9)
    args.figures.mkdir(parents=True, exist_ok=True)
    for suffix in ("svg", "png", "pdf"):
        fig.savefig(args.figures / f"paired-p2-p3.{suffix}", dpi=160)
    svg = args.figures / "paired-p2-p3.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)
    manifest = {"input": str(args.run / "metrics.csv"), "input_sha256": sha(args.run / "metrics.csv"),
                "source": "src/q3/report.py", "source_sha256": sha(Path(__file__)),
                "matplotlib": matplotlib.__version__, "run_head": run["head"],
                "command": ["python", "-m", "src.q3.report", str(args.run), str(args.figures)],
                "outputs": {f.name: sha(f) for f in args.figures.glob("paired-p2-p3.*")}}
    (args.figures / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    best_dir = args.run / "best"
    best_dir.mkdir(exist_ok=True)
    best_manifest = []
    for case in ("008", "044", "080"):
        row = min((r for r in rows if r["case"] == case), key=lambda r: r["p3_makespan_cycles"])
        source = next(r for r in run["records"] if r["case"] == case
                      and r["strategy"] == row["strategy"] and r["problem"] == 3 and not r["repeat"])
        target = best_dir / f"case_{case}_multicore_res.json"
        target.write_bytes((args.run / source["plan"]).read_bytes())
        best_manifest.append({"case": case, "strategy": row["strategy"],
                              "source": source["plan"], "sha256": sha(target),
                              "p3_makespan_cycles": row["p3_makespan_cycles"]})
    (best_dir / "manifest.json").write_text(json.dumps({"selection": "retrospective E0 selection",
                                                        "plans": best_manifest}, indent=2) + "\n")
    table = ["| case | 构造 | P2 cycles | P3 cycles | P3字节命中率 | spill bytes | 构造进程ms |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        table.append(f"| {r['case']} | {r['strategy']} | {r['p2_makespan_cycles']} | "
                     f"{r['p3_makespan_cycles']} | {r['p3_hit_rate_bytes']:.2%} | "
                     f"{r['spill_added_copy_bytes']} | {1000*r['constructor_process_wall_seconds']:.2f} |")
    gains = []
    for case in ("008", "044", "080"):
        base = next(r for r in rows if r["case"] == case and r["strategy"] == "component")
        best = min((r for r in rows if r["case"] == case), key=lambda r: r["p3_makespan_cycles"])
        gains.append(f"- {case}：{base['p3_makespan_cycles']} → {best['p3_makespan_cycles']} cycles，"
                     f"相对本批 component 基线降低 {1-best['p3_makespan_cycles']/base['p3_makespan_cycles']:.2%}。")
    report = f'''# Q3 首批官方对照：7 个直接构造，3 个公开用例

本机实测源码 **{run['head']}**，原始开始时间 {run['started_utc']}。
4核、官方固定配置，未修改 E0。P2 7次、P3 10次（含3次优选完整复核），
共17次，全部成功、0超时/拒绝/重试；24次总上限未用完、不继续耗余量。
另有8组结构单测通过、0合成E0。资源序列在044/080因守卫不适用明确跳过。

{chr(10).join(gains)}

## 配对结果

{chr(10).join(table)}

完整数据见 metrics.csv；每个场景直接读取同一计划文件、同一 op-core、同一有序mapping。
数据源和结果哈希、实际命令/平台、错误日志、每次评价RSS/CPU在run.json及旁边文件。
P3每图优选复跑完整无损JSON gzip字节与首次一致；不只比较Makespan。
best/下为事后选出的官方两字段计划，**不是训练出的在线选优策略**。

## 能得出的结论

- 008的三种构造都无Cache命中、无spill且COPY字节相同；资源序列的收益发生在执行优先级改变后。
  它支持利用M/V管线结构的方向，不能归功于Cache或宣称已证P3最优。
- 044仿射方案的命中率下降但Makespan改善，同时spill从2887424降至1388544字节。
  当前控制没有进一步拆分管线/内存的单独因果贡献；已经足以反驳只按命中率筛选。
- 080仿射方案P2从111466增至112445，P3从90736降至83124；它还增加229376字节spill。
  因此P2排名和零spill均不能作为P3候选的硬淘汰条件。整体最好仍以P3 E0为准。
- 本实现参考了Pro2构造但重新固定singleton编号和mapping顺序；不是作者原plan字节复现。
  008分数与作者报告相同不证明plan身份相同；080 component与旧报告111314/90584有152周期差异，
  没有做原始plan逐事件归因，保留差异而不手改结果。

## 计时与验证边界

构造子进程外层wall覆盖解释器启动、import、读图、结构检测、分核、优先级生成、结构校验、
计划落盘和退出；本批约28–32ms，每候选仅一次，主机未独占，不能当稳定延迟分布。
结构校验不是完整执行证明；上表的完整合法性来自另列的外部E0。
官方复评墙钟单列于metrics.csv；当前没有E2、没有在线评分，也没有把3候选择优隐藏到生成时间。

原始实验驱动从main内开始到原始结果/账本输出为 {run['elapsed_seconds']:.3f}s，
这不是完整研发或出版耗时：不含环境安装、编程、此前只读准备，以及后续分析、制图和发布；
这些研发工作没有合为一个可靠外层计时。该数字也不包含实验驱动自身启动/import，不作为solver速度。
300秒保护作用于这次原始批处理；后续报告生成零新E0，单独执行。
单个官方评价进程峰值RSS最大 {max(r['max_rss_bytes'] for r in run['records'])/2**20:.2f}MiB；
没有测父子总RSS硬上限，不能把这一数字当整个开发环境占用。

运行环境：Python {run['python'].split()[0]}，{run['platform']}；依赖uv.lock固定。
首次提取并核验114份来源文件/100图字节，本次仅评价上述3图4核，不是全100图/1–5核验收。
没有最终平均加速比、泛化结论、Windows独立验收或真机结果。E2 P23只读接口已对齐，尚未接入。

## 复现与下一步

先 `uv sync --locked` 和 `uv run python scripts/a_materials.py --extract`。
结构检查：`uv run python -m unittest discover -s tests/q3 -v`。
重新测量须用新目录，不能覆盖本批证据：
`uv run python -m src.q3.experiment results/a/q3-nikolastarx/NEW_RUN`。
只读结果核验和制图（零E0）：
`uv run python -m src.q3.report results/a/q3-nikolastarx/pilot-20260924 figures/a/q3-nikolastarx/pilot-20260924`。

下一步优先从真实只读输入共享关系设计分核与相位，减少复制/首次同刻miss，
并用Cache完成时插入和FIFO驱逐检查候选机制；不能主动修改硬件Cache策略。
资源序列可交Q2作为受守卫的候选构造；A的Task门控须另测。更大预算或E2集成不由本批余量自动触发。

论文用语：在三个公开开发用例的四核控制实验中，结构化优先级构造相对分量顺序基线降低了
官方P3完工时间；同计划的无Cache/有Cache对照还展示了候选排序反转及命中率与完工时间不一致。
这些结果支持联合考虑管线、局部存储和Cache事件，而不是把某一代理量视为最终目标。
样本为机制导向开发选择，尚不能据此估计全用例平均收益。
'''
    (args.run / "REPORT.md").write_text(report)
    print(json.dumps({"rows": len(rows), "formal_calls_verified": len(run["records"]),
                      "new_evaluator_calls": 0}))


if __name__ == "__main__":
    main()
