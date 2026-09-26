# 完整弱分量的 DDR 工作量筛选界：条件证明与机器层限制

2026-09-25 独立只读审计。核对冻结 `multicore_cut_evaluate_problem_2.py`、`schedule_step2.py`、`schedule_step3.py` 和 `evaluation_validation.py`；本次 0 新 solver、0 Step2 前缀、0 E0，未实现筛选器，也未向外部 Pro 发问。以下区分精确数学服务模型、冻结 Python 事件实现及尚待实验的算法用途。

## 命题 A 的准确域

设 A 是**合法 singleton 计划**，每个 eligible 弱连通分量完整落在一个核，P2 重建后 `cross_links=[]`，`physical_frontier` 对**每核全部真实本地 token**获证，且 Step2/Step3 正常完成。因此 A 无 spill，运行中的非 eligible 操作只剩 P2 生成的基础 DDR COPY；没有跨核 `OUT→IN` 正延迟。仅说“没有跨核 eligible 依赖”还不够，筛选器应显式核对 `cross_links=[]`，并保留 `derive_multicore_plan`、Step3 及全局合法性守卫。P2 每核合成一个 Task、重建端点 COPY 与 Step2/3 的入口见 `multicore_cut_evaluate_problem_2.py:61-282`；全局跨核 release 见 `:323-381`。

令 `C_c=Σ_{eligible u on c} d_u`，其中 `d_u` 必须是冻结 `_op_duration` 的值（普通 eligible 操作的 `max(1,cycles)`），不能直接求原始 cycles。对**每一个基础 COPY 操作**单独计算 `d_v=max(1,ceil(bytes_v/B))`，包括 0 B COPY 的 1 cycle；定义 `W_D=Σ_v d_v`。这些 COPY 的确是 DDR 服务者，判断准则应与 `_uses_ddr_bandwidth` 一致（`schedule_step3.py:74-90`）。不要用 `ceil(Σbytes/B)` 代替逐 COPY 取整，也不要把原始 COPY 节点再算一次。记 `U_A=max_c C_c+W_D`。

**精确、连续、工作守恒的公平共享模型下，`M_A≤U_A` 成立。** 取最后完成的核 c。在 `[0,M_A)` 任意时刻，若全局没有正 DDR COPY 在服务且 c 尚未完成，则 c 必有一个自己的 eligible 操作运行：其本地 data/memory/FIFO 图有限无环，所有无前驱的 pipe 队头立即发射，且没有跨核 release 或额外 subgraph barrier。即使 Step3 的 allocation/free 复用使 c 的某一 pipe 等待，另一条尚未完成的本地前驱链上仍有操作运行；若该操作是 COPY，则全局 DDR 正忙。把时间划为“DDR 忙”和“DDR 不忙”：前者总长至多 `W_D`（公平池总速率 1），后者可逐段计入 c 的 eligible 工作，总长至多 `C_c`。故 `M_A≤C_c+W_D≤U_A`。每 pipe 一槽、Step3 编译的 memory edges 与 FIFO 词，以及全局事件循环的队头发射规则见 `schedule_step3.py:30,583-703`、`evaluation_validation.py:226-254`、P2 `:381-487`。证明不要求本地所有 eligible 工作串行；因此上界通常很松。

此证明依赖**无未建模等待**。若 A 有任何跨核 link，即使 eligible 投影似乎无直接边，目标核可以在没有本核工作也没有当前 DDR 服务时等待固定 lag；该等待不能计入 `C_c+W_D`，上界可能失效。若 Step3/全局执行报环、死锁或超过 `max_iter`，根本没有返回的 `M_A` 可比较。若存在未计入的非 DDR 操作、spill、或把需消耗 DDR 的 COPY 漏算，同样不能使用此式。内存 free/alloc 本身在最终全局阶段表现为已编译的依赖边，而不是另收时间费用；但必须以成功编译且包含这些边为条件（P2 `:248-270,295-297`）。

## 命题 B 与筛选规则

对另一个**固定、合法且成功执行的**方案 B，即使它有 spill 和跨核 link，令 `L_B` 仅为其规范化**基础** DDR COPY 的逐条独占服务和。它不含 spill COPY，所以在精确工作守恒 DDR 模型中 `L_B≤M_B`；跨核 lag、pipe、eligible 工作只可能提高 M。B 的基础 COPY 必须按它自己的核映射和 P2 的输入/最终输出/每个跨核核对/direct 边规则展开，不能从 A 的字节数或 `added_copy_bytes` 反推；P2 `:135-238,244-280`。因此在上述条件同时成立时，`U_A<L_B` **严格推出两份固定结构计划** `M_A<M_B`，无需在线 E0。它不证明 A 是全局最优，也不保证下一候选的求解墙钟更短。很多 B 的基础 COPY 较少，此界可能完全不触发，尤其 spill 是其主要损失时；不能据此判断 A 无益。

**冻结 Python 的机器级“严格证书”暂不可直接宣称。** P2 把 DDR 剩余工作转为 `float`，以 `1e-9` 为完成/并列阈值，并用 `ceil(cursor-1e-9)` 投影整数结束时刻；退役和发射仍以这些整数事件推进（P2 `:329-373,425-516`）。数学上的总速率积分和“无空转”论证不自动证明任意合法大整数/任意有限带宽在该浮点实现中逐周期成立。单纯加一个未经证明的固定 `+1` 或 `+N_COPY` 不够：误差上界需覆盖数值量级、事件次数、近并列完成和取整传播。若要**无需 E0 的官方严格筛选**，应对所用配置证明保守机器误差 `ε_A,ε_B`，并要求 `U_A+ε_A<L_B-ε_B`；或使用精确/向外舍入的服务演算并证明其与冻结事件结果的关系。在此之前，`U_A<L_B` 只能作为有理论依据的**启发式预筛**，不能标为官方已证 M 改进。成功返回的 `max_iter` 条件也须保留。

## 020/045 的静态适用性与成本

现存 k5 原件显示：020/045 旧 `packet_eft` 计划保留全部弱分量、不产生额外 DDR 或 spill；固定 gap 保存计划分别跨核拆开 271/288、68/68 个弱分量，五核均有拆分，且有大量分区 COPY 与 spill（见 `GAP_K5_NEXT.md` 的原 run 路径）。这使“完整分量 A 对拆分 gap B”成为**结构上合适**的对照；它不说明 A 的 `physical_frontier` 一定获证，也不说明 `U_A<L_B`，本次没有生成 A 或计算新 M。F1 的 word 守卫不覆盖这两图，现有整核容量重排也不能直接修补带拆分分量的核。已有保存结果仅可用于研究优先级和静态身份核查，不能成为求解时的按图号赢家规则。

若 A/B 两份完整候选已存在，规范化基础 COPY、逐条计算 `d_v`、累加每核 eligible 工作与物理容量事件峰值，增量规模约 `O(V+E+I+k²T)`，其中 `I` 是 op–tensor 触碰数、`T` 是 tensor 数、`k≤5`；实际 `derive_multicore_plan` 的排序/图验证和候选构造成本另计，不能声称整条求解器线性。筛选只比较**一对事先定义的结构候选**，不逐图查询旧结果；不等式失败就保持“未判定”，不能反向宣称 B 更优。后续最小证伪应固定少量完整分量 A/拆分 B 结构，记录两者真实 COPY 多重集、证书、`U_A/L_B`、官方 M 和端到端墙钟；若数学界违反、机器裕量不能封闭或时间成本压过收益，停止把它推广为确定性门。
