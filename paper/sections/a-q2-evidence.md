# P2 章节证据、图件占位与修订记录

本文是 [P2 章节初稿](a-q2.md) 的编辑伴随材料，不作为正式论文正文。作者会话为 `yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24`，日期 2026-09-25。用户已明确将任务调整为持续跟进算法并写 P2；此前“P1”字样是用户已纠正的笔误。

## 当前稿件采用范围

| 对象 | 固定版本/身份 | 本稿的采用方式 |
| --- | --- | --- |
| 主方法 | `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f` | 结构初解 + gap + hypergap，最多三个不同完整计划的原生 E2 评分 |
| 主结果发布 | `1c00079aadbd071de62db17686d5ba3fed1da0f2` | 完整 100×1–5 核，500 次独立 E0；并非本会话重新运行 |
| 最新已读算法资料 | `70f2e8bd8e850f1d49c924a86b654b29c24e087f`，继承 e6ae369 / afabca8 / fff17b9 | R05 配对官方负结果、完整 500 格 DDR 取舍；主算法与完整均值不变 |
| 成员 tensor/gap/F1 数据 | 读取提交 `178a3673bd238b20772211427b8134b6db35f5af` 的冻结 CSV | 各自独立固定算法的对照；F1 只列五核完整均值 |
| R5 保存方案静态诊断 | 源码 `1acc50a7f8290fd98fa94a12113281728705d7ca`；本次归档完成结果 | 100 对、200 个条件下界、0 新评分，仅用于研究边界 |
| 外部截图成绩 | 身份与未四舍五入数值未核实 | 不作论文正式同行基线，不写“已超越外部最优” |
| 未提交 tensor_incumbent 实验模块 | 仅有合成检查，未接入、未测真实图 | 不纳入章节主算法或任何结果行 |

主方法是“当前已有完整验证证据的主线”，不是声称它已被队长冻结为最终提交算法。本会话已通过 [Issue 33 的论文范围通知](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5826333267) 联系 P2 队长与协调者，请其给新固定版与采用范围；通知已发出不等于对方已读或验收。正式 TeX 单写归属不变。

随后实际读到队长 [Issue 33 #5826526478](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5826526478) 的定向证据更新：完整成绩仍为 c665，新增 e4f7b13 没有新正式成绩。已读取所给三个 README 的原文并修订 5.7；这是已读材料回执，仍不是章节验收。该通知时 Pro R06 尚在生成；其后已按 [#5826838909](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5826838909) 读取完成归档及限定审阅，见 S13。当前不将旧“正在生成”状态当作活任务或等待凭据。

最新按队长 [#5827059774](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5827059774) 与 [#5827163275](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5827163275) 读取 e6ae369 的 R05 已完成官方配对和 70f2e8 的完整 DDR 对照，分别见 S15、S16。S11–S14 中的“未测、未派发、等待窗口”均是各自固定版本的历史状态，已被 S15 的完成证据更新；本会话没有新发起实验，也不据旧状态等待已结束的任务。

## 结构参考与正文组织

用户提供的《论文结构参考.pdf》共 52 页，SHA-256 为 `f302a6d59b7cea9bcfe3c12287a0d6fb76d1dc5d1a0394f88896121c3336fe12`。已提取完整文本，实际重点阅读目录与相关章节的第 2–7、20、26、27、29、30、51 页，视觉查看目录第 4–5 页及问题二起始第 20 页。本稿借鉴其章节组织、模型—求解—结果关系及图表位置，不沿用该文不同赛题的模型、数据、结论或公式。

正文采用 5.1 问题分析、5.2 数据与符号、5.3 模型、5.4 算法、5.5 容量与下界、5.6 结果、5.7 最新探索、5.8 评价与跨问衔接。总摘要、总技术路线与全篇符号表由队长整合时去重；本章的第 5 章及图表编号均可统一调整。

## 资料索引

以下是研发证据索引，不冒充正式发表的外部学术文献。排版前应按全篇规则将实际引用的官方材料和算法文献统一编入参考文献；未查证的论文条目不补造。

<a id="s1"></a>

### S1：原题、固定配置及 P2 执行语义

- [官方目标核验](../../docs/a/OFFICIAL_OBJECTIVES.md)：原题、页码、5～10 分钟口径、平均加速比与额外 DDR 定义。
- [冻结 P2 官方源码](https://github.com/huaweibei123/huaweicup2026/blob/45f647b395b84e9569f418fd33d62c2b8eb4d190/data/raw/a/official/code/multicore_cut_evaluate_problem_2.py)：Task 重建、COPY 多重集、释放条件、Step2/3 与公平共享事件模拟。
- [固定配置](https://github.com/huaweibei123/huaweicup2026/blob/45f647b395b84e9569f418fd33d62c2b8eb4d190/data/raw/a/official/data/config.txt)，SHA-256 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。
- [P1/P2 交接及边界](../../docs/a/Q2_HANDOFF.md)。P1 的 Task 等待和 P1Evaluator 不能直接移植为 P2。

<a id="s2"></a>

### S2：全局下界与固定 FIFO 下界

- [OPTIMALITY_BOUNDS.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md)：逐 Pipe 工作、不可分割性、实际计算路径、head/tail 窗口及 COPY 收缩反例，支持式（5-14）至（5-17）。
- [FIFO_BOUND.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/FIFO_BOUND.md)：同核同 Pipe 的实际计算顺序及固定候选的适用域。不得与全局界混用。

<a id="s3"></a>

### S3：主算法及准确的基础字节目标

同一固定提交 `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f` 下已读：

- [adaptive_hypergap_guarded.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/adaptive_hypergap_guarded.py)：最多三次完整计划评分；字节下降只决定是否追加 hypergap，不剪掉原 gap。
- [hypergraph_cost.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/hypergraph_cost.py)、[binary_hypercut.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/binary_hypercut.py)：物理域、连通度费用、最小割及逐次锚定。
- [gap_candidate.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_candidate.py)、[gap_hyperrefine.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_hyperrefine.py)、[gap_retime.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_retime.py)：链与汇合、16 链区域、固定分核重排。
- [adaptive_guarded.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/adaptive_guarded.py)：实际 E2 进程、源/二进制核对、在线开销和失败账本。旧构造器退回初始方案不自动构成一次成功质量验收；完整批次的状态由独立运行收据限定。

成员 gap 适配来源为 P3 会话固定 `a37eb931a22fb7df7e0d00d193538ce5289ae045` 的日历及放置思路；队长 gap 源码保留了从成员 `71616ac7` 适配的来源注释。正文按团队共同成果表述，不将跨会话复用改称本人独立发明。

后续主方法复核重新逐行读取固定 c665 的完整 `adaptive_hypergap_guarded.py`、`hypergraph_cost.py`、`binary_hypercut.py`、`gap_candidate.py` 和 `gap_calendar.py`，补入两核指示费用的两组辅助弧、负常数偏移及逐次锚定终止证明，并明确不计任何 eligible 操作均未触及的张量。这是既有实现的论文展开，没有运行新构造、评分或算法测试，也没有把无负载约束的最小割最优性扩张到带负载约束的全局最优性。

<a id="s4"></a>

### S4：结构初解与活跃核心

固定 c665 下的 [ADAPTIVE_SEMANTIC.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/ADAPTIVE_SEMANTIC.md)、[ACTIVE_CORE_WAVE.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/ACTIVE_CORE_WAVE.md)，结合 `adaptive_budget.py`、`adaptive_semantic.py`、`adaptive_frontier.py` 与 [active_core_wave.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/active_core_wave.py) 完整源码阅读。当前 budget 调用明确关闭仅由分量计算不均触发的拆分，不能照搬旧 frontier 文档的默认路线。后续修订补齐 choose_cores 的最优平台处理：先求模型最小值，再逆推最早计算可行核数并夹到容量下限；不能只比较交点附近两个候选就宣称找到了全局最少核的平局解。

<a id="s5"></a>

### S5：容量条件

- [P2 容量与 DDR 冻结源码审计](../../docs/a/q2/PRO_CAPACITY_AUDIT_20260925.md)：区分实际 Step2 完整物理序列、零 spill 正常返回、Step3/全局成功，以及理想时间模型与机器实现。
- [F1 方法](../../docs/a/q2/feedback/FRONTIER_GAP.md)、[审阅](../../docs/a/q2/feedback/FRONTIER_GAP_REVIEW.md)，源码 `4a501d7f4a8b780263e097a963e12dcb66178e69`。
- 命题 2 使用真实完整本地序列的闭区间条件；F1/R4 的保守替代模型各有更窄守卫，不能隐去区别。

<a id="s6"></a>

### S6：完整主结果及本次表格重算

- [完整 500 格结果说明](https://github.com/huaweibei123/huaweicup2026/blob/1c00079aadbd071de62db17686d5ba3fed1da0f2/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/RESULTS.md)、[审计 report.json](https://github.com/huaweibei123/huaweicup2026/blob/1c00079aadbd071de62db17686d5ba3fed1da0f2/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/report.json)。求解器 c665，runner `ff47cbca4a953602dec7e4b959bbb10a016eca9a`。
- [本文表格重算脚本](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/build_snapshot.py) 与 [evidence.json](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/evidence.json)。脚本从固定 Git 对象读取 CSV/报告，核对 500 个唯一坐标、各图分母、实际图/config 哈希、终态，重算均值、DDR/spill、配对数及耗时分位数。
- 复算入口：仓库根目录执行 `python -B results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/build_snapshot.py`。要求相应固定提交可读取及只读官方数据已解出。不构造方案、不调用评分。
- 本次复算通过；生成证据 SHA-256 `c9656605c5d47e99f260fd63d62f3fe41bc83137e7b03ed741808e0a9a64b5a7`。不再次声称本会话核对了队长全部原始压缩结果与运行收据；原作者的完整审计与本次汇总复核是两层证据。
- 下界内 5% 的计数取已发布下界审计。本文重新核对了报告口径，没有重新运行其全图下界扫描。

<a id="s7"></a>

### S7：成员对照与负结果

- [tensor 500 格](../../results/a/q2-yuanzhifang/feedback-20260924/full-coverage/all500/README.md)，算法 `e64723bdf99669c44f76d8e90ab0379a8578522e`；[gap 500 格](../../results/a/q2-yuanzhifang/feedback-20260924/full-coverage/gap-full500/README.md)，算法 `384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`。
- [F1 五核 100 图](../../results/a/q2-yuanzhifang/feedback-20260924/full-coverage/frontier-k5-100/README.md)，105 个总测量坐标含另 5 个三核格；不能写成 500 格。
- [020/045 保存计划的静态机制](../../docs/a/q2/feedback/COMPONENT_DDR_STATIC.md)。它们是五核开发案例，使用既有 E0，非新增得分。
- tensor 与 gap 各有 501 次 solver、500 次 E0 的实际成本，包含已记录的故障/限时成本；F1 为 105 solver/105 E0。跨时段与硬件不可直接计算稳定端到端提速。

<a id="s8"></a>

### S8：COPY 事件与容量安全重排

固定 `e6925b5747b4e2dcccf2eb4a5ff41ea3f33502d8` 下的 [COPY_EVENT_GUARDED.md](https://github.com/huaweibei123/huaweicup2026/blob/e6925b5747b4e2dcccf2eb4a5ff41ea3f33502d8/docs/a/q2-nikolastarx/COPY_EVENT_GUARDED.md) 与 [CAPACITY_SAFE_RETIME.md](https://github.com/huaweibei123/huaweicup2026/blob/e6925b5747b4e2dcccf2eb4a5ff41ea3f33502d8/docs/a/q2-nikolastarx/CAPACITY_SAFE_RETIME.md)。015 的 40701 是作者已发布单次官方 E0 结果；本会话读到报告，未再次运行。它不是 c665 full500 的新数值，也不是新的统一 500 格均值。

<a id="s9"></a>

### S9：标量有限作业流水 DP

固定 `9404635dea70aa532894506c21d383f22ea6ca81` 的 [TEMPLATE_FINITE_JOB_PIPELINE.md](https://github.com/huaweibei123/huaweicup2026/blob/9404635dea70aa532894506c21d383f22ea6ca81/docs/a/q2-nikolastarx/TEMPLATE_FINITE_JOB_PIPELINE.md)，以及同提交的 `TEMPLATE_CAPACITY_PIPELINE.md`。本稿实际读取完整方法说明及新增差异。DP 的四项合成测试属于作者报告，不写成本会话执行；本次没有新真实图构造/E0/E2。

式（5-20）是固定标量阶段系统的等式，非官方周期定理。最新实现的状态标签剪枝还需保留字典序相等条件；完整复杂度、256 模板位置上限与 2000000 次可行转移预算见原说明。若后续将其升级为主算法，需要重新确认构造源、实际 runner、真实图覆盖及官方结果。

后续 S13 收紧代表作业容量表的物理触碰同构前提，并给出重入 Pipe 反例。本稿已将式（5-19）的 $P_p$ 明确定义为全部作业的最大私有峰值；只有验证物理触碰同构后才允许只计算代表作业。未修改原型源码，不能把正文修正说成原型实现已完成适配。

<a id="s10"></a>

### S10：R4/R5 条件界诊断与 Pro 来源

- [R4 方法](../../docs/a/q2/feedback/COMPONENT_GATE_R4.md)，未进行真实冷求解与独立 E0；冻结三例提案不能当作已运行。
- [R5 适用域](../../docs/a/q2/feedback/IDEAL_BOUNDS_R5.md)、[100 对静态结果](../../results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/report.json)、[完成回执](../../results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/completed-receipt.json)。结果 SHA-256 `53d102dbe6ce461cae05f110cee01cb6949c45370b283e91dcd4492fded4db0a`。
- 完成窗口 2026-09-25 03:31:13.9620654Z 至 03:32:57.0028234Z，exit 0。程序内静态诊断耗时 102.5018218999976 s，不是 solver 端到端时间。R4 与 R5 均触发 020/022/029/044/045/057，新增触发为零，0 新评分。
- 第一窗口 RAM 不足、0 启动的收据仍保留，不能覆盖为成功记录。第二窗口完成结果是新增事实，本稿据此更正旧段落的“尚无 report”。
- Pro 三轮公开原件位于 `AI chats/P2-capacity-ddr-6ab57979/`，最新快照 `snapshot-20260924T215321Z.md`。公开建议经过冻结源码复核后才转成文中限定命题；Pro 自报微型实验、未取得附件及未闭合机器误差引理不当成本机实验或正式证书。

<a id="s11"></a>

### S11：队长新发的准备剖析、模板上限及恢复计划

以下均实际读取固定 `e4f7b13e4af04914a1264a650831a3959f14a373`：

- [preparation-profile README](https://github.com/huaweibei123/huaweicup2026/blob/e4f7b13e4af04914a1264a650831a3959f14a373/results/a/q2-nikolastarx/preparation-profile-20260925/README.md)：014/K1 保存计划，Linux 单次 preparation-only，0 E0/native、0 重试；52.521 s 的 profiler 准备中 list.index 自身时间 24.301 s。这不是新求解器成绩或替代实现提速。
- [template-opportunity README](https://github.com/huaweibei123/huaweicup2026/blob/e4f7b13e4af04914a1264a650831a3959f14a373/results/a/q2-nikolastarx/template-opportunity-20260925/README.md)：九图识别域、其余输出不变条件下的五核均值贡献上限 +0.155990，不是可达预测、留出测试或新均值。
- [pro-r05-recovered README](https://github.com/huaweibei123/huaweicup2026/blob/e4f7b13e4af04914a1264a650831a3959f14a373/results/a/q2-nikolastarx/pro-r05-recovered-20260925/README.md)：按保存 owner/start 和原始 witness 恢复 003/K2 被代理拒绝的原始计划，基础 COPY 为 5207554 B。该固定版本尚无官方 Makespan，不能只凭静态代理 230838→241374 的拒绝认定官方退化；随后完成的实际对照见 S15。

本会话读取上述原报告，未重复 profiler、算法、评分或逐字节恢复验证。准备层语义保持优化属于基础设施会话，不由论文写作会话并行修改共享 evaluator。

<a id="s12"></a>

### S12：五核保存时间线诊断与 R05 对照协议

实际读取固定 `7c9b648dfaad134215fcc09c0a3258861cdd4c72` 的 [k5-utilization README](https://github.com/huaweibei123/huaweicup2026/blob/7c9b648dfaad134215fcc09c0a3258861cdd4c72/results/a/q2-nikolastarx/k5-utilization-20260925/README.md)、完整 `report.json` 数据结构及 `scripts/q2_k5_utilization_diagnosis.py`。报告从 c665 的已保存官方五核结果计算每核 M/V 忙时和 COPY 区间并集；COPY 活跃时间不等同于 DDR 字节带宽利用率，亦非关键路径归因。

本会话新增 [静态复核脚本](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/check_trace_diagnosis.py) 与 [复核证据](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/trace-diagnosis-check.json)，证据 SHA-256 `670f408dc94207716ba45b4d3b3b66ab594f8197b356b83ddbbc7b8d7708cfe2`。实际核对 100 个唯一用例、同一完成摘要、Makespan、每核求和/比例及总体算术；对 005/086/088 三份原始压缩结果逐一校验压缩与解压哈希，重算每核忙时、同 Pipe 无重叠、COPY 区间并集和事件数。不能将“三份原始结果 + 一百行汇总复核”表述为另一次一百份 raw 审计或真实复跑。

复核命令：仓库根目录运行 `python -B results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/check_trace_diagnosis.py`。全程 0 新 solver/Step2/Step3/E0/E1/E2。新增表 5-6 的数值来自上述复核；当前主算法和 500 格主均值未改变。

同时完整读取 [pro-r05-pair-pilot README](https://github.com/huaweibei123/huaweicup2026/blob/7c9b648dfaad134215fcc09c0a3258861cdd4c72/results/a/q2-nikolastarx/pro-r05-pair-pilot-20260925/README.md)。该版本明确为 frozen, no dispatch；胶囊和测试通过只证明实验准备，不证明已运行或有分数。本会话不执行其云端控制器，也不把“准备就绪”登记为活进程等待。

<a id="s13"></a>

### S13：分组流水的容量、重入计算与通信界审阅

实际读取固定 `fff17b9e116ed98c0c0cc5dd04944102f7f98978` 的完整 [R06 单条公开回复 Markdown 派生件](https://github.com/huaweibei123/huaweicup2026/blob/fff17b9e116ed98c0c0cc5dd04944102f7f98978/AI%20chats/20260924-P2-%E5%BC%82%E6%9E%84%E6%B5%81%E6%B0%B4%E4%B8%8E%E6%9C%80%E4%BC%98%E6%80%A7%E7%95%8C/r06-response-9d1b8125.md)、[方向决定 README](https://github.com/huaweibei123/huaweicup2026/blob/fff17b9e116ed98c0c0cc5dd04944102f7f98978/results/a/q2-nikolastarx/pro-r06-review-20260925/README.md)、[独立限定审阅](https://github.com/huaweibei123/huaweicup2026/blob/fff17b9e116ed98c0c0cc5dd04944102f7f98978/results/a/q2-nikolastarx/pro-r06-review-20260925/independent-review.md) 及 [Fraction 算术反例记录](https://github.com/huaweibei123/huaweicup2026/blob/fff17b9e116ed98c0c0cc5dd04944102f7f98978/results/a/q2-nikolastarx/pro-r06-review-20260925/rounding-model-probe.json)。未重新遍历该网页全部历史问答；本项记录已读的 R06 单条归档和审阅，不代签整份网页归档完整性。

正文 5.7.2 保留分组方案的核心构造：组内连续阶段、按 1/2/至少 3 作业分类容量、真实依赖/FIFO 的单作业延迟与可行启动间隔、内外两层精确非支配 DP。同步收紧三处适用域：代表作业峰值必须有物理张量触碰同构；最大 Pipe 工作不能直接等价为重入阶段的重复服务时间；一般多维标签最坏增长不能套用旧标量 DP 的复杂度。

正文 5.7.3 单列 $C_0+Q$ 的无额度门控、全局工作守恒模型及安全拒绝边界。逐 COPY 取整和可作为保守服务预算，不自动成为真实字节流体模型的工作下界；因此不报告官方近似比。审阅提出的进一步小规模检查尚未执行，不能把检查提案记为测试通过。

原型 ZIP 未取得，Pro 自报的 2204/2204/1203/45/40 次检查只是作者报告，本会话未执行该原型或 Fraction 探针。此修订仅阅读固定文件及修改论文，0 新 solver/Step2/Step3/E0/E1/E2；不改变 c665 / 1c00079 的固定成绩身份。003/K2 的 R05 配对实验在此版本仍待资源窗口，且没有被论文会话启动。

<a id="s14"></a>

### S14：当前方案重构入口与 R05 固定顺序余量

依照队长 [Issue 33 #5826959849](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5826959849)，读取固定 `afabca83ffa941f988cae0680a4d99760018d580` 的 [静态界 README](https://github.com/huaweibei123/huaweicup2026/blob/afabca83ffa941f988cae0680a4d99760018d580/results/a/q2-nikolastarx/pro-r05-pair-static-20260925/README.md)、完整 report、静态界脚本与 `fifo_bound.py`，以及完整 [ready_exchange.py](https://github.com/huaweibei123/huaweicup2026/blob/afabca83ffa941f988cae0680a4d99760018d580/src/q2_nikolastarx/ready_exchange.py)、[ready_exchange_candidate.py](https://github.com/huaweibei123/huaweicup2026/blob/afabca83ffa941f988cae0680a4d99760018d580/src/q2_nikolastarx/ready_exchange_candidate.py)。正文 5.7.4 区分就绪单射匹配中的条件字节精确性、静态时序代理、最终代理回退与官方结果；新入口要求调用者在线提供 singleton 完整方案，没有历史成绩查表，也未接入冻结 full500 主求解器。

本会话新增 [保存证据复核脚本](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/check_r05_headroom.py) 与 [复核 JSON](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/r05-headroom-check.json)，后者 SHA-256 为 `1b7e3f7ea1e8e485d52c9a8810339c4d2c38ee4f1e445011b099d244529f5d91`。实际核对原图/config、两份 R05 方案、压缩界记录、当前 c665 方案/E0 原件的固定哈希；按原图与顺序逐条验证旧初解 3310 节点、恢复候选 3638 节点的路径见证及边理由，重算每核 Pipe 工作、路径长度与三份方案的基础字节量。没有重跑最长路生成器，没有执行官方计划合法性或完整执行验证。

复核命令：仓库根目录运行 `python -B results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/check_r05_headroom.py`，要求固定提交可读及 case_003 原件已解出。恢复方案的条件界为 240126 cycles，当前保存 E0 为 245150 cycles，最大相对 Makespan 降幅精确为 `2512/122575`，约 2.0494%。这个数不是加速比增幅、预测收益或全图全核均值，也不限制其他归属及顺序。6351422→5207554 B 的约 18% 下降相对旧初解；当前 c665 重算基础字节及官方 scheduled COPY 都为 4262874 B，spill 为零。

另读同提交的 [R05 pair 协议](https://github.com/huaweibei123/huaweicup2026/blob/afabca83ffa941f988cae0680a4d99760018d580/results/a/q2-nikolastarx/pro-r05-pair-pilot-20260925/README.md)：当时仍为 frozen/no dispatch；七项匹配合成检查及五项主机派发模拟检查是作者报告，论文会话没有重跑或启动云端派发。此静态复核全部为保存数据读取和算术，0 新 constructor/solver/Step2/Step3/E0/E1/E2。当前表 5-7 的两份新增官方结果来自随后完成的 S15；仍不是新主算法成绩。

<a id="s15"></a>

### S15：R05 两份保存方案的官方配对负结果

实际读取固定 `e6ae3699870c78b11c8c47b0fa9001249a428e1c` 的 [完成说明](https://github.com/huaweibei123/huaweicup2026/blob/e6ae3699870c78b11c8c47b0fa9001249a428e1c/results/a/q2-nikolastarx/pro-r05-official-pair-20260925/README.md)、完整 `verification.json`、`batch.json` 及 [原始结果 ZIP](https://github.com/huaweibei123/huaweicup2026/blob/e6ae3699870c78b11c8c47b0fa9001249a428e1c/results/a/q2-nikolastarx/pro-r05-official-pair-20260925/result.zip)。ZIP 为 2835556 B，SHA-256 为 `c90065d9d90aae3be4144080483e3ac394a6ef150f92fc7d4450d81114ba2c66`。

本会话新增 [官方配对与 DDR 复核脚本](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/check_official_pair_and_ddr.py) 与 [复核 JSON](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/official-pair-and-ddr-check.json)，后者 SHA-256 为 `54d2c4222f783cc7907be184cb20ba55b43e0e7f254757bb343b9da4f86f3573`。实际核对 ZIP 全部 23 个成员的 CRC、SHA，原图/config、两份计划与旧静态复核的身份一致性，清单中的全部官方源码与固定胶囊源 7c9b648 的逐字节哈希。解析两份 result/Trace，核对最大执行结束时间、搬运量、进程终态、退出码及记录中无残留进程；没有重新执行评价器，也没有查询当前云端状态。队长归档中的 VM 停止及空 session 记录不冒充本会话的实时查询。

003/K2 的旧初解与恢复候选分别为 248166、254508 cycles，scheduled COPY 为 6351422、5207554 B，spill 均为零。候选相对旧初解减少 COPY 18.00964%，却增加 Makespan 2.55555%；相对此前已保存的 c665 245150 cycles 慢 3.81725%。固定 FIFO 界增加 9371 cycles，官方值减去界的残差减少 3029 cycles，两者合计等于官方退化 6342 cycles；该残差不是实测 DDR 等待时间。本例否定了该候选的官方收益，不能证明所有代理拒绝都安全。

原实验在 2026-09-25T04:54:48.715344Z 进入 T0，只对这两份保存计划串行执行两次 E0，0 E1/E2、0 新构造、0 重试；worker 批次为 21.27858728399997 s。环境准备与外部 E0 成本单列，均不作为新 solver 墙钟。本文表 5-7 纳入结果，表 5-2 的 c665 完整成绩不变；新 singleton 入口依旧没有真实图增益证据。

复核入口：仓库根目录执行 `python -B results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/check_official_pair_and_ddr.py`，要求所列固定 Git 对象及同目录旧证据可读。全程仅解析保存数据，0 新 constructor/solver/Step2/Step3/E0/E1/E2。

<a id="s16"></a>

### S16：完整 500 格的次要 DDR 指标与跨版本取舍

实际读取固定 `70f2e8bd8e850f1d49c924a86b654b29c24e087f` 的 [次要 DDR 指标说明](https://github.com/huaweibei123/huaweicup2026/blob/70f2e8bd8e850f1d49c924a86b654b29c24e087f/results/a/q2-nikolastarx/secondary-ddr-full500-20260925/README.md)、完整 [report.json](https://github.com/huaweibei123/huaweicup2026/blob/70f2e8bd8e850f1d49c924a86b654b29c24e087f/results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json) 和 `scripts/q2_secondary_ddr_audit.py`。对照为前版 `2794ceba93acc1f7fc119154f61082511843d4b3` 与主方法 c665，不能将前版称为所有 c665 求解调用中实际参与评分的初始候选。

使用 S15 同一复核脚本，从固定 `60afc38b327680fbda0ff10182e3e05a01edd72d` 的旧完整 board feed 和新 completed-summary 逐格核对两侧各 500 个唯一坐标、算法身份、图/config、接受状态、前版 E0 路由及字节分解恒等式，再重算全部 500 行与发布报告的一致性、分核/总量、均值、计数和增量集中程度。这是固定 feed 与已审计摘要的再核对，没有重新审计全部 500 份 raw 结果或运行评分。

全部额外 DDR 从 3043860416 增至 4159738560 B，即 +36.65996%；55 格 Makespan/DDR 同降、199 格 Makespan 降但 DDR 升、14 格 Makespan 降且 DDR 不变、232 格两项均不变。净增量中切分新增搬运占 77.66135%，spill 占 22.33865%；014 与 072 合占净增量 77.09089%。正文表 5-4 的分核变化率均按总量比计算，不是逐图百分比均值。案例集中性用于诊断，不产生针对用例编号的例外规则。

正文表 5-3 同步更正解释：268/232/0 是前版与主方法在此批次的配对观察，不是任意前版均由候选选择器包含所带来的理论保证。Makespan 为主的字典序规则不会限制已改善 Makespan 时的 DDR 增幅。当前继续报告真实取舍，不以任意加权分数掩盖通信退化，也不因次要字节指标单独否定首要目标的实测改善。

## 图件与最终补证清单

| 图号 | 本次状态 | 最终输入与检查 |
| --- | --- | --- |
| 5-1 | 文字占位 | 最终主程序调用关系；尚未接入的模块不能画进执行主线 |
| 5-2 | 文字占位 | 手算合成例或完整实际物理序列；区分静态容量与运行峰值 |
| 5-3 | 文字占位 | 固定版本 100×5 逐格结果、固定分母；缺测不连线 |
| 5-4 | 文字占位 | 同图同核同配置的固定 plan/trace；含 R05 负结果及完整配对取舍，COPY 区间活跃与带宽利用率分开 |
| 5-5 | 文字占位 | 同硬件同并发的完整求解墙钟及质量，不混内核时间 |
| 5-6 | 文字占位 | 有适用域的全局界证书；与固定 FIFO 界分离 |

正式制图时使用项目 `scientific-figures`/`scientific-figure-making` 规范与标准绘图工具，保留数据、脚本、矢量输出和视觉验收。本轮没有生成看似真实的模拟成绩图；用户允许文字占位，故优先把指标与证据要求写清楚。

同主程序消融、同硬件质量—耗时实验、最终版本完整覆盖和全篇文献/符号合并仍是待补证，不据此自行启动新的批次。共享正式 TeX 由队长整合，本会话持续修订本 Markdown。

## 更新规则与本轮验证

新方法出现后，先核对固定提交、适用条件与复杂度，更新 5.7；只有与该实现绑定的新结果才更新对应实验。替换主方法时同步重写 5.4、伪码、预算、表格与图源，不保留过期算法叙述配新成绩。评分缺口仍按缺口表示，算法开发者的报告、汇总重算、独立复评和最终验收分开记录。

本轮只读查阅官方语义、算法固定源码/说明、冻结结果并重算论文表；没有新 solver/Step2/Step3/E0/E1/E2，也没有重启 Pro 或后台实验。算法临时代码保留在原工作树，不随论文提交伪装成已验证主方法。

交付检查：表格重算脚本通过；本地文档链接及 11 个资料锚点、20 个连续编号公式、8 节标题、6 个图占位检查通过；示例 007/020/045 的五核数字再次与冻结 CSV 核对。Markdown 解析后的 6 张表（含符号表）列数一致，已视觉查看正文开头及主结果表；预览保留 TeX 文本，不称作最终数学排版验收。Git 空白检查、文件编码、个人路径及凭据模式检查通过。Windows 无 dot_clean，已对本次 paper/结果具体目录做只读元数据扫描，无 `._*`、`.DS_Store` 或 `__MACOSX` 项；未作跨目录清理。

后续版本新增 5.6.6、5.7.4 与资料 S12–S16，并展开 5.4.3 的最小割证明；旧“11 个资料锚点/6 张表”是首次交付记录。最新检查通过：16 个资料锚点、48 个本地链接、21 个连续编号公式、8 节、6 个图占位，以及 8 张表（含符号表）的列数；表 5-4/5-7 的新增数值与保存数据复核对应，并已查看这两张表的渲染预览。详细图仍为文字占位，预览不包含最终公式排版。
