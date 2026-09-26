# P2 完整分量 / DDR gate 独立审阅（R4）

实现者修复回执：下方窄审指出的 direct 大整数缺口已加入 `size<=2^31` 守卫和 `18014398509482041` 的纯合成拒绝回归；计数改名 `outer_plan_count`，明确不含 F1 内部构造。F1 已经因容量拒绝的 resource word 不再重复构造。新模块与原 F1 共11项测试通过，0真实图求解/Step2/Step3/E0。此段为Root修复与自测回执，不代称审阅者二次验收；下文保留审阅时实际发现。

审阅范围：当前工作树 HEAD `3234d159a88480729cd301bcf4fdc8175b9d541b`；`COMPONENT_DDR_BOUND_REVIEW.md`、`COMPONENT_DDR_STATIC.md`、第三轮公开回答（消息 `d625ab0e-3660-4703-a34a-a64b4bf7b009`）和 `r3-p2_cheap_gate.py`，对照冻结 P2、Step2/3。只做源码审阅和纯合成算术；0 真实图构造、0 Step2/3、0 E0。第三轮机器引理全文 `NUMERICAL-LEMMA-zh.md` 尚无本地原件，无法独立核验其逐步误差及计数证明。

## 结论与最小适用域

**可以把 `U_A < L_B` 实现为有理论依据的启发式选择信号，不能标为已证明的官方机器 Makespan 严格改进。** A 必须是针对**当前输入及核数**直接构造并通过 `derive_multicore_plan` 的 singleton 完整弱分量计划；检查 P2 规范化后的 `cross_links=[]`，且 `physical_frontier.certificate(index,A,capacity)['certified'] is True`，其 token 身份、无 alias/唯一 producer 和容量前提均实际成立。不能用旧保存计划、图号或仅由“完整分量”字样代替这些检查。B 必须是针对同一输入、配置的完整 F1 构造结果，不能把 F1 的预修复 gap 草稿、旧计划或其元数据代入。F1 未获证的核可保留原序；B 的容量证书**不是** `L_B` 基础 COPY 下界的必要条件。

上述条件使 A 的 Step2 局部桶内无 spill，且完整成功编译/执行时没有额外跨核 release。取最后完成的核，精确工作守恒公平 DDR 模型中，它在未完成时若没有 eligible 操作运行，就必有已计入的 DDR COPY 服务。因此 `M_A <= max_c C_c + W_A = U_A`；任意成功的 B 至少消耗其基础 DDR 服务 `W_B=L_B`，所以 `U_A<L_B` 在**这个精确模型**下可严格选 A。这里还要求没有未计入的非 DDR 正时长操作、局部/全局调度死锁及 `max_iter` 失败；仅有 JSON 合法和容量证书不证明两份计划会正常返回。冻结 P2 的整数事件、`float` 剩余量、`1e-9` 阈值和 `ceil(cursor-1e-9)` 不自动满足精确模型的界。

## COPY 归一化与实现边界

`C_c` 逐个 eligible op 用冻结 `_op_duration` 的 `max(1,cycles)`，不是原始 cycles。P2 重建的每一条**基础** DDR COPY 分别用 `_op_duration` 计算 `max(1,ceil(size/60))`，再求 `W`；0 B COPY 仍是 1 cycle。输入 tensor 每个消费核一条 `COPY_IN`；最终输出每个生产核一条 `COPY_OUT`；跨核 tensor 的每个生产核/消费核对以及每条跨核 direct op 边各一对 COPY。跨核 direct 大小用 `max(0,int(data_size))`。原图 COPY 节点被排除后由 P2 重建，不能重复计入；`ceil(总字节/60)`、`added_copy_bytes/60` 和只统计 tensor 不统计 direct 边均错误。A/B 各按**自己的映射**生成 COPY 多重集；不能把 A 的基础流量用于 B。逐条还应核对端点含 DDR，与 `_uses_ddr_bandwidth` 一致。官方配置此处带宽是 60 B/cycle；若配置改变，常数 60 的 gate 代码必须拒绝或改为实际带宽。

`r3-p2_cheap_gate.py` 只接收调用者交来的摘要整数和两个布尔值；它不构造计划、COPY、token、合法性、Step2/3 图，也不核验 `g`、`q`、`W`、`d`、`C` 是否来自实际候选。`a_structure_certified=True` 不能由调用者无条件填写；`ieee_ops_attested=True` 和 `sys.float_info` 也不证明每个官方运算满足作者的舍入假设。第三轮公开回答的 `epsilon_A/epsilon_B` 依赖缺失的完整机器引理及两计划正常返回前提，当前不能把 `conditional_prefer_A=True` 展示为已证 theorem、官方证书或免 E0 成功性证明。若生产实现保留这些余量，标注为**未独立证明的候选数值守卫**；超出守卫、统计不齐或比较未命中均返回“未判定”，不可反推 B 更快。

## 最小边界与反例

1. **跨核等待必须排除。** 两个 1-cycle eligible op 分置两核，中间一条 0 B direct 边。P2 仍生成两条各 1-cycle 的 COPY，并对目的端施加 500-cycle release lag。忽略 `cross_links` 时写出的 `max C+W=3` 无法上界官方作者报告的 `M=504`；具体数值来自第三轮公开回答，机制可由冻结 P2 的 `cross_links` 与 release 代码直接核对。
2. **基础 COPY 不变、退化只来自 spill 时 gate 必不命中。** 若 `W_A=W_B`，则 `U_A=max C+W_A >= L_B`，即使 B 的 spill 很大也无判断力。不能用“未命中”覆盖 F1 既有容量准入或回退策略。
3. **正常返回不是结构推论。** 第三轮作者报告一个 1-op、`2^53` cycles 加 60 B 最终输出的 A，在冻结 E0 报 `no progress`；原始 tiny 附件未取得，故这是作者报告而非本机复现。即使容量足够、无跨核链接，机器事件循环仍可能无 M。这也说明成功性前提不能藏在 gate 的布尔返回中。
4. **取整边界。** 两条 0 B COPY 合计字节为 0，但 `W=2`；用总字节一次取整会给 0 或 1，导致下界/上界错计。两条各 61 B、60 B/cycle 的 COPY 有 `W=4`，合并字节后 `ceil(122/60)=3`。

## 实施前必要检查

- 用纯合成输入固定三类边界：0 B direct 跨核、同一 tensor 的多生产/消费核对、只有 spill 差异而基础 COPY 相同；逐条比对规范化 COPY 多重集、`q/W`、`cross_links` 和 `certified`，不只比字节总和。
- 对 A 当前方案核查 singleton、完整分量、合法顺序、无 alias/唯一 producer、全核物理证书；B 保留 F1 的真实输出及原有失败回退。门命中只代表优先尝试 A；如需声明官方严格比较，先独立补齐机器引理证明和两份计划正常返回依据。
- 后续获授权实测时，固定同图同核 A/B，仅少量对照，分别记录门值、官方成功/失败、Makespan、DDR/spill、构造至落盘端到端墙钟与外部 E0 墙钟。若机器余量或成功性证伪，撤回严格说法；若 gate 成本抵消收益，保留静态诊断用途。

源码锚点：冻结 `multicore_cut_evaluate_problem_2.py:61-282,323-379,425-515`，`schedule_step2.py:204-290`，`schedule_step3.py:74-92,315-375`；本地 `src/q2/feedback/physical_frontier.py` 与 `frontier_gap.py`。静态 020/045 表只证明两份**旧保存计划**的该式在这两格触发及旧官方结果方向一致，不是当前 A/F1 新算法的验证。

## 新 `component_gate.py` 窄范围代码复审

只读该模块、其六项纯合成测试及必要冻结源码；未运行真实图、Step2/3 或 E0，也未改实现。`service_profile` 的 tensor 输入/最终输出、异核 tensor 对和 direct 边 COPY 多重集，与冻结 P2 `:133-234` 对齐；每条 0 B COPY 给 1 cycle，eligible `max(1,cycles)`，B 用 F1 **最终**计划，A 的完整分量、`cross_core_links==0` 和容量证书均实际检查。`consider_alternative` 检查 A/B 核数相同；不等式失败保留 F1，没有发现直接反转选择的分支错误。

**需修正的具体缺口：跨核 direct `data_size` 不受类型/上限守卫。**模块仅限制 tensor `size<=2^31`，但 direct 大小直接做 `max(0,int(data_size))`，再用精确整数 `ceil(size/bandwidth)`；冻结 P2 同样先 `int` 归一化，却在 `_op_duration` 使用 `math.ceil(size / bandwidth)` 的浮点除法。官方 `validate_graph` 不检查 direct `data_size`。纯合成算术例：`bandwidth=60`、`data_size=18014398509482041` 时，官方表达式 `math.ceil(size/60)=300239975158034`，模块整数式为 `300239975158035`。一条跨核 direct 边产生两条 COPY，`W_B` 可多算 2，从而把原本不触发的严格不等式变成触发。应对 direct 归一化大小加入与 tensor 相同的保守整数范围守卫，或逐条严格复刻冻结浮点表达式并重新说明适用域；还应加这个纯合成边界测试。此例只是公式差异，未声称构造了能通过全程 E0 的图。

`constructed_candidates` 当前值 1/2 是**gate 外层** F1 返回计划与可选 tensor 计划数，不是完整在线构造尝试数。F1 内部可能先构造 uncertified resource-word，再构造 gap，再生成容量修复计划；这些都计入 solver 墙钟。若该字段用于报告“实际构造候选总数”，数值会低报；可改名为 `outer_candidate_plans`，或分别记录 F1 内部尝试和 gate 增量。`online_E0_calls=0` 与可见模块行为相符。最新队长 c665 全 500 的 k5=4.549757 属另一算法身份；本组件的静态 gate 不能据此声称超越该结果。
