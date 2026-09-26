# 四份既有 P3 原件：管线下界与 COPY 等待诊断

范围仅为 069/071 的 DAG k5、044 的 active/pipeline k4；没有生成新方案，没有调用 `_build_scene_b_tasks`、Step2/3 或 evaluate。solver/E0/E1/E2 均为 0；静态 `derive_multicore_plan` 仅校验四份已经存在的计划。

单 worker、低于普通优先级，60 s 墙钟 watchdog；实际外层 8.690958 s、分析墙钟 7.667481 s、Python 进程 CPU 0.703125 s。CPU 不包含 Git 原件读取子进程，外层墙钟包含。分析时间为 2026-09-24T16:00:42.025710+00:00 至 2026-09-24T16:00:49.692494+00:00。网络取源码发生在分析前，不属于 solver 时间。

## 固定来源与守卫

复用队长 [pipe_bound.py](https://github.com/huaweibei123/huaweicup2026/blob/eb58910b7b4d6ee7f5725fdf9bd4e0bcc6acb315/src/q3/pipe_bound.py) 及其 [适用范围与证明](https://github.com/huaweibei123/huaweicup2026/blob/eb58910b7b4d6ee7f5725fdf9bd4e0bcc6acb315/docs/a/q3/PIPE_BOUND.md)，固定提交 `eb58910b7b4d6ee7f5725fdf9bd4e0bcc6acb315`。本工作树没有 `src/q3/construct.py`，只将 `.construct` 导入替换为已固定的 `src.q3_yuanzhifang.baseline`；算法函数未改。原模块 SHA `656865f7b124dd546f45d961819c67a6c72c8da4fede9c8cb50df9fe67465d26`；适配 SHA `6c0409a2af4ce0a57883f9d514ece69916724755b61fa26624be33526892bc3a`。源/适配/驱动脚本留在项目外指定任务临时目录，JSON 记录字节 hash。

每份 feed、plan、result、trace 均与其固定 Git 提交逐字节相等；图、配置及冻结官方源码逐项核 SHA。四份均满足 singleton 原计算 M/V、非负整数时长、真实 eligible 依赖守卫；没有把 COPY 收缩新边无条件当作官方依赖。全部 36 组每核 M/V 提交投影与 result 操作序逐 ID 一致；result 中每条操作的开始、时长、Pipe 又与原 trace 核对一致。

| 计划 | 固定原件提交 | 结果入口 |
|---|---|---|
| 069 / dag_chain_list / k5 | `dfecc02387060fda5105d2c6e35aabc0b4459440` | [result.json.gz](https://github.com/huaweibei123/huaweicup2026/blob/dfecc02387060fda5105d2c6e35aabc0b4459440/results/a/q3-yuanzhifang/dag-list-20260924/069/dag_chain_list/P3/result.json.gz) |
| 071 / dag_chain_list / k5 | `dfecc02387060fda5105d2c6e35aabc0b4459440` | [result.json.gz](https://github.com/huaweibei123/huaweicup2026/blob/dfecc02387060fda5105d2c6e35aabc0b4459440/results/a/q3-yuanzhifang/dag-list-20260924/071/dag_chain_list/P3/result.json.gz) |
| 044 / active_stages / k4 | `738e2c3b274140a7ceea08d83a365282238e84c7` | [result.json.gz](https://github.com/huaweibei123/huaweicup2026/blob/738e2c3b274140a7ceea08d83a365282238e84c7/results/a/q3-yuanzhifang/active-20260924/044/active_stages/P3/result.json.gz) |
| 044 / pipeline_stages / k4 | `e6b5500dcbf3818034804168ee79d0f65c16706b` | [result.json.gz](https://github.com/huaweibei123/huaweicup2026/blob/e6b5500dcbf3818034804168ee79d0f65c16706b/results/a/q3-yuanzhifang/pipeline-20260924/044/pipeline_stages/P3/result.json.gz) |

逐项身份、36 组投影 hash、完整 L0/L500 最长路径、MTE2 首操作、最大等待和阻塞序列见 [trace-feedback.json](trace-feedback.json)。

## 对当前计划有效的必要下界

L0 保留真实计算依赖与提交次序的 M/V FIFO 边，忽略 COPY 服务；L500 额外加入冻结配置的跨核 500 周期间隔。重复约束取 max；COPY 服务、Cache/DDR 竞争与内存补边均不计入。下界针对当前计划，不能当作所有可能计划的全局最优，也不单独证明容量合法性。

| 计划 | L0 | L500 | 官方 T | T−L500 | 最大 COPY 释放后等待 |
|---|---:|---:|---:|---:|---:|
| 069 dag_chain_list | 6461 | 11166 | 16554 | 5388 | 9699 |
| 071 dag_chain_list | 5657 | 8429 | 12149 | 3720 | 4656 |
| 044 active_stages | 41290 | 41290 | 44185 | 2895 | 0 |
| 044 pipeline_stages | 27142 | 28642 | 40927 | 12285 | 18537 |

四份均为 L500≤T。044 active 的当前计算/FIFO 下界已到 41,290，离 44,185 尚有 2,895；仅压缩搬运不能突破该计划的计算/FIFO约束。pipeline 的 L0=27,142 恰与其抽象 flowshop 数字一致，加入真实跨核间隔后为 28,642；官方 40,927 仍比此必要下界多 12,285。差额不是已证明可消除的延迟。

## MTE2 启动与忙时

以下向量按核心编号从 0 递增。`—` 表示空核无该事件。权重以“无 eligible 生产者、至少两个 eligible 消费者的原 tensor”作结构代理；不声称文件给出了语义权重标签。忙时为该核 MTE2 所有已观察 COPY 时长之和，已核对同 Pipe 无重叠。

| 计划 | 各核首 MTE2 时刻 | 各核首共享输入时刻 | 各核 MTE2 忙时 |
|---|---|---|---|
| 069 dag_chain_list | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | 4317 / 3010 / 3907 / 3883 / 5662 |
| 071 dag_chain_list | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | 3650 / 2584 / 3344 / 2728 / 2675 |
| 044 active_stages | 0 / 0 / — / — | 0 / 0 / — / — | 31395 / 31391 / 0 / 0 |
| 044 pipeline_stages | 0 / 0 / 10560 / 19742 | 0 / 0 / 10572 / 19760 | 693 / 7818 / 8601 / 1082 |

044 pipeline 核2首队头 `COPY_IN #1000001622` 的源 COPY_OUT 在 10,060 完成，外部释放=10,560；目标恰在 10,560–10,566 执行。随后 `#1000001619` 到 10,572，第一份共享输入 `#1000001548` 才于 10,572 开始。核3对应首队头 `#1000001628` 的源在 19,242 完成，释放=19,742，执行至19,751；随后另一跨核 COPY 到19,760，共享输入 `#1000001574` 于19,760才开始。

此两条链证明当前已观察 FIFO 队列具有很晚的首队头释放约束。官方 P3 `queue_if_ready` 只允许当前 Pipe cursor 入队，`advance_pipe` 在队头完成后唤醒下一项，因此后面的独立权重不能在当前队列中越过该队头。原件没有提供全部 Step3 内存边，本诊断没有重建它们；其他等待的具体成因不能仅由时间先后唯一确定。

## 释放后等待与前驱证据

| 计划 | 跨核 transfers | 释放后有等待 | 其中前一个 MTE2 也是跨核 COPY |
|---|---:|---:|---:|
| 069 dag_chain_list | 391 | 239 | 220 |
| 071 dag_chain_list | 214 | 114 | 95 |
| 044 active_stages | 0 | 0 | 0 |
| 044 pipeline_stages | 110 | 84 | 78 |

- 069 核3：目标 `#1000001420` 已于1,240释放，却到10,939才开始，等待9,699。其紧前 MTE2 `#1000001408` 的源核1 COPY_OUT 到10,413才结束，释放10,913，执行10,913–10,939；后项恰接前项完成。这是明确的“早释放 COPY 排在晚释放 COPY 后”的当前 FIFO 约束。
- 071 核0：最大等待为目标 `#1000001050`（释放2,287，执行6,943–6,988），紧前项为共享输入 `#1000000951`（6,807–6,943），因此不能把最大等待误报成紧邻一个跨核 COPY。再向前的实际链包括跨核 `#1000001515`（释放6,519，执行6,519–6,559）、`#1000000835`、`#1000000876`、`#1000000941`、`#1000001011`、`#1000000951`，完整逐项时刻保留在 JSON。
- 044 pipeline 核3：目标 `#1000001601` 的源在1,019结束、1,519释放，但到20,056才开始，等待18,537。紧前为权重输入 `#1000001588`（20,051–20,056）；更早的整个 MTE2 队列因首跨核队头19,742才开始。第二大等待的目标 `#1000001635`（3,472→21,647）紧前则确为跨核 `#1000001638`（21,629–21,647，释放4,214）。

各 transfer 的等待可能在时间上重叠，不能相加为总延迟，也不能从最大等待直接推出 Makespan 可降低多少。等于前项完成时刻证明当前执行满足 FIFO 的必要顺序；调换计划后 DDR 竞争、Cache、容量和原计算顺序都可能变化，因此不是反事实性能证明。

研发含义：DAG 的大缺口需要同时看真实计算/FIFO 依赖与输入队头释放；pipeline 的独立权重晚入说明可研究能让官方生成较早预取序的合法提交顺序。可提交自由度仍只有分图、分核和子图顺序，不能直接篡改官方 COPY 队列。本报告没有生成该候选或追加评分。
