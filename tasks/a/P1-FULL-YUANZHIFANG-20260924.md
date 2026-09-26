# P1 全量结果核验与统计共享

1. **任务目标**：按本人用户要求把 P1 情况全部计算并通过 Git 仓库共享。准备期间队长发布了完整 fixed64 批次，故优先核验并统计现有 100 图 × 1–5 核的 500 格，不重复启动先前计划的 search32 批次。算法身份不混用。
2. **输入文件**：固定提交 `6664a63adc3464d28d1f835d907cdeaea23e6b35` 的 `results/a/local-p1-fixed64-20260924/20260924T1337Z-s59ee/`、冻结 source-manifest 与原图；该提交内的 100 份官方单核分母（原发布 `b0937de5b97cb2e85fda68d702c8076457993588`）。算法是 `4dff90ef699fd51845cf482951e8477066f5f566` 的 `search.py propose --kind fixed64 --seed 0`，不是同文件的 32 候选 search 入口。
3. **输出要求**：可重放只读核验脚本、逐格 CSV、100×5 矩阵、逐核统计、退化清单、逐文件哈希来源清单及简短报告；提交本人分支和 PR，并在 Issue33 通知队长与队员。
4. **限制条件**：只写 `src/analysis/p1_full_yuanzhifang.py`、对应 `tests/analysis/test_p1_full_yuanzhifang.py`、本任务卡和 `results/a/p1-full-yuanzhifang-20260924/`。新增 solver/E0/E1/E2 均为 0。原件只读，不改算法/官方配置/中央成绩台，不动其他会话在途进程；不启用 Actions。整批检查失败就保留错误，不部分补零或伪造成功。
5. **验收标准**：精确覆盖 500 个唯一格、100 个有效分母；全部最终 plan/result/run 哈希和冻结身份一致；完整 JSON 数值及类型一致；静态计划覆盖/唯一调度/依赖与执行顺序检查通过；均值为逐例 B/M 算术平均，实际 solver k1 与官方曲线锚点分开；求解墙钟与外评分开。原件核验不代替独立官方复跑或科学终验。
6. **截止时间**：本轮完整核验后立即发布；如传输或原件不齐如实报告缺口。用户未另设硬截止，不将旧失败预算重置为新运行。

实际交付按两个状态报告：500 格统计与 100 分母已完成核验的薄表先共享；完整 500 个分子原件静态审计仍以第 5 项为标准，未完成不标通过。完整快照传输超时不阻塞真实薄表共享，也不放宽原件/科学验收要求。

执行会话：`yuanzhifang30-sudo/s-e777d827b5af4adfafd148ff3a4fae8b`，[fork 登记与身份纠正](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5815778625)。原 s-c909 继续负责本机网站；本分叉只做 P1 测算。
范围调整与来源：[Issue33 固定说明](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5815529496)。P1 算法写权仍归队长 s6607，本会话负责测算与核验。
