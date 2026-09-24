# Q3 迭代 02：balanced 与 fragment 的独立直接构造对照

fragment 在 6 组配对中 **2 组改善、4 组退化**。12 个独立求解均通过官方 P3，实际 12/12 次 E0，0 失败、0 重试、0 E1/E2。没有选择性删除负结果，也没有继续追加参数或样本。

源码固定为 `b84e3670452603af1f08169f4dfb5809df8cd31a`。本批每种方法每格只构造一个方案并调用一次在线 E0；下表是**两个独立求解器的事后对比**，不是在线二选一算法，也不保证相对旧 `safe_solve` 或 balanced 不退化。

## 六组逐项对比

ΔMakespan = (fragment − balanced) / balanced；负值表示 fragment 改善。Makespan 单位为模拟 cycles，wall 单位为实际秒。每个表格单元对应一次独立 solver 进程和一次 E0。

| case | 核数 | balanced cycles | fragment cycles | ΔMakespan | 结果 | balanced wall s | fragment wall s | E0 次数 B/F |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 002 | 3 | 93527 | 119342 | +27.60% | 退化 | 0.154458 | 0.157018 | 1 / 1 |
| 002 | 5 | 85129 | 67948 | -20.18% | 改善 | 0.155110 | 0.163987 | 1 / 1 |
| 062 | 3 | 1342199 | 1183248 | -11.84% | 改善 | 3.877716 | 3.652592 | 1 / 1 |
| 062 | 5 | 673177 | 1010340 | +50.09% | 退化 | 3.138417 | 3.644704 | 1 / 1 |
| 063 | 3 | 399671 | 422182 | +5.63% | 退化 | 1.103262 | 0.967421 | 1 / 1 |
| 063 | 5 | 336337 | 340898 | +1.36% | 退化 | 0.819901 | 0.811593 | 1 / 1 |

002 五核和 062 三核得到改善；002 三核、062 五核及 063 的三核/五核均退化。最大退化发生在 062 五核，673177 → 1010340 cycles（+50.09%）。因此不能把 fragment 当作 balanced 的普遍替代。

## 搬运与机制反馈

12 个结果的 spill_added_copy_bytes 均为 0、官方按字节 Cache hit_rate 均为 0。两组改善不能解释成 Cache 命中率提高；负结果也不能归因于新增 spill。fragment 在六组中都增加了切分额外搬运，而质量有升有降，说明搬运量本身也不足以决定胜负。

| case | 核数 | balanced 额外搬运 bytes | fragment 额外搬运 bytes | 增量 bytes |
| --- | ---: | ---: | ---: | ---: |
| 002 | 3 | 6144 | 30720 | 24576 |
| 002 | 5 | 12288 | 67584 | 55296 |
| 062 | 3 | 6144 | 33792 | 27648 |
| 062 | 5 | 12288 | 76800 | 64512 |
| 063 | 3 | 6144 | 27648 | 21504 |
| 063 | 5 | 12288 | 70656 | 58368 |

这里的额外搬运是官方 added_copy_bytes；CSV 的 scheduled_copy_bytes 是调度搬运总量，不冒充实际物理 DDR 流量。

062 五核的构造收据记录：balanced 最大核计算负载为 707868 cycles，fragment 降至 619440 cycles，但官方 Makespan 反而增加 50.09%。这否定了“只要降低计算负载不均衡，就一定改善官方 Makespan”的直接推断。固定阈值碎片化与 LPT 的计算负载界并未包含跨核依赖等待和 COPY/FIFO 带来的时间；具体退化原因仍需读已保存时序逐项解释，不能只凭这张表宣称单一因果。

## 实际成本与限制

- T0：`2026-09-24T14:39:37.925305Z`；结束：`2026-09-24T14:39:58.053064Z`。
- 整批跨度 **20.127765 s**；12 个 solver 进程 wall 合计 **18.646179 s**。二者不混用：整批还包括固定版本预检、逐项审计和父进程收尾。
- 每个 solver wall 覆盖新解释器启动、读图、Index/构造、一次在线 E0、全部必要证据与最终计划落盘及进程退出。外部独立最终评价未另跑，evaluation_wall_seconds 留 null。
- CSV 中 construct_seconds 和 evaluation_seconds 是 solver 内部分段诊断，后者覆盖完整 evaluate_problem_3；它们不能代替完整进程 wall，也不能再加到已经包含它们的 solver wall 上。
- 预算为新阶段 12 E0、1 worker、每 job 90 s、整批 900 s；实际恰好使用 12 E0。旧阶段封存额度未恢复。未执行额外单核或 P2 对照。
- 环境：Apple M5 Pro，macOS-27.0-arm64-arm-64bit，Python 3.12.13，RAM 51539607552 bytes；不使用 GPU，workers=1。线程数及单进程峰值 RSS 未采样，留 null。
- 主机非独占，操作系统缓存状态未知，每个方法每格仅观测一次。wall 的差异只作本次观测，不能据此宣称稳定尾延迟或严格跨批提速。
- 三个图均为已见公开开发图，仅 3/5 核；不是全 100 图、1–5 核或独立平台验收。
- 官方单核分母从已有固定原件逐字节复制并核 SHA；来源链保存在 run/baselines.json。没有新的单核评价。没有同计划 P2 配对，cache_pair 保留 null。

## 可追溯入口

- [12 行完整数值表](metrics.csv)：每条包含最终 Makespan、完整 solver wall、构造/E0 内部时间、真实调用和搬运/命中。CSV 保留浮点原始精度，报告展示值仅作排版。
- [实际批次与每条收据索引](run/batch.json)：实际 argv、输入/config/official SHA、代码版本、环境、完整 source_input_sha256、预算与所有状态。
- [正式执行清单](manifest.run.json)；[运行前协议](../../../../docs/a/q3/FEEDBACK_ITERATION_02.md)，包含从未运行 capacity 方案改为 fragment 的静态依据和 0 E0 边界。
- [完整成绩台 feed](board-feed-20260924T144104Z-complete.json)；[生产端预检](preflight-complete.json)：valid/submission=true，12 records、12 eligible、无待核或失败。
- 每个 `run/cells/<case>-k<cores>-<variant>/` 下保留官方两字段 plan、完整 E0 gzip、receipt、evaluations ledger 和 stdout/stderr；官方 JSON 未改写。

本报告只读取现存原件并计算差值，新增 E0/E1/E2 均为 0。工作树原件预检不等于中央服务已接收、页面入榜、独立复跑或算法终验；这些状态以接收方回执为准。

输入 run/batch.json SHA-256：`e15ffab29459601d7e967ff6f9ae6c690e3e04f1d059f2cd28b23e56566c252a`。
