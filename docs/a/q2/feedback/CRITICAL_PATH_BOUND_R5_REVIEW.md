# P2 的廉价 Pipe / 关键路径下界：条件审阅 R5

范围：只读冻结 P2、`schedule_step3.py`、入口 COPY 收缩代码及现有构造接口；0 真实图求解、0 Step2/Step3/E0，未修改算法。此处讨论固定、合法且**成功执行**的 singleton P2 候选 B。在精确工作守恒 DDR 模型中，以下三项均为 Makespan 下界，故可取

\[
L_B^{\rm ideal}=\max\{W_B,\;P_B,\;D_B\}.
\]

`W_B` 是 P2 基础 DDR COPY **逐条**独占服务和，0 B COPY 仍计 1；忽略 spill 只使它变弱。`P_B=\max_{c,p}\sum_{u:\,core(u)=c,\,pipe(u)=p}d_u`，其中只计 eligible op、`d_u=max(1,cycles_u)`；冻结全局每核每 Pipe 一槽，COPY 与 spill 竞争该槽只能增加时间。它不是每核所有 Pipe 工作量之和。`D_B` 是下面物理依赖图上的最长路径。可把此 `L_B` 作为已有 `U_A` gate 的更强**理想模型**比较量；本次没有验证它会改善任何真实格，也不据此宣称官方机器 Makespan 严格有界或 E0 必然成功。

## 关键路径图的安全构造

顶点仅为 eligible op。对每个原图真实 tensor，若有**唯一 eligible 原始 producer** `u` 和 eligible consumer `v`，加入 `u→v`；对每条原图直接 eligible op→op 边也加入一条。原图 tensor 没有 eligible producer 时是图输入，不凭空添加 eligible 前驱；原始 COPY_IN/COPY_OUT 不作为顶点。若同一 `u→v` 同时有 tensor 和 direct 边，可保留平行弧或合并为最大权弧，不能把其通信时长串加。先完成官方 `derive_multicore_plan` 校验，再按 P2 物理 core 映射定权：同核弧权 `\ell=0`；跨核真实 tensor 弧权 `\ell=2\nu(size_t)+\delta`；跨核 direct 弧权 `\ell=2\nu(max(0,int(data_size_e)))+\delta`。`\nu(s)=max(1,ceil(s/bandwidth))` 按 P2 冻结 COPY 实际服务量的适用数值域计算；固定配置 `bandwidth=60`、`\delta=500`。跨核每条物理连接的 `COPY_OUT` 在 producer 后，`COPY_IN` 等待源 COPY_OUT 完成并再等一次固定 lag，consumer 在目的 COPY_IN 后。DDR 公平竞争只能延后每次 COPY，故这段依赖至少消耗上述权重。**同一 tensor 同一生产/消费核对只生成一对 COPY**，不能按每个 consumer 重复增加 `W`；但每个 consumer 都受这对 COPY 的先后约束。

令 `F(v)=d_v+max(0, max_{(u,v,e)}[F(u)+\ell_e])`，`D_B=max_v F(v)`；按**物理弧构成的 DAG**拓扑序计算。多个输入必须取 `max`（最晚前驱），不能求和；多条同端点并行弧只取最大权。若图为空，定义 `D_B=P_B=0`。合法性校验的 contracted op DAG 可提供一种拓扑顺序，但**不可把其所有弧当作这里的物理弧**。Step3 添加的内存复用边和逐 Pipe FIFO 可以忽略，下界只会更松；`core_schedules` 给的是优先级/子图顺序，不是所有 eligible 节点之间的强制串行执行边。

证明对每条保留的物理弧逐段归纳：本地 tensor/direct 保留 `u` 完成后 `v` 才可发射；跨核弧经 P2 重建 COPY 对及 `external_release`，且每个 COPY 在精确模型下耗时至少其独占服务。于是每个 eligible 结束时刻不少于 `F(v)`，所以 `M_B≥D_B`。所有 COPY 共享总速率 1，故 `M_B≥W_B`；单槽 Pipe 不可能在小于其 eligible 工作和的时间内完成，故 `M_B≥P_B`。三条独立下界取最大，而不是相加，避免把可重叠工作重复计时。

## 小手算与失效边界

两核、两个 eligible：`u` 在核 0 的 M Pipe 耗 2 cycle，`v` 在核 1 的 V Pipe 耗 3 cycle；真实 tensor `u→t→v` 大小 120 B。每条 COPY 为 2 cycle，`W_B=4`，`P_B=3`，路径 `D_B=2+2+500+2+3=509`，所以理想下界为 509。若另有一条同端点 0 B direct 弧，它的路径贡献为 `1+500+1=502`，与 tensor 弧取 `max(504,502)=504` 的通信间隔，而不是合计 1006；总 `W` 则仍须计入这条 direct 的两条实际 COPY。三核两个各 1-cycle 前驱通过各自 0 B direct 边汇入一个 1-cycle 目标时，每条路径为 504，目标等待两条输入的**最大**完成时刻，不是两个 502-cycle 通信时长之和。

重要反例：原图可有 `eligible u→tensor t→原 COPY_OUT→DDR tensor→原 COPY_IN→tensor s→eligible v`。入口 `_contract_excluded_copy_nodes` 会为合法切图/排序保留 `u→v` 的**可达性**，但 P2 重建时分别为 `t` 生成最终 `COPY_OUT`、为 `s` 生成图输入 `COPY_IN`，它们没有共享 `cross_link`；若把 contracted 弧套用 `2\nu+500`，会制造不存在的跨核物理等待。即使同核，子图先后优先级也不能替代实际强制执行依赖。故只从 P2 实际保留/重建的真实 tensor producer-consumer 和 direct eligible 边建关键路径，不沿被收缩的原 COPY 链外推。多个原始 producer 会使单一 `u→v`/一对 COPY 的简化模型失效，应沿现有 `TensorIndex` 唯一 producer 守卫拒绝；`logical_tid` alias 的真实物理身份未证，同样拒绝下界增强，不能把逻辑 ID 当唯一物理 token。原图输入与最终输出 COPY 未进入 eligible 路径，只在 `W_B` 计入。

若已建 `TensorIndex`、core 映射及基础 COPY profile，逐核 Pipe 累加为 `O(V)`，物理弧与一次 DAG 最长路径为 `O(V+E+I)`（`I` 为 tensor 触碰数；唯一 producer 使 tensor fanout 扫描为线性），COPY 核对计数另有至多 `O(k²T)`，与已有 profile 同阶；官方 plan 校验、排序和候选构造成本另计。不能把本下界的线性扫描宣传为整个求解器端到端线性或更快。

**机器层限制：**冻结全局 DDR 残余用 binary64、`1e-9` 阈值和整数 `ceil(cursor-1e-9)` 投影。理想每条 COPY 至少 `\nu` 和总工作量至少 `W_B` 不自动成为返回的机器时钟严格下界；大 direct `data_size` 的浮点 `math.ceil(size/bandwidth)` 还须与 profile 一致。没有独立的向下安全误差证明和两候选成功返回依据时，`max(W_B,P_B,D_B)` 只能作为有条件理想下界或启发式 gate 信号，不能贴“官方严格证书”。

源码锚点：`stub_multicore_cut_and_schedule.py:20-43,70-89,114-196`；`multicore_cut_evaluate_problem_2.py:133-234,323-379`；`schedule_step3.py:74-92,675-703`。本机工作树在审阅期间由主会话并发推进；此文只依赖冻结官方文件与题设条件，不引用新的真实测量。
