# 008 / k4 合法退化：成绩台历史导出

本目录只导出现有原件，新增 **0 solver / 0 E0 / 0 E1 / 0 E2**。本次实际实验仍是原 run `20260924T1720Z-pro008-auto` 的一次 solver + 一次 E0，不因导出建立新尝试或新评分批次。六个合成微图不在此 feed。

- feed：`board-feed-20260924T1730Z-pro008.json`，board-submission-v1，1 条，revision=1。
- algorithm_id：`q1-one-cut-return-rotation-candidate`；variant：`auto-candidate-without-adoption-gate`。这是直接 auto 实验候选，不是 integrate fallback 或默认生产算法。
- 原始 source：`a556d534382cc670a6e5450661da6f8adbe638ca`；实际 runner：`dfa8de323b1b24087cfda02c25de9b0652b32f60`；原始 data：`3dd923a86ce97480c37edf749806255eab33a6e9`。三者与后续导出提交分开。
- 新方案官方 Makespan **162326 cycles**；旧 bounded 的 123060 仅作同格历史比较，退化 **31.90801235%**。extra DDR **3244032 B**，0 spill、0 MEMORY 依赖边；certificate=false，未采用为生产改进。
- 原实验 solver **0.126234875 s**、外部 E0 **0.186556125 s**。保留原始 UTC 首尾、源码清单与两个进程收据；本次导出不修改这些字段。

## 正确的官方单核分母

复用固定 `6fcec11ccc472a1a652b21feb6fccf85a4555598` 的 `results/benchmark-board/official-singlecore-20260924/008/result.json.gz` 和原始 run receipt。真实入口 `singlecore_evaluate.evaluate_singlecore`，487605 cycles，graph/config/official 三项身份与本条一致。压缩原字节复制到 references，SHA-256 与既有单核收据一致。

对应单格加速比为 `487605 / 162326 = 3.0038625974890034`，由成绩台依原件重算；**没有把旧 optimized k4 的 123060 充当单核分母**。这里只是 1 个 case/k，不是全100均值。

## 验证与交付范围

使用主目录当前 `docs/benchmarks/BENCHMARK_BOARD.md` 与 `SUBMISSION_PROTOCOL.md`；官方协议工具版本与哈希保存在 `precheck-worktree.json`。在独立 `output/p1-pro-case008-board-20260924/20260924T1730Z-export-only` 留存预检 stdout/stderr/收据；预检临时库与中央库隔离。

标准工作区预检：exit0，valid=true，records=1，eligible=1，无 reported_or_failed。固定 Git 预检另附；该检查确认格式和原件匹配，不是独立重跑或中央接收回执。

协议明确算法注册表不是新方法白名单；本条给出 source/authors/method/references，接收维护者可据此登记。导出者没有修改中央注册表、中央账本或网站，也未直接通知队友。由 root 统一发布和正式签名入队。
