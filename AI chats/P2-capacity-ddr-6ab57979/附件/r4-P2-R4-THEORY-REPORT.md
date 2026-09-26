# P2 第四轮：全局加速比上界、保存数据差距与迭代保证

负责人：`yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24`。仅 P2。

## 0. 本轮来源、执行边界与结论

本轮附件实际解压并核验：523787 B；ZIP SHA256
`3c0eba21dfc907d109c3a5e91b8a3dea29fe64e82abe92123d660694b42797a8`。
41 个成员，MANIFEST 所列其余 40 项大小和 SHA256 全部一致。

实际读取了请求、manifest、全局界证明/源码、完整全局证书和 500 格摘要/CSV，冻结 P2 构图和全局循环、Step2 的生命周期/backing/重命名、Step3 的时长/分配/释放/FIFO/准备接口，以及提供的候选构造、超图费用/二元割、固定 FIFO、C01/R07 和反例材料。论文稿只审阅下界、结果、局限和 R05 相关段落；不是全文编辑。逐文件读取深度和哈希见 `R4-SOURCE-AUDIT.md`。

缺件：100 原图、500 份计划/raw E0/trace、原 A 基线回执、主算法全部传递依赖、原生 E2 源码/二进制、C01/R07 的完整原提案/实现及 069 的准备快照。旧轮 ZIP 虽仍可见，本轮没有用它重跑或替代新包。P1 文件仅用于 P2 共享解析函数，未沿用 P1 Task 语义。

源身份是 MANIFEST 的组织主库完整提交链接与本地实际哈希，不等于 Git checkout 验证。正文实质审计以已核哈希的附件为准，未以在线仓库读取替代附件。R4 没有 P3 代码，因而没有声称重算旧轮包含 P3 的整包 code aggregate；已逐项核对当前全局证书列出的六个关键官方源码哈希。

标记：**[源码]** 冻结代码；**[作者记录]** 包内既有运行记录；**[本轮复算]** 保存数据算术；**[本轮证明]** 本文给出推导；**[理想模型]** 非冻结机器保证；**[未验证实现]** 原型尚无全图验证。

| 结论 | 状态及限制 |
|---|---|
| 现有计算负载、不可分割、保留计算 CP、head/tail 窗口可作全局下界 | [本轮证明] 依赖明确的重建域；不使用 DDR 浮点服务守恒 |
| 现有 500 格界与当前值、身份、聚合算术一致 | [本轮复算] 未重新验证缺失的原图与 raw E0 |
| 新增“必需 I/O 整数事件—计算窗口”界 | [本轮证明] 弱支配现有界，在极小结构可严格加强；未计算完整 500 格 |
| 带逐 COPY 服务权重的 DDR 窗口式 | [理想模型] 未认证 binary64/1e-9 实现，不采用前轮未验收机器引理 |
| K5 均值加速比最多增加 34.24984% | [本轮复算] 只是现有放松下的上限；不是已知可实现收益 |
| 保留完整 incumbent、精确成功评分、只接受 M 不增 | [本轮证明] 证书区间单调收缩；不保证严格进步、全局收敛或 DDR 不增 |

本轮 E0/E1/E2、计划构造器、搜索、云任务调用全部为 **0**。仅做保存数据复算，以及四个极小整数静态界 fixture 和一个证明域拒绝 fixture；静态正例因证书输出整理复核过一次，共九次静态 `certify` 调用。没有模拟它们的官方执行。

## A. 上界对象与定理链

### A1. 对象不能互换

对固定图、配置及核预算 k，令 P(G,k) 为能成功返回有限官方 Makespan 的合法计划集合，

\[
M^*=\min_{\Pi\in P(G,k)}M_{\rm E0}(\Pi),\qquad U=M_{\rm E0}(\Pi_{\rm inc}).
\]

只要 L 对所有这些计划有效且 U 是可行见证，便有

\[
L\le M^*\le U,\qquad A/U\le A/M^*\le A/L \quad(L>0).
\]

这里 U 是“最优 Makespan 的已知上界”，不是把某个模拟器预测当成计划的执行上界；A/L 才是所求全局最优加速比的上界。固定 owner/FIFO 的最优值是受限问题的最优值，不能换成 M*。求解墙钟是程序和运行条件的成本，另报。[BOUND-PROOF]

A 是固定官方 A 单核基线，不是优化后的 P2 单核最优值。故没有理由直接套 A/M*≤k；K1 加速比大于 1、K5 的现有上界大于 5 并不矛盾。[BASE-A] [RESULTS]

### A2. 现有计算界：逐项审核

令 V 为非 COPY_IN/COPY_OUT 的原操作；d(v)=max(1,cycles(v))，p(v) 为节点 pipe。原 COPY 被重建，不能把它们的原 cycles 再加进 V。非 COPY 的 MTE2/MTE3 操作仍算计算工作。[P2] [S3]

**命题 1（负载与不可分割性）。** 对每条 pipe p：

\[
M^*\ge\left\lceil\frac{W_p}{k}\right\rceil,\quad W_p=\sum_{v:p(v)=p}d(v).
\]

将该 pipe 操作时长降序为 d₁≥…≥dₙ。对 q≥1、m=(q−1)k+1≤n：

\[
M^*\ge\sum_{j=m-q+1}^{m}d_j.
\]

证明：每个操作完整落在一个核心的一个槽中；k 个核心同类槽同时最多容纳 k 个操作。积分得到负载式。前 m 个操作中至少有一个核心拥有 q 个，它们的和不小于这 m 个中最小 q 项之和。两式只用真实操作不可分割性，不将整弱分量当作官方不可分割作业。对不同 pipe 与不同 q **取最大**，不相加。[BOUND-CODE]

**命题 2（保留计算因果）。** 在每个原 tensor 至多一个 eligible producer 的保守证明域内，以下关系在任何成功 P2 执行中都先完成、后开始：原 eligible→eligible direct 边；同一原 tensor 上 eligible producer→consumer 的边。不得增加仅由原 COPY 路径收缩得到的计时边。

证明分三种情形：同核 direct 边直接保留；同核唯一 producer tensor 若被 spill，则经首次真实写回 backing 与 reload 保留 producer 因果；跨核时经源 OUT、外部释放、目的初始 IN。即使后续 reload 重用已有 backing，初始 IN 在完整序中的位置仍在 reload 之前，Step2 不改变基础操作相对序、最终 MTE2 FIFO 不允许它被超越。新增内存边可以增加限制，不能删除上述已保留路径。[P2] [S2] [S3]

多 eligible producer 域中该证明不成立时必须停用相应路径/窗口界；不是宣称这些输入一定错误。固定 FIFO 下界也有同样重建域，但额外固定的 FIFO 不能进入全局界。[FIFO]

**COPY 收缩反例（源码推导，不是本轮 E0）。** 原图 A(M,10)→原 COPY_OUT→B(V,10)，无 tensor。合法性图收缩出 A→B；P2 丢掉两个含原 COPY 端点的 direct 边。剩下 A/B 不同 pipe 可同时执行，完成时刻 10，而收缩计算路径为 20。将后者作为全局时间下界错误。[P2] [STUB]

**命题 3（CP 与工作窗口）。** 在保留 DAG 上计算严格前驱最长路 h(v)、严格后继最长路 t(v)。成功执行满足 s(v)≥h(v)、e(v)≤M−t(v)，故

\[
L_{CP}=\max_v(h(v)+d(v)),
\]

对同一 pipe 上任意非空 S：

\[
L_S=\min_{v\in S}h(v)+\left\lceil\frac{\sum_{v\in S}d(v)}k\right\rceil+\min_{v\in S}t(v)\le M^*.
\]

证明：S 全部占用区间都落在共同窗口 [min h, M−min t]；其中只有 k 个相同 pipe 槽。积分后取整数上整即可。不是“任意 CP 加全部工作”。若多个 valid L_j≤M*，则 max_j L_j≤M*；不存在把同一工作跨不等式重复相加的问题。

现有实现仅扫描所有 head 阈值子集及所有 tail 阈值子集，并非所有子集。路径动态规划和排序扫描成本明确；形成原 tensor 的 producer×consumer 诱导边应按实际诱导边数计，不能笼统宣称对原二部边数总是线性。[BOUND-CODE]

**机器适用域。** 这些计算界可覆盖冻结返回值：普通操作结束时刻由整数 now 加整数 d(v) 得到，不走 DDR 剩余工作更新；每个计算操作和 pipe 槽约束真实存在。DDR 舍入影响的是调度开始时刻等，不会使这些整数计算时长被消除。证明没有调用“逐 COPY 服务总量≤机器 M”的未验收引理。[P2] [S3]

### A3. 本轮主推：必需 I/O 整数事件窗口界

这是一个 **机器级安全、但故意较保守** 的强化。它耦合必需 I/O 的事件先后及 MTE 占用与计算窗口，不声称已刻画 60 B/cycle 的字节瓶颈或容量强制 spill。

**引理 4（成功返回的 COPY 至少占一个整数周期）。** 对固定 P2 全局循环，每个被发射并成功退休的 COPY 都有整数 end−start≥1。

完整证明如下。

1. 初始 now=0；普通操作 end=now+整数 duration，COPY 重排 end=int(ceil(...))，外部 release=end+整数 500。因此下一事件时刻仍为整数。
2. 上一次循环在进入下一轮前检查 min(next_times)>now。故进入当前 retire(t) 时，所有在飞操作的已登记 end≥t。
3. `advance_ddr_work` 只改残余量，不改已登记 end；retire 遍历全部 executor 时只退休 end≤t 的操作，故它们的 end 恰为 t。统一 `reschedule_ddr` 在这轮遍历之后才执行。
4. 新发射发生在 retire 之后；它不可能同轮退休。若之后舍入产生不前进的事件，程序报错而非成为有限成功见证。对成功返回的运行，它必在较大的整数 t' 退休，因此 end−start=t'−t≥1。
5. 已退休 COPY 从残余字典移除，不再被后续重排改变 end；最终 M 是这些已退休 end 的最大值。因此可以把这个正占用长度用于返回的 M，而非另一个虚构的退休时间。

这个论证不估计 float 运算误差，不需要搬用前轮 ε，也没有把 1 周期解释成服务时间 max(1,ceil(bytes/60))。它直接使用冻结成功返回的控制流不变量。[P2]（尤其 329–371、425–509 行）

**构造 H_evt。** 从命题 2 的保留计算 DAG 出发：

- 对每个有 eligible consumers、无 eligible producer 的输入 tensor t，加一个虚拟 I_t，pipe=MTE2、时长下界 1，并连向 t 的全部 eligible consumers。
- 对每个唯一 eligible producer 为 u、且有原 COPY_OUT consumer 或没有 eligible consumer 的最终输出 t，加一个虚拟 O_t，pipe=MTE3、时长下界 1，连 u→O_t。
- 计算操作保持 d(v)。不加固定 owner、提交顺序、特定 FIFO、任一方案的 spill/memory 边或“整分量不可分割”约束。

**定理 5（全局投影）。** 在唯一 eligible producer 的证明域内，每个成功官方计划都能投影为 H_evt 上不超过原 M 的 k 核 per-pipe 可行排布。

证明：一个共享输入可能在多个消费核有基础 IN。选其 **最早完成的那一份基础 IN**。每个消费者均在自己核心的初始 IN 之后执行；若它改接 reload，初始 IN→reload 的固定 MTE2 FIFO 仍保存该先后。因此所选 IN 的结束不晚于所有消费者开始。虚拟 I_t 放在所选真实 IN 占用区间的最后一个周期。不同输入 t 映射到不同基础 COPY，不会重复使用同一服务实体。

对最终输出，唯一 eligible producer 使它只有一个基础输出源核。该基础 OUT 即使经 incarnation 重接，也在 producer 完成之后；将虚拟 O_t 放在真实 OUT 的第一个周期。保留全部计算的真实区间。虚拟 COPY 区间是不同实际 COPY 区间的子集，因此不增加任何 per-pipe 并发；由引理 4 均容纳得下。所有 H_evt 的边满足先后关系，完成不晚于原 M。证毕。

特别地，虚拟共享输入是“理想免费广播”的放松，而不是声称官方只读一次；恰因为允许比官方更自由的共享，才可作为所有 owner 的共同下界。

**可计算界。** 在 H_evt 上计算 h、t，并令

\[
S_{p,a,b}=\{v:p(v)=p,\ h(v)\ge a,\ t(v)\ge b\}.
\]

对非空 S：

\[
L_{p,a,b}=a+\left\lceil\frac{\sum_{v\in S_{p,a,b}}d(v)}k\right\rceil+b.
\]

主推

\[
\boxed{L_{evt}=\max\{L_{old},\ CP(H_{evt}),\ \text{H_evt上的负载/不可分割界},\ L_{p,a,b}\}.}
\]

每一项由投影定理和命题 1/3 得到。把 L_old 保留在 max 中，确保新界绝不弱于旧界。它在某些图上严格加强：单个 10-cycle 计算，带一个 0B 必需输入和一个 0B 最终输出时，旧界为 10，新 CP 为 12。这是手工可核验结构，不能当作 500 格新结果。

**复杂度与预算。** 设增强图有 N 节点、E_H 条边。在 h/t 排序后，选 r 个 head 阈值，对每个阈值扫描按 tail 排序的节点并累加工作，可得 O(N log N+E_H+rN) 的核心算术成本；输入验证、确定性排序和证书序列化另计。全部阈值最坏 r=O(N)，得到二次扫描；也可固定 r=32 等预算。任意阈值子集都只使界变弱，不影响有效性。附件原型包括旧单阈值族与有限双阈值扫描，整体考虑确定性边排序可保守记 O((N+E_H)log(N+E_H)+rN)，空间 O(N+E_H)。

**证书格式与验证。** 至少保存图/config/官方关键源码/界程序哈希，eligible 与唯一生产者检查，虚拟边界节点及原 tensor/consumer/producer 身份，保留边的构造规则或出处，全部 h/t 标签及关键路径，最大窗口的 pipe、a、b、节点 ID、工作和与整数上整。验证器重建这些集合并核算不等式，不调用 Step2/3 或 E0。不能只保存一个“certified=true”或一个无法追溯的工作总量。多生产者/输入验证不通过时退回已适用的负载界或报 unsupported，而不把 unsupported 解释为无解。

**本轮实现与未完成项。** `r4_event_bound.py` 是新静态证书原型，额外保守拒绝 logical_tid 元数据；四个极小静态界和一个域拒绝测试通过，未验证全 100 图。它不编译任何官方计划，不产生新成绩。

现有保存证书只含必需输入/输出数量、字节总量，没有原 tensor 的完整关联信息。可从这些字段算的安全弱推论是

\[
L_{count}=\max\!\left\{\left\lceil\frac{W_{MTE2}+n_{in}}k\right\rceil,\left\lceil\frac{W_{MTE3}+n_{out}}k\right\rceil\right\}.
\]

本轮对全部 500 格算 max(L_old,L_count)，**新增加强 0 格**。完整增强 DAG/窗口界没有全图数值，不能给出更低的均值加速比上限。[BOUND-DATA]

### A4. 同一构造的逐 COPY 加权版：只在理想模型成立

将虚拟边界 COPY 时长换为

\[
w_t=\max\{1,\lceil size(t)/60\rceil\}.
\]

在定义为“每 COPY 初始工作 w_t，所有在飞 COPY 精确公平共享一个单位速率服务器”的实数模型中，任一实际 COPY 区间长至少 w_t。保留的因果仍成立。用该加权 DAG 得到 h、t；对任意所选必需 COPY 集 J，其实际服务均落在共同窗口，故

\[
\boxed{M_{ideal}\ge \min_{j\in J}h(j)+\sum_{j\in J}w_j+\min_{j\in J}t(j).}
\]

证明使用的是实际 COPY 占用区间内的服务积分；没有把所有服务擅自移到区间末尾、也没有把虚拟 COPY 当作全部可串行化的官方计划。head/tail 只是所有选中服务共同满足的前后计算条件；因此没有非法叠加独立 compute 和 DDR 下界。

**此式不用于冻结机器的 500 格严格 L。** `advance_ddr_work` 的残余舍入、1e-9 阈值、近并列投影和退休时残余移除使“归一化服务严格守恒”需要单独证明。前轮未验收的数值引理不在此补签；本轮也未完成通用误差界。本轮机器级主界正是通过只使用整数事件占用避开它，而不是声称解决了字节服务的误差封闭。

两个必要区分：

- 独立 M10 计算与另一个消费 600B 输入的 V1 计算，可让输入 COPY 和 M 并行于 0–10，V 于 10–11；计算界 10 加 DDR 10 得 20，却大于 11。此为手算反例，不是本轮评价。
- 两份 1B COPY 的逐项归一化工作是 2；byte-fluid 工作是 2/60。两种模型不能混称。零字节 COPY 也不能在事件或归一化模型中直接删除。

### A5. 现有证书到底验到了哪一层

100 份保存记录声明全部输入在唯一 eligible producer 域内，且 contracted-only 额外边计数为零。本轮独立检查 500 个 L 的最大值合成、1937 个 total-work、63 个 pigeonhole、965 个非空窗口的已存标量算术，并核对所有图/config 身份及 L≤U；与 DERIVED 的最大浮点显示差为约 2.84×10⁻¹⁴。[BOUND-DATA] [SUMMARY]

没有原图，不能独立证明这些保存的工作和、路径 op ID、成员数确实对应原始节点。没有 raw E0，不能独立重验 U 的时间线、合法性和回执。论文应写“源码定理与保存证书算术复核”，不要写“本轮重新认证所有图与 500 个 E0”。

## B. 500 格的独立差距复算

对每格：

\[
r^{M}_i=(U_i-L_i)/U_i,\quad r^{S}_i=U_i/L_i-1,
\]

\[
\Delta_i=A_i/L_i-A_i/U_i.
\]

前者为当前 Makespan 最多还能下降的比例；第二个为当前加速比最多还能相对增加的比例。全部都是有效 L 前提下的**上限**，不是实际未优化损失。

平均成绩与上限分别为 mean(A_i/U_i)、mean(A_i/L_i)。本轮用独立旧 per-cell CSV 的 `baseline_cycles` 提取固定 A，用完整摘要 `official.makespan` 提取 U。摘要的 `baseline.makespan` 是前版 P2 值，不能当 A；例如 008/K1 为 250437 而固定 A 为 487605。[BASE-A] [SUMMARY]

| 核数 | 当前 mean(A/U) | 上限 mean(A/L) | 均值差额 | 均值加速比相对增长上限 | 逐例 M 降幅上限均值 | 近 1% / 5% / 10% 数 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.206139235 | 1.242498920 | 0.036359685 | 3.01455% | 2.63840% | 51 / 81 / 90 |
| 2 | 2.316726858 | 2.480578992 | 0.163852133 | 7.07257% | 5.90958% | 29 / 62 / 81 |
| 3 | 3.235565608 | 3.703682921 | 0.468117314 | 14.46787% | 11.52031% | 12 / 32 / 52 |
| 4 | 3.971149310 | 4.922559198 | 0.951409888 | 23.95805% | 17.64093% | 11 / 33 / 42 |
| 5 | 4.549756997 | 6.108041537 | 1.558284540 | 34.24984% | 23.80605% | 6 / 23 / 33 |

“近 5%”定义 U/L≤1.05，可推出 U/M*≤1.05，而不是 (U−L)/U≤5%。表中所有核数均无 L=U。每格完整数值、源哈希、原件来源链接在 `r4-cells.csv`，统计在 `r4-audit.json`。[BOUND-DATA] [SUMMARY] [BASE-A]

K5 的三个容易混淆的数字：

- 均值加速比增长上限：34.249841%；
- 逐例 Makespan 降幅上限的平均：23.806054%；
- 逐例加速比相对增幅上限的平均：43.646456%。

第一个量是以当前逐例加速比为权重的 r_i^S 加权均值，不等于第三个量。K5 的逐例 Makespan 降幅上限中位数为 20.914063%，r_i^S 中位数为 26.448804%。这些不同聚合都不能替换彼此。

### B1. 五核差距贡献

按 Δ_i/100 排序，贡献的是全 100 图平均加速比上限与当前值的差，不是按原始 cycles 排序。

| 图/K5 | L | U | 对均值差额贡献 | M 降幅上限 | 加速比相对增幅上限 |
|---|---:|---:|---:|---:|---:|
| 044 | 14925 | 43795 | 0.068199 | 65.921% | 193.434% |
| 069 | 3722 | 11962 | 0.046535 | 68.885% | 221.386% |
| 005 | 12935 | 33515 | 0.045392 | 61.405% | 159.103% |
| 071 | 2918 | 9465 | 0.044847 | 69.171% | 224.366% |
| 086 | 16152 | 41466 | 0.044751 | 61.048% | 156.724% |
| 068 | 50529 | 134367 | 0.044713 | 62.395% | 165.921% |
| 088 | 34759 | 93547 | 0.044046 | 62.843% | 169.130% |
| 015 | 20300 | 40828 | 0.043929 | 50.279% | 101.123% |
| 010 | 11100 | 20820 | 0.036579 | 46.686% | 87.568% |
| 064 | 3573 | 11274 | 0.036545 | 68.308% | 215.533% |

前 5/10/20 图分别贡献总证书差距的 16.0256%/29.2332%/50.1699%。这是证书闭合工作的优先级线索，不是“这些图确实能提升这么多”。044 等图的大差距目前无法仅从本包分离为算法不足与松弛损失。[BOUND-DATA] [SUMMARY] [BASE-A]

| U/L−1 区间 | 图数 | 占总证书差距 |
|---|---:|---:|
| (0,1] % | 6 | 0.1168% |
| (1,5] % | 17 | 1.3899% |
| (5,10] % | 10 | 2.2494% |
| (10,25] % | 14 | 7.6280% |
| (25,50] % | 22 | 21.8278% |
| (50,100] % | 20 | 35.4207% |
| (100,inf] % | 11 | 31.3674% |

K5 在 1% 内的六图是 007、025、030、036、076、084；在 5% 内共有 23 图：
001、007、008、013、018、020、021、025、028、030、033、036、038、041、059、076、084、089、091、093、095、097、099。
这些小差距具有真正的条件近优意义；对大差距，既不能断言全部可达，也不能断言全部仅是下界松。

### B2. 6.108041537 的含义与可达性缺口

它等于 100 个固定 A_i/L_i 的算术平均。它是“逐图都能自由选择最优合法计划”的成绩上界，已经比固定单一构造家族更宽松。若要求均值恰好达到这个上界，因为各格 A_i/L_i−A_i/M_i^* 均非负，就必须逐格闭合 M_i^*=L_i；不能依靠某图超过界补偿另一图未达到界。

要证明实际还有某个正提升，需要给出更好的合法计划及成功官方值；要缩小不可达部分，需要更强全局下界或针对阈值的完整不可行证书。当前甚至没有一格 L=U，且下界允许忽略大部分通信/存储，因此 **真实剩余提升量仍未知**。本轮没有给它一个正的“至少还能提升”百分比。

## C. 迭代方向的可证范围

### C1. 代理目标与官方目标的关系

| 方向 | 代理目标 / 已证不变量 | 对官方 M 能推出什么 | 尚缺条件 |
|---|---|---|---|
| 超图字节最小割 | 唯一物理生产者域中，基础 COPY 字节 = 常数 + Σ_e w_e(λ_e−1)；二标签、固定外部 pins 的 cut 精确 | 精确优化该受限基础字节问题；不能推出 M 不增 | COPY 时间/顺序、并行、spill、memory、最终成功评分 |
| gap / 固定 owner 重排 | 在静态计算/通信日历中放置链；固定 owner 的 retime 保留基础 COPY 多重集 | 静态可行/较早 finish 只是该模型事实；M、spill 都可改变 | 全部真实 FIFO/内存边、DDR 竞争和容量 |
| 容量穿插 DP | 固定 owner/Pipe 字/投影前驱及真实 token，逐转移双池 alloc-before-free 可精确判定受限零 spill 存在性 | 证明该序的 Step2 存储性质；非 M 优化 | Step3 credit 边、全局时间、改变 owner 后的更大空间 |
| 接收闭包迁移 | 固定 producer a，对目标 b 的消费者全部移走且不回流，恰可删除该 a→b tensor COPY 对 | 删除该对及其基础工作；最终 OUT、其他目标和 direct COPY 不因此消失 | 重排、补偿迁移、其他 COPY 竞争、真正可行与官方收益 |
| 完整候选选择 | 候选均完整合法，评分精确且包含 incumbent，取 min M 或 min(M,DDR) | 对被保留 incumbent 的 M 条件不退化 | 每次保留同一完整 incumbent、成功评分身份、失败分支、E2 等价域 |

超图费用证明来自逐 tensor 计数：无 eligible producer 的输入为 size×消费核数；内部唯一 producer 的每个异核目的需要 OUT+IN，恰为 2size×额外触核数；最终输出为常数；direct 边单独计。不能把这份“基础 scheduled COPY”称为包含 spill 的总 DDR。[HYPER]

`binary_hypercut` 的网络精确求二标签连通度费用；`load_guarded_cut` 则在超载时把一个正工作量的移入单元固定回初始标签，最多单元数+1 次 flow。初始解对每次新增 anchor 都可行，因此最终基础费用不超过初始且满足 caps。**这不证明求得带负载约束的全局最小割**：anchoring 可能排除另一更好可行解。[CUT] [REFINE]

R07 的精确性不能从“每行可行状态是区间”获得：该性质不一定成立；双池最大值也不必保留逐池 Monge 性。只在辅助图无环、前驱投影有效和完整转移检查下使用 Boolean DP 结论。多个核不能用同一次其他核冻结的投影同时独立改序。[R07]

C01 的“编辑覆盖全部旧紧路径”只在固定加权图中有相应必要性。真实共享 DDR 下，一个未编辑 COPY 的 duration 也可能随其他 COPY 改变；故漏覆旧紧路径不能作为无官方收益的安全剪枝。069 新候选只有静态约束审计、COPY 模型 447992→447928 和固定 FIFO 界 8311，没有新 M。[C01] [069]

### C2. R05 是时间目标代理失效的实际反证

| 003/K2 保存方案 | scheduled COPY/B | spill/B | 官方 M/cycles | 固定 FIFO 下界 |
|---|---:|---:|---:|---:|
| R05 seed | 6351422 | 0 | 248166 | 230755 |
| R05 recovered | 5207554 | 0 | 254508 | 240126 |
| 当前 c665 | 4262874 | 0 | 245150 | 本项未提供 |

前两份少搬 18.00964%，反而慢 2.55555%。这直接反驳“基础字节下降即向官方时间最优前进”的一般推理，而且无需借 spill 解释。[R05] [PAPER]

固定 FIFO 界增加 9371，而松弛残差从 17411 减到 14382，恰有 9371−3029=6342。该等式只是两个量的差分恒等式；残差不是实测 DDR 等待，不证明哪个事件造成这些变化。[PAPER]

完整 500 格的既有数据也不是双目标单调：268 改善、232 相同、0 退化只是两固定版本配对；其中 199 格 M 降、DDR 升。额外 DDR 3043860416→4159738560 B，增加 36.659964%。55 格两者同降、14 格只降 M、232 格两者相同。[DDR]

### C3. 真正可进入论文的单调性定理

**定理 6（可行解—全局界区间单调）。** 同一图/config/k 下，保留上一轮完整合法 incumbent Π_t。新候选仅在成功精确评分并满足 U_{t+1}≤U_t 时接受，失败/未评分保持 Π_t。若 L 为同一有效正全局下界，则

\[
U_{t+1}-L\le U_t-L,\quad U_{t+1}/L-1\le U_t/L-1,
\]

\[
A/L-A/U_{t+1}\le A/L-A/U_t.
\]

若另有有效 L_{t+1}≥L_t，则

\[
[L_{t+1},U_{t+1}]\subseteq[L_t,U_t],
\]

\[
(U_t-L_t)-(U_{t+1}-L_{t+1})
=(U_t-U_{t+1})+(L_{t+1}-L_t)\ge0.
\]

相对证书差距与加速比区间宽度也不增，因为分子 U 不增、正分母 L 不减。

证明即由接受规则与有效性代入；没有使用代理改进。这个恒等式还能分别记录“方案变快”与“下界变强”：若 U 不变而 L 上升，证书更紧，但实际算法成绩完全没有提高。

**必须保留的局限。** 恒等式不保证存在新候选、不保证严格改善、不保证趋于 M*，更不提供速度。算法永远返回 incumbent 即满足不增却可能永久不最优。即使 M 为整数，严格下降次数至多 U₀−L，也只证明严格改善次数有限，不证明最后停在全局最优。

若按 (M,DDR) 字典序接受，M 相同才要求 DDR 不增；M 下降时 DDR 可增加。若需要两个指标分别单调，须另加 D_{t+1}≤D_t，这又可能排除有意义的 M 改进。论文应明确采用哪种目标。

### C4. 当前源码与上述假设并不完全相同

提供的 `adaptive_hypergap_guarded.py` 至多比较 baseline、gap、hypergap 三个不同完整计划，按 `_score` 返回值择优；没有把历史图号或历史最优表作为构造输入。该事实支持“有限完整候选选择”，不支持已经实现无限 incumbent 迭代。[MAIN]

本包没有 `_score` 定义、原生 E2 实现及完整传递依赖，因此本轮不能独立证明它对全部合法输入等同 E0。500 个选中计划的独立 E0 记录也不等于对所有被比较候选的普遍等价证明。[SUMMARY]

异常/评分失败分支返回 baseline；只有当 baseline 就是要保护的 incumbent 时，这个分支才满足定理 6。升级成真正迭代时，应先保存 incumbent 对象及其原评分，任何新构造/评分失败都直接返回它，而不是重建一个可能不同的默认 baseline。

268/232/0 不表示前版 2794ce 的完整结果在每次当前候选集中；它是配对观察，不能借接受定理反推候选包含关系。

“最多三候选”本身也不证明总体非暴力或低复杂度：候选内部可能有昂贵搜索。应同时披露链扫描、至多 k² 的配对、区域宽度、flow 次数、全部准备/验证/评分/失败回退及 I/O，不能把评分次数当整体复杂度。保存数据中的求解进程均值 4.029s、P95 18.841s、最大 40.187s 是原测共享主机条件的记录，不是本轮计时或跨机器提速保证。[GAP] [REFINE] [RESULTS]

## D. 可记录轨迹、停止标准与最小证伪

### D1. 轨迹不是代理曲线

每次记录至少包括：

```
instance = (graph_sha256, config_sha256, k, official_source_hashes)
incumbent_before = (plan_sha256, E0_result_sha256, U, DDR_partition, DDR_spill)
action = (constructor_version, structural_guard, region/neighborhood,
          proxy_before, proxy_after, proposed_plan_sha256)
score = (oracle_identity, success, objective, raw_receipt_sha256)
acceptance = (accepted, reason, incumbent_after_sha256)
bound = (scope='global', proof_kind, proof_source_sha256,
         certificate_sha256, witness, L_before, L_after)
cost = (cold_wall, parse, construct, compile, scoring, fallback, I/O,
        calls_attempted, calls_successful)
```

未知字段留 null，不得从摘要回填为已读 raw 回执；各版本 hash 可查但本轮不填造迭代时间线。全局界更新使用 max(既有合法界,新合法界)；若出现 L>U，先停止并审计身份/证明/记录，不把矛盾解释为突破。

理论轨迹可以分成三条：U_t（真实主目标）、L_t（放松证明）、D_t（DDR）；外加墙钟。不能只画字节或固定界残差并标注“向时间最优收敛”。

### D2. 可验证停止

- **最优停止：** L=U；或严格有效实数界 L>U−1 且官方值整数。
- **相对精度停止：** U≤(1+δ)L，证明 U/M*≤1+δ。均值成绩可用 mean(A/L−A/U)≤η 作为距离逐图最优均值不超过 η 的证书。
- **预算停止：** 明确记录未搜索区域和用尽的构造/评分/墙钟预算，不称局部或全局最优。
- **局部最优：** 只有声明的邻域已全部覆盖，每个邻居均有实际不改进评分、正确不可行证明或适用的候选下界拒绝，才可声称该邻域局部最优。guard 不支持不等于官方非法。若还允许同 M 降 DDR，单凭候选时间下界等于 incumbent 不能剪掉它。

### D3. 最小证伪设计与本轮执行记录

| 检验 | 可证伪的错误 | 本轮状态 |
|---|---|---|
| 计算→原 COPY→计算 | 把验证收缩边当时间边 | 已读源码并给手算；静态证书排除该边 |
| 0B 输入→10cycle 计算→0B 输出 | 删除 0B COPY、混淆 byte-fluid 与事件 | 静态旧 L=10、新 L=12；没有 E0 |
| 两消费者共享输入 | 将所有真实复制数固定进全局界或重复计同一虚拟输入 | 静态使用一个虚拟输入，旧 L=5、新 L=6 |
| eligible MTE2 操作与边界 IN | 漏计非 COPY MTE 工作 | 静态旧 L=3、新 L=4 |
| 多 eligible producer | 超域仍套路径证明 | 静态明确拒绝；不声称 E0 拒绝 |
| R05 保存 pair | 字节下降必使 M 不增 | 既有官方记录已经反驳，不重跑 |
| 完整 500 格配对/身份/不等式 | 错分母、漏格、假 DDR 单调、标量算术错误 | 本轮完成保存数据核对 |

未来若取得相同身份的 raw 图/计划/trace，可让新界验证器复算并逐项查 L_evt≤保存 M；一例违反就停止推广，先定位证明域、构图或整数事件引理。全部样本不违反仍只是实现一致性测试，不是全局证明的替代。本轮没有提出或执行全量新评分任务。

### D4. 论文落点与最终缺口

现稿 §5.5.2 可补充保留路径的 spill/FIFO 桥接与机器整数计算说明；新增一小节给整数事件增强图的投影定理，把加权 DDR 式标为理想模型；§5.6.5 放入本轮均值/分布表，并明确 34.24984% 与 23.80605% 的不同含义；§5.7/§5.8 加定理 6 及 incumbent/失败分支条件。无需把当前主方法描写成“已被证明朝全局最优收敛”。[PAPER]

仍缺的三类证据是：原图级证书复核；完整加权 DDR 的冻结机器误差证明；保留完整 incumbent 的真实迭代轨迹及与 E0 一致的评分域。当前能成立的积极结论是 **已有可行结果确实更好、部分格有小的条件近优差距、结构代理有明确局部作用、完整接受规则可保证证书单调**。不能据此补出剩余可达收益、DDR 同降或全局收敛。

## 交付与复算

`r4_saved_audit.py` 仅标准库，使用有理数进行主要算术；运行：

```sh
python r4_saved_audit.py EXTRACTED_R4_ROOT NEW_OUTPUT_DIRECTORY
```

`r4_event_bound.py` 是新静态界原型；只需原图和当前包中的固定验证器，不需要计划/评价器：

```sh
python r4_event_bound.py --evidence-root EXTRACTED_R4_ROOT \
  --graph GRAPH.json --cores 5 --head-budget 32 --output NEW_CERTIFICATE.json
```

此命令是交付接口，不表示本轮已经运行全图。`r4-static-fixtures.json` 保存极小输入与静态结果。CSV、JSON、脚本、本文及来源记录的大小和 SHA256 见独立 `R4-ARTIFACT-MANIFEST.json`；原始附件不修改。正文最终消息 ID 只能在消息发布后由归档方取得，本轮不伪造归档 ID 或宣称已写入组织仓库。

## 固定来源

以下全部来自本轮 MANIFEST 的组织主库完整 SHA 链接；没有用分支 HEAD 替换固定版本。

[P2]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/multicore_cut_evaluate_problem_2.py

[S2]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/schedule_step2.py

[S3]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/schedule_step3.py

[VAL]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/evaluation_validation.py

[STUB]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/stub_multicore_cut_and_schedule.py

[CONFIG]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/data/config.txt

[BOUND-PROOF]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md

[BOUND-CODE]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/global_bounds.py

[BOUND-DATA]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/results/a/q2-nikolastarx/goal-20260924/global-bounds.json

[SUMMARY]: https://github.com/huaweibei123/huaweicup2026/blob/1c00079aadbd071de62db17686d5ba3fed1da0f2/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json

[BASE-A]: https://github.com/huaweibei123/huaweicup2026/blob/178a3673bd238b20772211427b8134b6db35f5af/results/a/q2-yuanzhifang/feedback-20260924/full-coverage/all500/per-cell.csv

[RESULTS]: https://github.com/huaweibei123/huaweicup2026/blob/1c00079aadbd071de62db17686d5ba3fed1da0f2/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/RESULTS.md

[MAIN]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/adaptive_hypergap_guarded.py

[HYPER]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/hypergraph_cost.py

[CUT]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/binary_hypercut.py

[REFINE]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_hyperrefine.py

[GAP]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_candidate.py

[RETIME]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_retime.py

[FIFO]: https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/FIFO_BOUND.md

[C01]: https://github.com/huaweibei123/huaweicup2026/blob/b6aa25f02413d02892cbbabd33c993093bc18565/docs/a/q2-nikolastarx/PRO_C01_REVIEW.md

[R07]: https://github.com/huaweibei123/huaweicup2026/blob/b6aa25f02413d02892cbbabd33c993093bc18565/docs/a/q2-nikolastarx/PRO_R07_REVIEW.md

[069]: https://github.com/huaweibei123/huaweicup2026/blob/39a191604b841be257d3bc75d3ea28e088ce33ba/results/a/q2-nikolastarx/receiver-closure-069-static-20260925/README.md

[R05]: https://github.com/huaweibei123/huaweicup2026/blob/e6ae3699870c78b11c8c47b0fa9001249a428e1c/results/a/q2-nikolastarx/pro-r05-official-pair-20260925/verification.json

[DDR]: https://github.com/huaweibei123/huaweicup2026/blob/70f2e8bd8e850f1d49c924a86b654b29c24e087f/results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json

[PAPER]: https://github.com/huaweibei123/huaweicup2026/blob/615b1a5f7913a97fff8924cfec9936d3d303c6fc/paper/sections/a-q2.md

[PAPER-SOURCES]: https://github.com/huaweibei123/huaweicup2026/blob/615b1a5f7913a97fff8924cfec9936d3d303c6fc/paper/sections/a-q2-evidence.md

- [P2](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/multicore_cut_evaluate_problem_2.py)：`data/raw/a/official/code/multicore_cut_evaluate_problem_2.py`。
- [S2](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/schedule_step2.py)：`data/raw/a/official/code/schedule_step2.py`。
- [S3](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/schedule_step3.py)：`data/raw/a/official/code/schedule_step3.py`。
- [VAL](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/evaluation_validation.py)：`data/raw/a/official/code/evaluation_validation.py`。
- [STUB](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/code/stub_multicore_cut_and_schedule.py)：`data/raw/a/official/code/stub_multicore_cut_and_schedule.py`。
- [CONFIG](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/data/raw/a/official/data/config.txt)：`data/raw/a/official/data/config.txt`。
- [BOUND-PROOF](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md)：`docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md`。
- [BOUND-CODE](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/global_bounds.py)：`src/q2_nikolastarx/global_bounds.py`。
- [BOUND-DATA](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/results/a/q2-nikolastarx/goal-20260924/global-bounds.json)：`results/a/q2-nikolastarx/goal-20260924/global-bounds.json`。
- [SUMMARY](https://github.com/huaweibei123/huaweicup2026/blob/1c00079aadbd071de62db17686d5ba3fed1da0f2/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json)：`results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json`。
- [BASE-A](https://github.com/huaweibei123/huaweicup2026/blob/178a3673bd238b20772211427b8134b6db35f5af/results/a/q2-yuanzhifang/feedback-20260924/full-coverage/all500/per-cell.csv)：`results/a/q2-yuanzhifang/feedback-20260924/full-coverage/all500/per-cell.csv`。
- [RESULTS](https://github.com/huaweibei123/huaweicup2026/blob/1c00079aadbd071de62db17686d5ba3fed1da0f2/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/RESULTS.md)：`results/a/q2-nikolastarx/hypergap-full500-audit-20260925/RESULTS.md`。
- [MAIN](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/adaptive_hypergap_guarded.py)：`src/q2_nikolastarx/adaptive_hypergap_guarded.py`。
- [HYPER](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/hypergraph_cost.py)：`src/q2_nikolastarx/hypergraph_cost.py`。
- [CUT](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/binary_hypercut.py)：`src/q2_nikolastarx/binary_hypercut.py`。
- [REFINE](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_hyperrefine.py)：`src/q2_nikolastarx/gap_hyperrefine.py`。
- [GAP](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_candidate.py)：`src/q2_nikolastarx/gap_candidate.py`。
- [RETIME](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_retime.py)：`src/q2_nikolastarx/gap_retime.py`。
- [FIFO](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/FIFO_BOUND.md)：`docs/a/q2-nikolastarx/FIFO_BOUND.md`。
- [C01](https://github.com/huaweibei123/huaweicup2026/blob/b6aa25f02413d02892cbbabd33c993093bc18565/docs/a/q2-nikolastarx/PRO_C01_REVIEW.md)：`docs/a/q2-nikolastarx/PRO_C01_REVIEW.md`。
- [R07](https://github.com/huaweibei123/huaweicup2026/blob/b6aa25f02413d02892cbbabd33c993093bc18565/docs/a/q2-nikolastarx/PRO_R07_REVIEW.md)：`docs/a/q2-nikolastarx/PRO_R07_REVIEW.md`。
- [069](https://github.com/huaweibei123/huaweicup2026/blob/39a191604b841be257d3bc75d3ea28e088ce33ba/results/a/q2-nikolastarx/receiver-closure-069-static-20260925/README.md)：`results/a/q2-nikolastarx/receiver-closure-069-static-20260925/README.md`。
- [R05](https://github.com/huaweibei123/huaweicup2026/blob/e6ae3699870c78b11c8c47b0fa9001249a428e1c/results/a/q2-nikolastarx/pro-r05-official-pair-20260925/verification.json)：`results/a/q2-nikolastarx/pro-r05-official-pair-20260925/verification.json`。
- [DDR](https://github.com/huaweibei123/huaweicup2026/blob/70f2e8bd8e850f1d49c924a86b654b29c24e087f/results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json)：`results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json`。
- [PAPER](https://github.com/huaweibei123/huaweicup2026/blob/615b1a5f7913a97fff8924cfec9936d3d303c6fc/paper/sections/a-q2.md)：`paper/sections/a-q2.md`。
- [PAPER-SOURCES](https://github.com/huaweibei123/huaweicup2026/blob/615b1a5f7913a97fff8924cfec9936d3d303c6fc/paper/sections/a-q2-evidence.md)：`paper/sections/a-q2-evidence.md`。
