# P3：100 图结构覆盖与 500 格下界核对

2026-09-24 静态分析；1 worker；solver/E0/E1/E2 均为 0。逐图读取冻结原件，仅调用 `SharingIndex`、`stage_structure` 和 `resource_choices`，没有生成方案或调用 build/derive。100/100 图于 15:25:31–15:25:54 UTC 完成，分析墙钟 22.364630 s、外层 22.841430 s，未触及 120 s 上限。这里的时间是结构分析开销，不能替代求解器端到端墙钟。

逐图 SHA、计算节点/边、弱分量尺寸、入出度直方图、每 Pipe 工作量、共同输入量、守卫、资源公式以及 500 个配对明细见 [紧凑数据](structure-inventory-100.json)。本地检查脚本与检查点保留于 `output/q3-research/goal-inventory/structure-100/`，未把重复 API 原响应提交到仓库。

## 结构覆盖

冻结来源：`baseline.py`/`construct.py` = `8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6`；`active_stages.py` = `bb7a7e8702b636a0a9dda33d070daad5f4d7c212`。数据文件记录源码字节 SHA、官方 aggregate/config/manifest SHA。

active_stages 守卫通过 8/100 图；66 图无全作业共同输入，26 图含非串行分量。全部分量均为串行链的图共 11 张；有分叉的图 82 张、有汇合的图 98 张（两类可重叠）。最大 eligible ops 为 35,705，最大弱分量为 19,737 节点。

| 图 | 弱分量数 | 最大尺寸 | 全作业共同输入/B | 请求 1/2/3/4/5 核时所选活跃核 |
|---|---:|---:|---:|---|
| 001 | 200 | 3 | 1152 | 1/2/3/4/5 |
| 036 | 800 | 3 | 1152 | 1/2/3/4/5 |
| 044 | 11 | 124 | 930400 | 1/2/2/2/2 |
| 046 | 8 | 124 | 930400 | 1/2/3/4/4 |
| 067 | 71 | 124 | 3721600 | 1/2/3/4/5 |
| 073 | 39 | 124 | 3721600 | 1/2/3/4/5 |
| 083 | 31 | 124 | 930400 | 1/2/3/4/5 |
| 092 | 142 | 124 | 930400 | 1/2/3/4/5 |

资源公式为各候选活跃核数的 `max(compute_pipe_load, all_miss_copy_service)`；完整逐核值在 JSON。它是分派启发式，忽略实际重叠、Cache、排队和容量行为，不能当作官方 Makespan 或数学下界。结构覆盖说明串行同构链方法只覆盖小部分图，后续需直接处理分叉/汇合 DAG。

## 下界与已接收成绩

使用 15:11:27 UTC 抓取的中央成绩台镜像（生成于 14:55:24 UTC，snapshot `f8ae9d66a149c8994d10935d858f1f51b571396a5566a63e911ee1853362846d`）。取 P3 每图/核历史最佳，共 100×5=500 格；这是一组历史最佳组合，不是单一求解器的全量运行。中央标记 eligible 不表示本机重新验证了全部方案原件（`verification_location=central`，`local_artifacts_verified=false`）。15:17 的 044 active 新结果不在此冻结快照中。

`B` 直接来自本机既有官方单核 scene A 的 `result.json.gz`，逐图核对原件 hash 和 run 中的 graph/config/official 身份；没有用发布 ratio×T 取整推导 B。另将发布 ratio×T 与原始 B 比较，最大浮点误差 < 7.46e-9 周期。500 格均核对图/config/official 身份；下界的 eligible ops/Pipe 工作量也与本次独立结构扫描一致。

| 核数 | 配对数 | 当前 mean(B/T) | mean(B/LB) | mean(T/LB) |
|---:|---:|---:|---:|---:|
| 1 | 100 | 1.087010856 | 1.242987859 | 1.144961162 |
| 2 | 100 | 1.900466833 | 2.483347968 | 1.418149157 |
| 3 | 100 | 2.620382628 | 3.710391441 | 1.697702905 |
| 4 | 100 | 3.222339715 | 4.931893925 | 2.034335190 |
| 5 | 100 | 3.729754388 | 6.109738937 | 2.381899165 |

所有均值均为逐图比值的算术平均，不使用总时间相除。500/500 满足 `LB ≤ T`，没有到达下界的格子。若 LB 确为有效必要下界，则 B/LB 是该图最优质量加速比的乐观上界；它不是已实现成绩，也不保证可达到。仅验证 `LB ≤ T` 不能证明下界本身正确。

输入下界文件 SHA-256 为 `230d04b0ad062a31637771717f51f9158fef2245197b12768386617c4fa72100`。该现有文件没有记录 as-run 源提交和官方 aggregate；当前 `lower_bounds.py` 最后提交为 `dcaaff9f9ed4f1d27f252e44c1e9ea07f7b6c729`，本次记录当前字节 hash，但不把它冒充旧分析时已固定的版本。没有改动下界代码或数据。

后补执行来源：根会话确认本轮先提交上述 `dcaaff9` 再执行下界生成（exec session 69239），终端报告500行、49.296399秒；文件内计至写出前49.288234秒。对应源码当前字节与该固定Git blob逐字节相同。新增 [provenance sidecar](lower-bounds-100.provenance.json) 记录此次执行依据及冻结官方身份；原JSON和上述子代理初审记录保留，不重跑、不把500次必要界计算计作solver/E0。

按 4 核 T/LB 排序，缺口最大为 071（5.809）、069（5.759）、005（5.663）、086（5.659）；这些是优先研究的结构线索，较松的下界也可能放大缺口。它们并不授权额外实测，下一批以独立冻结 spec 为准。

## 成绩来源

逐格 winner record ID、算法名和下列 source index 均保存在 JSON：

- 0: [results/a/local-p3-20260924/20260924T1331Z-s59ee/board-feed-full500.json](https://github.com/huaweibei123/huaweicup2026/blob/ba99b74b523f93a4002cd88970ec7164076d8008/results/a/local-p3-20260924/20260924T1331Z-s59ee/board-feed-full500.json)
- 1: [results/a/p123-multicore-20260924/submissions/20260924-cases001-010/board-feed-20260924T133700.533615Z-cf4c0ea0d79a-001.json](https://github.com/huaweibei123/huaweicup2026/blob/fd0a78b3f3e62357a3c04ebb77c1e7796b93dad9/results/a/p123-multicore-20260924/submissions/20260924-cases001-010/board-feed-20260924T133700.533615Z-cf4c0ea0d79a-001.json)
- 2: [results/a/q3-nikolastarx/feedback-20260924/board-feed-20260924T1414Z-complete.json](https://github.com/huaweibei123/huaweicup2026/blob/78aeda4e18ffe64adead9644a2369f3358bafcaf/results/a/q3-nikolastarx/feedback-20260924/board-feed-20260924T1414Z-complete.json)
- 3: [results/a/q3-nikolastarx/capacity-20260924/board-feed-20260924T144104Z-complete.json](https://github.com/huaweibei123/huaweicup2026/blob/eb58910b7b4d6ee7f5725fdf9bd4e0bcc6acb315/results/a/q3-nikolastarx/capacity-20260924/board-feed-20260924T144104Z-complete.json)
- 4: [results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json](https://github.com/huaweibei123/huaweicup2026/blob/46c709228c0a83e09c13b008e919d135100b938e/results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json)
- 5: [results/a/q3-yuanzhifang/stages-20260924/board-feed-20260924T142449Z-stages.json](https://github.com/huaweibei123/huaweicup2026/blob/5f137e14f5bc73d123c53401737e2b5dc62e66d2/results/a/q3-yuanzhifang/stages-20260924/board-feed-20260924T142449Z-stages.json)
