# P2 固定算法的 1/2/4 核全量性能反馈

本报告只读已保存的 `tensor_packet` 官方 P2 E0 结果。算法固定提交 `e64723bdf99669c44f76d8e90ab0379a8578522e`，与旧连续构造固定来源逐图比较；旧来源**不是中央当前最好成绩**。每个 `(case, k)` 的图、配置和官方代码哈希与已保存的单核 A 基线逐项相同。`build_feedback.py` 读取轻量 JSON 与 solver stdout，未调用 solver、E0、Step2，未解析大体量 trace。`case-comparison.csv` 保存全部 300 行，包括收益和退化。

逐图贡献定义为 `(B/M_new − B/M_old)/100`，B 是同一图的官方单核 A Makespan；全量均值是这 100 项之和。负贡献表示新方案使均值下降。事后 `max` 包络逐图取新旧较快者，仅表示离线可见的机会量，**不是已实现的在线策略或成绩台结果**。

| 核数 | 新方案 B/M 均值 | 旧连续 B/M 均值 | 事后 max 包络 | 改善/退化/相同 | 新方案 spill>0 | 分区额外搬运>0 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.056973404 | 1.000000000 | 1.079604802 | 68 / 24 / 8 | 41 | 0 |
| 2 | 1.938126019 | 1.459837851 | 1.975783867 | 89 / 9 / 2 | 34 | 86 |
| 4 | 3.330228459 | 2.099807013 | 3.398411693 | 91 / 6 / 3 | 29 | 91 |

同一算法在各核数均有 `shared_stages` 8 图、`shared_cohorts` 53 图、`packet_eft` 36 图和 `guarded_resource_word` 3 图。来源分别为 `round6a/b/c`（单核）、`round7a/b/c`（二核）、`round4` 十图 + `round5a/b` 六十图 + 原 `round5c` 的 070 一图 + `round5c-recovery` 二十九图（四核）。原 5C 的 071 中断 solver 不作为完整测量，额外调用另在事故记录中计费。

## 对均值贡献最大的图

下表的 Δ 单位是均值加速比本身，例如 +0.01047 表示该图令 100 图均值增加约 0.01047。所有正负项及 cycles、spill、分区额外 bytes 都在 CSV 中。

| 核数 | 最大改善：case / Δ / 路由 | 最大退化：case / Δ / 路由 |
|---:|---|---|
| 1 | 044 / +0.010472 / shared_stages；084 / +0.009795 / guarded_resource_word；095 / +0.009479 / guarded_resource_word；008 / +0.009470 / guarded_resource_word | 025 / −0.003174 / shared_cohorts；036 / −0.003061 / shared_stages；013 / −0.002876 / shared_cohorts；007 / −0.002850 / shared_cohorts |
| 2 | 044 / +0.022627 / shared_stages；084 / +0.019573 / guarded_resource_word；095 / +0.018933 / guarded_resource_word；008 / +0.018835 / guarded_resource_word | 025 / −0.008558 / shared_cohorts；036 / −0.008540 / shared_stages；007 / −0.006361 / shared_cohorts；013 / −0.005468 / shared_cohorts |
| 4 | 084 / +0.039220 / guarded_resource_word；095 / +0.037682 / guarded_resource_word；008 / +0.036842 / guarded_resource_word；058 / +0.029679 / packet_eft | 025 / −0.021573 / shared_cohorts；036 / −0.021368 / shared_stages；007 / −0.014729 / shared_cohorts；001 / −0.009646 / shared_stages |

单核 24 个退化中 18 个走 `shared_cohorts`，2 个走 `shared_stages`，4 个走 `packet_eft`；21 个新方案 spill>0，3 个无 spill（035、037、061）。单核无跨核中间搬运，退化主要伴随 spill 或操作顺序变化，但相关性不证明 spill 是全部耗时的因果。最差的 025 单核从旧连续 4,863,026 cycles 变为 7,124,388，spill 103,650,816 bytes；007 和 036 分别 spill 19,345,920、15,093,760 bytes。061、035 的无 spill 退化说明同一路由的顺序策略也须保留负例；037 是无 spill 的 `packet_eft` 退化，容量窗口的路由守卫不会进入它。

二核 9 个退化中 7 个有 spill、9 个有分区额外搬运；四核 6 个退化中 4 个有 spill、6 个有分区额外搬运。分区额外 bytes 是官方输出的跨分区通信代价指标，和 spill bytes 分列，不能把 `added_copy_bytes` 全部归因于跨核搬运。037 在二核/四核均无 spill 却慢于旧连续方案，分区额外搬运分别为 204,800/614,400 bytes。025、036、007 在三种核数均显著退化且有 spill，是优先证伪容量方案的共同负例。

## 容量窗口的适用边界

独立容量原型固定于 `eb00b1c25fe92cf8b9f835a4f3e8a63ab20a90e8` 的 `src/q2/feedback/capacity_window.py`。现有 `build()` 只在原路由为 `shared_stages`/`shared_cohorts` 且 tensor 无 `logical_tid` 别名时考虑窗口；`shared_cohorts` 还可能先被重分量守卫转到 `heavy_component_packet_override`。每核必须得到 `window≥1` 且闭区间峰值不越 L1/UB 容量才有其保守内存证书。本报告只用已保存的 `selected` 元数据执行**路由门槛筛选**：三种核数各有 61 图进入路由候选，其中单核退化的 20/24 图处于候选路由。其余 4 个单核退化均走 `packet_eft`，现有窗口不会覆盖。

旧 `solver.stdout.txt` 未记录 `logical_tid` 检查、重分量判定和每核 `S+W·P`，所以 20 只是待验证上限，**不是 20 个已可用窗口，更不是 20 个预计改善**。已有 `capacity-prototype/two-case-structure.json` 对 007、025 的四核图报告窗口为3且每核顺序有变化、结构检查通过，0 次官方 E0；这不提供新的官方 Makespan。原型本身可能减少 spill，也可能因过度串行化或通信改变使 Makespan 变差。`heavy_component_packet_override` 也无容量证书，须独立判断。

## 下一轮最小可证伪集合

建议先对以下 **10 图**运行一个事前固定的新算法/参数和独立官方 E0，记录原算法、新算法与旧连续方案的逐图 Makespan、spill、分区额外 bytes、solver 端到端时间。选图仅用于研发实验，不把 case ID 或历史赢家写入生产构造。

| 图 | 选择理由与主要证伪点 |
|---|---|
| 025、007 | 三核数共同大退化、`shared_cohorts` 且大量 spill；四核结构原型已证明顺序发生变化，检查新 E0 能否实际减少 spill 与 Makespan。 |
| 036、001 | 三核数 `shared_stages` 退化且 spill；检验窗口在另一共享路线上的容量守卫及耗时取舍。 |
| 013 | 单核/二核主要损失、`shared_cohorts` 有 spill；检验窗口改善能否跨图推广。 |
| 061 | 单核无 spill 仍退化、`shared_cohorts`；防止仅凭路由或 spill 选择窗口。 |
| 037 | 二核/四核无 spill、`packet_eft` 且有分区额外搬运；作为容量窗口不覆盖的通信负对照。 |
| 050、066、068 | 四核低加速比且无 spill 的 `shared_cohorts` 大分量问题；专门检验重分量 packet override，避免将其收益归于容量窗口。 |

如某图原型守卫拒绝，记录 `guard_unchanged` 及原因，不替换图或悄悄扩大预算；所有负结果保留。首先核对窗口/override 输出结构与容量证书，再用未修改官方 E0 评测合法性、Makespan 和搬运；本报告未开展这一轮新评分。

来源入口：`goal-baseline/sources/captain-k1/board-feed-full100.json`、`goal-baseline/sources/captain-k2-k5/board-feed-full400.json`、各新批次的 `ledger.json`/`run.json`/`solver.stdout.txt`，以及 `results/benchmark-board/official-singlecore-20260924/` 的逐图 A 基线。两份旧 feed 的官方代码哈希与新批次身份逐图相同；旧测量硬件和 runner 不同，因此仅比较官方 cycles，不比较跨机器 solver 墙钟。CSV 保留每行原件路径以便复查。
