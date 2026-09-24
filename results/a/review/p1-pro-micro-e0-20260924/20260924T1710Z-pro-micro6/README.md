# Pro 合成微图：6 次官方 P1 E0 验证

这批只验证合成机制，不是正式 case 性能成绩；未运行真实 case008，不生成或提交 board-feed。

- 材料固定提交：`a556d534382cc670a6e5450661da6f8adbe638ca`。原件目录：`AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607`。
- runner / manifest 冻结提交：`7752e5ce297cf50d8aa47b31b4719bc72803bc4f`。原始作者计划 01/02/03/06/07 原字节复用，只有 C 调用一次冻结 `p1_phase_cut.encode`。
- 官方代码汇总 SHA-256：`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`；配置 SHA-256：`dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。
- 执行 UTC：`2026-09-24T17:11:13.063Z` 至 `2026-09-24T17:11:13.572Z`，整批 `0.5093282079906203 s`。run_id 是稳定标签，以这些实际时间为准。
- 1 worker；每 E0 含清理 30 s（29 s 执行等待及最后 1 s 清理保留），整批 240 s；0 重试；首身份/合法性/E0/明确模型断言失败即停。实际 6/6 成功，0 failed / 0 timeout / 0 not_run。
- P2/P3 由 root 确认释放后执行，原授权保存在 `EXECUTION_AUTHORIZATION.json`；全部自有 E0 PID / process group 已退出，`resource-release.json` 为关闭执行门回执。
- `uv sync --locked --python 3.12` 成功，Python 3.12.13。共享 M5 Pro 主机，没有独占计时/加速比声明。

## 官方实测

| 合成计划 | 作者 Makespan 声明 | 官方 Makespan / cycles | partition extra / B | spill extra / B | M/V 重叠 / cycles | 外部 E0 / s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01-A-small-interface-whole | 7002 | 7002 | 0 | 0 | 0 | 0.041455709 |
| 02-A-small-interface-return-cut | 6207 | 6207 | 240 | 0 | 1000 | 0.041074250 |
| 03-A-small-interface-entry-cut | 7206 | 7206 | 240 | 0 | 0 | 0.041768500 |
| 06-B-large-interface-whole | 7002 | 7002 | 0 | 0 | 0 | 0.041124125 |
| 07-B-large-interface-return-cut | 7704 | 7704 | 120000 | 0 | 1000 | 0.038567250 |
| 09-C-skip-interface-reduce-cut | 未声明 | 4604 | 60120 | 0 | 0 | 0.040980792 |

A 小界面的返程切法相对保全链减少 795 cycles（约 11.35%），入口切法反增 204 cycles（约 2.91%）。B 大界面虽然同样产生 1000 cycles 的 M/V 重叠，却因整体执行结果变为 7704 而比保全链多 702 cycles（约 10.03%）。这是对模型预测的官方复现，不据此将额外周期全部归因于某一种调度机制。

C 在 REDUCE 后切分，Task 0 包含 compute op 2/3，Task 1 包含 4/5。切口同时跨过 tensor 10003（30,000 B，旁路至 NORMALIZE）与 tensor 10004（60 B，REDUCE 标量）；各自一写一读，完整新增边界量为 `2 × (30000 + 60) = 60120 B`。官方 scheduled 为 60,240 B，原图 COPY 为 120 B，partition / total added 都为 60,120 B，spill 为 0。C 的 4604 cycles 是本次观测，没有事先预测 Makespan。

六格 memory_dependency_count 均为 0；前五格作者 Makespan、边界搬运、M/V 重叠及零 spill / 零复用边断言均通过。C 只以完整 boundary extra 为事先断言，其他指标作为观测记录。

## 真实调用与时间范围

- 本机：6 次未修改官方 E0；0 个 solver 子进程；5 份已有计划复用；1 次 controller 内 `recognize + encode`；0 E1 / E2；无参数扫描或重试。作者历史上自行执行的 8 次模型 CLI 不计作本机调用。
- 前五格没有本次 solver wall，保留 `null`。C 的 controller 内生成耗时为 `0.009274749987525865 s`，范围含导入冻结源、读取 C 图、识别结构、一次 encode 与计划落盘；不是独立进程冷启动指标。
- 外部 E0 墙钟逐项如表，与计划构造分列。RUSAGE_CHILDREN 记录各次增量 CPU；最大 RSS 是 Darwin 的累计子进程峰值，已注明不等同单进程独立峰值。

## 原件与验证边界

`manifest.json` 保存全部 72 份材料 Git / SHA-256 收据、11 份官方代码/配置身份、固定顺序、预算与断言。准备期核对 71 项作者 SHA 清单和前五份原 receipt 的 source/input/plan/model 身份均一致。最终源相对 executed-v1 仅增加模型迭代预算守卫；本轮不执行作者模型。

每格保存 `input.json`、`plan.json`、完整 `result.json`、`trace.json`、`official.log`、原始 `e0.stdout.txt` / `e0.stderr.txt`、`e0-process.json` 和 `run.json`。`batch.json` 收录各原件哈希和实际 PID、退出码、时间；不以进程退出 0 代替结果、断言和身份核验。

只读固定 Git 核验命令（0 新 solver / E0）：

```sh
.venv/bin/python -B src/q1_benchmarks/pro_micro_verify.py <本数据完整40位提交> results/a/review/p1-pro-micro-e0-20260924/20260924T1710Z-pro-micro6
```

只支持这六份合成样例的断言。尚未证明一般输入的定理或复杂数值域等价性，也没有证明 008 可改善或全 100 图泛化。后续真实图验证需要另行冻结候选与预算。
