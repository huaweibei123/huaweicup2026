# P2 容量与 DDR 命题的冻结源码复核（2026-09-25）

审阅对象：Pro 公开回答 `AI chats/P2-capacity-ddr-6ab57979/snapshot-20260924T202250Z.md`，冻结官方提交 `45f647b395b84e9569f418fd33d62c2b8eb4d190` 下的 `multicore_cut_evaluate_problem_2.py`、`schedule_step2.py`、`schedule_step3.py`、`evaluation_validation.py` 与 `stub_multicore_cut_and_schedule.py`。本次是独立静态源码审计：没有把 Pro 的自报重放、附件数值或证书当作本机复现实验；没有构造官方大图、运行 solver 或 E0。未新增探针脚本，合成运行数为 0。

## 1. 固定 eligible 核映射时的基础 COPY 多重集：可用，须限定对象

P2 先由 `derive_multicore_plan` 得到每个 eligible 操作的核，再按 tensor ID 遍历原图；每核一份本地 tensor，原 DDR 位置转 UB（`multicore_cut_evaluate_problem_2.py:61-153`）。无 eligible producer 且有消费者时，每个消费核生成一个 IN；最终输出每个生产核生成一个 OUT；每个异核 producer/consumer **核对**生成一对 OUT/IN；每条异核直接 op-op 边也生成一对 COPY（同文件 `:156-238`）。这些循环的次数、源/目的核、大小只由原图和核映射决定。局部 subgraph 选择会改变 COPY 的桶和 Step2 输入序，但不改变该多重集。源 tensor 发往两个核时，源端确有两份 OUT。零字节直接边仍生成 COPY，时长至少 1 cycle（同文件 `:217-232`、`schedule_step3.py:74-90`）。

此命题只指 **Step2 spill 插入以前的基础 COPY**，并以同一原图、合法计划、同一 eligible 核映射、同一配置为前提。不能把 COPY ID、桶标签、FIFO 顺序、spill COPY 或最终 makespan 也说成不变。原图中没有 eligible 操作触及的 tensor 不进入本地 task；原始 COPY 不作为 eligible 操作直接保留，而由 P2 重建端点需求（P2 `:135-180`）。原图允许零字节 tensor；验证器只要求非负整数及 `pos∈{DDR,L1,UB}`（`evaluation_validation.py:10-25,171-213`）。原图多 producer 不应在证明里默认为不存在：P2 此处按 producer **核集合**处理，且同核 producer 可共享一个本地 tensor；若算法 token 模型要求唯一 producer，必须另加守卫，而不能由这个 COPY 计数命题推出。固定核映射也不保证重新切分/合并后的商图合法；入口及跨核依赖仍须复验（`stub_multicore_cut_and_schedule.py` 的 `derive_multicore_plan`、`evaluation_validation.py:226-254`）。

## 2. Step2 闭区间峰值与零 spill：对返回结果成立，须用 Step2 实际输入

对 **P2 已重建的每核局部图** 和 `_prioritize_task_seq` 交给 Step2 的完整操作序列，按物理 tensor ID 统计所有 op–tensor 边的首次/末次触碰。只统计 `pos=L1/UB` 且至少被序列触碰的 tensor；DDR backing 不算池驻留，原 DDR 的本地副本已被 P2 改成 UB，跨核 direct 边的合成本地 UB tensor 也必须计入（P2 `:145-153,217-231`；`schedule_step2.py:105-129`）。定义每步闭区间和 `H_p(i)=Σ size(t)·1[first(t)≤i≤last(t)]`，同一步输入、输出和一次性 tensor 均在检查前同时驻留。

在合法拓扑序、非负容量、上述完整物理 token 清单、Step2 **正常返回**的域内，`max_i H_p(i)≤C_p` 当且仅当该次 Step2 无 `spill_records`。前向证明：按首次分配、末次执行后释放，任一步驻留就是闭区间集合，故不进入溢出循环。反向证明：若首次越界，循环必须选择 victim 生成 spill，或因没有合法 victim 抛 `Step2SchedulingError`，无法“正常返回且零 spill”（`schedule_step2.py:210-292`）。因此对任意合法输入更稳妥的逻辑表述为：`H≤C ⇒ Step2 可零 spill 通过`；`H>C ⇒ 不会零 spill 返回`，但可能**报错**，不能把报错当作一次正数 spill 测量。

缺失 producer 不等于可忽略输入：Step2 对任何被触碰的非 DDR tensor 在首次触碰时分配，P2 生成的图输入还附有合成 COPY_IN（P2 `:159-167`；Step2 `:113-125,228-241`）。`logical_tid` 别名标签不合并 Step2 的物理 ID 驻留：原始同名逻辑关系若影响实际 token 身份，必须先确认映射；现有保守算法的 alias 守卫仍合理。零大小 tensor 对峰值贡献 0，却可参与依赖与至少 1 cycle COPY；越界时它不能释放有效容量。池外位置在合法图中只能是 DDR，跳过其驻留是正确的；未知位置、负大小或错误端点不在该定理域（`evaluation_validation.py:171-213`）。孤立/未触碰 tensor不参与此 `H`。多 producer 对 Step2 的区间和本身可按物理 ID 计算，但算法若以“一个 producer 决定一个 token”建模，必须额外拒绝该结构。

注意这是 **Step2 零 spill** 判据，不是整个 E0 成功、最终并行驻留峰值或 makespan 证明。Step3 对无 producer 的本地输入有“图开始前驻留”处理，还会生成容量复用依赖；本地 Step3 可因自己的调度/契约失败，最终 P2 也可能因跨核组合成环或事件上限失败（`schedule_step3.py:217-259,600-669`；`multicore_cut_evaluate_problem_2.py:295-297,500-516`）。现有 `capacity_window.footprint` 仅覆盖其弱分量同核、单操作子图等守卫域，不能直接替代一般 gap 计划的完整 P2 合成 token 清单。

## 3. 固定编译图的 L/U：数学模型可用；冻结实现声明须收紧

必须先完整运行 P2 构图、Step2、Step3，得到实际本地 data/memory edges、每核每 pipe 的 FIFO 顺序和跨核 COPY link。`G` 要显式加入 FIFO 相邻边及 `OUT→IN` 的配置 lag；仅用 `execution_graph['edges']` 不够。局部 Step3 结果的绝对时刻不是全局下界，P2 全局阶段只沿用其图和 pipe 词（`schedule_step3.py:600-703`；`evaluation_validation.py:226-254`；P2 `:315-327`）。

对每个节点以 `_op_duration` **实际返回值**作独占时长 `d_v`；DDR 集合必须用 `_uses_ddr_bandwidth` 的真实谓词，而非仅凭 COPY 名称（`schedule_step3.py:74-90`）。对成功完成的执行，精确实数公平共享模型给出 `L=max(Σ_DDR d_v, max_{c,p}Σ_{v∈(c,p)}d_v, longestPath(G;d,lag))≤M`：总 DDR 工作需要至少其独占总量，各 pipe 槽位为 1（Step3 `:30`），每节点受完整前驱约束。至多 `2k` 个 MTE2/MTE3 COPY 同时在飞；每个 DDR COPY 的服务率至少 `1/(2k)`，所以其完成历时至多 `2k·d_v`。全局事件循环对已满足 data/memory、FIFO 与 cross release 的队头立即发射（P2 `:382-487`）；按拓扑归纳，`M≤U=longestPath(G;\bar d,lag)`，其中 DDR COPY 用 `2k·d_v`、其他节点用 `d_v`。这里固定的是**完整编译图**，含该计划实际 spill、memory、FIFO；不能把此 L 当所有合法计划共同下界。

冻结 Python 实现另有数值前提，Pro 原文的无条件“严格证书”应收紧：DDR 剩余工作转 `float`，用 `1e-9` 阈值判完成，并以 `ceil(cursor-1e-9)` 投影**整数**结束时刻（P2 `:330-373,469-484`）。这不是精确有理数处理器。对正常量级、有限事件，上述界有清楚的结构证明；若要将任意合法非负整数大小和任意有限带宽都纳入机器级严格证书，应证明浮点误差不会突破整数取整裕量，或用保守有理/区间算术重新计算边界。还须限定全局执行成功返回：`max_iter` 超限、死锁或数值无进展时没有可比较的 M（P2 `:489-516`）。本次未独立重算 Pro 所报 008/095 的 `L/U` 数值或 `U_new<L_gap`；这些是待核的作者附件报告，不在本静态审计中升级为已验收结论。

结论分类：**命题 1 可用但仅限基础 COPY 多重集；命题 2 可用但必须是完整 P2 物理 token 与 Step2 实际序列且区分报错；命题 3 在精确服务模型下成立，若作为冻结 Python 任意输入的严格数值证书须补误差证明与成功返回条件。**
