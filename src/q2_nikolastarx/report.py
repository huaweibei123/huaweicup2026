"""Generate the pilot table/report without running an evaluator."""
import csv
import json
import sys
from pathlib import Path


def main():
    root = Path(sys.argv[1])
    rows = json.loads((root / "rows.json").read_text())
    protocol = json.loads((root / "protocol.json").read_text())
    summary = json.loads((root / "summary.json").read_text())
    complete = json.loads((root / "completion.json").read_text())
    with (root / "metrics.csv").open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(["candidate_id", "cycles", "partition_copy_bytes", "spill_bytes",
                         "construction_seconds", "index_seconds", "official_cli_seconds"])
        for r in rows:
            writer.writerow([r["candidate_id"], r["cycles"],
                             r["data_movement_bytes"]["partition_added_copy_bytes"],
                             r["data_movement_bytes"]["spill_added_copy_bytes"],
                             r["generation_seconds"], r.get("index_seconds", ""), r["cli_seconds"]])
    table = "\n".join(f"| {r['candidate_id']} | {r['cycles']} | {r['data_movement_bytes']['partition_added_copy_bytes']} | {r['data_movement_bytes']['spill_added_copy_bytes']} |" for r in rows)
    baseline002 = next(r["cycles"] for r in rows if r["candidate_id"] == "002-M1")
    reduction = 100 * (1 - summary["winners"]["002"]["cycles"] / baseline002)
    (root / "REPORT.md").write_text(f'''# Q2/B 联合次序首批开发检查点

002：72415 → {summary["winners"]["002"]["cycles"]} cycles，改善 {reduction:.3f}%；044最终保留既有M2的69113。本轮验证联合构造有有限收益，没有得到统一优胜策略。

真实官方开发样例002/044、4核；13次P2 E0全部成功，含3次历史基线复核、8次候选评价、2次赢家完整输出重复确认。不是合成例、不是全100图验证或数学最优性证明。E1/E2/P1/P3调用均0。

| 候选 | Makespan cycles | 分区新增COPY bytes | spill bytes |
|---|---:|---:|---:|
{table}

固定源版本 `{protocol["as_run_commit"]}`；Fang输入版本 `{protocol["seed_commit"]}`。原计划字节从Git取出，图从原ZIP成员恢复；协议保存输入/源码/uv.lock SHA-256与环境。构造/驱动代码在调用前提交。后续report.py只整理结果，不追加评价。

T0至完整机器报告/清单收尾 {complete["elapsed_seconds"]:.6f}s；13次CLI合计 {sum(r["cli_seconds"] for r in rows):.6f}s；8候选生成合计 {sum(r["generation_seconds"] for r in rows):.6f}s（索引另列metrics）。输入提取准备 {protocol["preparation_seconds"]:.6f}s在T0之前。本段不含后续人工审阅/文档/Git发布，也不含历史强种子搜索，因此不是完整求解器端到端测速，更不能与Fang Windows总耗时直接比较。单worker、30秒/次、180秒批预算、最后60秒不启动调用，13次额度已用尽，无追加重试。

结论与边界：

- 002全ready critical小幅改善；critical32组合反而72634。将现有好分核与另一现有策略组合并不保证改善。
- 044最早开始71242优于M1父74530，但仍落后另一核分配M2的69113；002同策略92004，显示忽略COPY/资源等待的计算代理不宜单独选优。
- 044-id退化125366且增加2169984 bytes spill；所有singleton候选逐操作核归属和有序mapping一致，原始父计划到singleton仍是粒度/顺序复合改动。
- 044-critical32与044-critical的计划字节相同，本批仍按预声明规则各计一次官方调用。保留这次重复成本，未称8个候选都是独立新计划。下轮应在同图/config/source身份下去重。
- 4项结构测试通过；8个候选的owner/键序、13份完整结果哈希和88项运行清单另作只读复核。两赢家完整JSON（含时间线）复跑SHA相同。尚无跨平台独立复跑或强候选同预算总求解比较。

论文可用表述：在两个公开开发实例上，以既有强核分配为种子，比较有限的计算DAG次序构造。全就绪关键路径策略使002的官方Makespan降低0.50%，044则保留原方法最佳解。最早开始代理在两例的方向相反，表明管线计算模型须结合实际COPY、内存与FIFO行为验证；该实验不支持通用性能保证。

复现与算法限制见 `docs/a/q2-nikolastarx/METHOD.md`。本目录manifest覆盖运行时产物，不包括测后生成的REPORT/metrics与completion本身；protocol/rows/summary/ledger及每次plan/result/trace/log原件完整保留。
''')


if __name__ == "__main__":
    main()
