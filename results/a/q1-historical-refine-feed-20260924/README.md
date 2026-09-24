# P1 历史 profile-refine 原件补证

本目录为 **零重新评估的历史导出**，不是新实验。新目录日期只用于归档；原运行 UTC 未记录，`observed_at/started_at/finished_at` 均为 null。成绩台 feed 为 [`board-feed-historical-refine.json`](board-feed-historical-refine.json)，保留原三格尝试，无新 attempt 运行时刻。

| case / 核数 | 原种子 Makespan | 最终 E0 Makespan | 监督的局部改进阶段秒数 | 完整 raw→final 求解墙钟 |
|---|---:|---:|---:|---|
| 002 / 4 | 88636 | 88188 | 1.8567057089821901 | 未记录，null |
| 044 / 4 | 116227 | 114443 | 1.3611342910153326 | 未记录，null |
| 051 / 4 | 338698 | 336057 | 2.478636749990983 | 未记录，null |

阶段计时包含历史种子的 E0 确认、2 轮最多 8 个新候选、9 次 E1（含种子）、最终 E0 确认以及监督进程启动/收尾；不包含已有种子的生产。函数内部 `total_seconds`、搜索子阶段与最终 E0 分别保存在 [`provenance-summary.json`](provenance-summary.json)。`metrics.solver_wall_seconds` 不填上述任一阶段值。`metrics.evaluation_wall_seconds` 对应历史最终 E0 确认阶段，已包含在局部改进计时中，不能再次相加。

## 原始来源与版本区别

- 首次保存全部本批证据的提交：`909f6f1f29fc7f2557395fae98f0f68a853f4c4b`，目录 `results/a/q1-profile-refine-20260924/`。导出器只从此固定提交读，不使用导出 HEAD 伪装运行版本。
- 原 `protocol.json` 的运行时基础 HEAD 为 `95bca21e3bf211caf975652d82f7f4e331ec44cd`。当时的新实现有完整五文件 `source/` 快照及 SHA-256。feed 的 `solver_commit` 指上述 **as-run 快照的归档提交和明确 source 路径**，不是说运行时 checkout 已在该提交，也不是把后来 `src/q1/profile_refine.py` 当作实际运行文件。
- 实际运行 `profile_refine.py` SHA-256：`fa632a1eba391358536c287b648b9a4ab7c0b24f90bb16e5dd91b02b4b7296a5`。交付前原子写入加固后的文件为 `b22582f6ff2d06ee02e482b739001fdb91836a04a3d327b7b77299e2ab7928d3`；原 `postrun_hardening.json` 明确没有重跑质量实验。不能使用后者冒充 as-run。
- 五个 as-run 文件全部与协议哈希核对。归档快照用于精确识别实际实现；它们仍依赖原项目目录结构，不宣称在 `source/` 内直接运行即可复现。
- 原种子来自 `results/a/q1-guided-moves-20260924/case<id>/guided/best_plan.json`；导出核对它与旧 `seed.json` 字节相等。该批种子首次归档于 `78105c7394c5ae2014970e6efccf3dcbb5618072`。
- 最终评价为官方 E0，内部候选评分使用固定 E1 `5bfe53a29c1ba05167239f51ea937e602f7f85b4`。原官方源码聚合身份为 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，由冻结 source-manifest 定义，不另造聚合算法。

## 方法的真实范围

`profile_refine.py` 的 CASES 固定为 044、051、002；`refine()` 先读取现有 guided-moves 计划。`profile_candidates.py` 编译实际 Task 得到 Step1 顺序、峰值/溢出和边界信息，优先生成 split 以及满足完整增广 Task DAG cover 条件的同核 merge，保持映射顺序，候选最多 4 个/轮。E1 按 `(makespan, scheduled_copy_bytes)` 选优，再用原版 E0 确认。

这是已有计划的局部改进，不是从 raw 图启动的全图通用求解器，也不是三格之外的质量证据。每例还做 2 次局部 Task profile 编译，单列记录，不把它混称完整 E0 调用。以上历史调用与本次导出的 0 调用严格区分。

## 原件与缺口

每格 `plan.json`、`run.json`、`seed.json` 均逐字节复制自固定历史原件。`result.json` 从原 `execution-evidence.tar.xz` 的 `e0_final/result.json` 定点读取；同时验证归档压缩字节 SHA-256 和清单中展开成员 SHA-256，保留原始 JSON 字节、类型和完整内容。没有裁剪、重写官方结果。

原运行只有 macOS/架构、Python、锁文件 SHA、worker=1、抽样进程组 RSS 和相对计时。CPU、GPU、RAM、线程数、UTC、冷热状态与确切 argv/cwd 未记录，保留 null/空 argv 并逐项解释。`repeat_index=0` 是原一次 CASES 遍历中该 case 唯一收据的索引，不是新重复实验或推测运行时刻。未擅自补入单核分母；维护者可复用相同冻结身份的已核分母。

## 验证与交接

重建导出（不会启动 solver/evaluator，也不会覆盖不一致的既有产物）：

```sh
python3 -B results/a/q1-historical-refine-feed-20260924/export.py
```

本地预检使用成绩台维护代码 `3f0004815ca1c8f1af14b4f77db652caa98b37ac` 的 `src/benchmark_board/protocol.py`，以本 worktree 为 `--repo`，传入上述 feed 和 `--submission`。结果见 [`preflight.json`](preflight.json)：`valid=true, submission=true, records=3, eligible=3`。此预检只读格式和原件，在临时账本验证，没有写中央成绩台，没有重新运行算法，也不等于独立复跑或算法验收。

本导出新启动次数：solver=0、E0=0、E1=0、E2=0。原历史每例 2 次 E0、9 次 E1 的成本仍在 feed，不用导出零调用覆盖历史成本。原件、当前 feed、所有引用均在同一新交付提交内可读。

## Revision 2：补齐已存在的官方单核分母

维护者指出胜出记录需要自己附身份匹配的分母，不能从被替代的旧记录继承。
[`board-feed-historical-refine-r2.json`](board-feed-historical-refine-r2.json)
因此保留同三个 `attempt_id`，仅升 `revision=2`、添加 baseline 原件及说明。
原 revision 1 保留，历史求解墙钟仍为 null，全部 metrics 和运行来源不变。

`add_baselines.py` 从固定 `6664a63adc3464d28d1f835d907cdeaea23e6b35`
的 fixed64 feed 定位已发布 official-singlecore 原件，逐一核对 graph/config/official
三项身份及压缩文件 SHA-256，将原字节复制到 `baselines/`。这不是从 fixed64
Makespan 构造分母，也没有重新评分。002、044、051 分母分别为 261945、154407、607628。
维护者当前协议的本地预检为 3 条全部有效；原件一致不等于独立科学验收。
