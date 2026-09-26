# P2 下界与树切分独立审计

审计时间：2026-09-24。审计者为同一 P2 任务的测量子 agent；只读冻结官方源码，增加纯结构测试和字节核验，不运行 solver、E0/E1/E2、Step2 或 Step3。父会话负责修改算法、冻结提交和对外同步。

结论：`bounds.py` 的三个松弛在下述**冻结数据域及共享服务模型**内成立；不能把 COPY 收缩后的所有边作为完成依赖，也不能把结论无条件推广到入口校验接受的任意图。`tree.py` 的最小开放块状态足以精确求解正整数标量权重的连通树切分；该最优值不构成完整 P2 Makespan 的最优性证书。

## 核验范围与固定来源

官方提交为 `45f647b395b84e9569f418fd33d62c2b8eb4d190`。以下文件的工作树字节与该提交的 Git blob 逐字节一致：

- `data/raw/a/official/code/multicore_cut_evaluate_problem_2.py`：端点与跨核 COPY 重建、全局 DDR 服务池。
- `data/raw/a/official/code/schedule_step2.py`：物理 incarnation 与 backing 的重命名。
- `data/raw/a/official/code/schedule_step3.py`：操作时长、DDR 判定、固定逐 pipe 顺序。
- `data/raw/a/official/code/stub_multicore_cut_and_schedule.py`：原 COPY 收缩与计划结构校验。

配置 SHA-256 为 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`，DDR 带宽为 60，官方 `PIPE_SLOTS=1`。本次读取全部 100 图，逐图 SHA-256 和配置 SHA-256 均与已有官方单核 receipt 匹配。结构结果为：

| 项目 | 数值 |
|---|---:|
| 原始操作 / eligible 操作 | 699118 / 634506 |
| 张量 | 747786 |
| 多个原始 producer 的张量 | 0 |
| 直接 op-op 边 | 0 |
| 零字节张量 | 0 |
| 最大单张量字节 / 最大原始 cycles | 294912 / 18480 |

所有图均有 eligible 操作。完整逐图身份、四份源码哈希、命令和时钟存于 `results/a/q2-yuanzhifang/feedback-20260924/theory/review-structure.json`。本次核验 UTC 为 15:32:34.133468–15:32:38.890176，内部墙钟 4.756613 秒，不是方案生成或评分耗时。重跑命令如下；输出采用排他创建，复核时请另选新文件名，保留原收据：

```text
.venv/Scripts/python.exe -X utf8 -B -m tests.q2.feedback.test_bounds --census results/a/q2-yuanzhifang/feedback-20260924/theory/review-structure.json
```

下面关于 spill 因果的证明以**原始张量至多一个 producer**为必要的审计前提。该前提比“至多一个 eligible producer”更强。普通官方输入校验没有这一限制；对多 producer 图，这份证明不作承诺。父会话已在 `bounds.py` 增加域外拒绝：原始 producer 超过一个、eligible 集为空、core 列表为空或含非整数/不在 1～5 的项、带宽为布尔值/非正/非有限均报错。空图和纯 COPY 图现有明确守卫，不再依赖 `max(empty)` 异常。审计补测包括“两个原始 producer 但仅一个 eligible”的情况，防止将证明域无意放宽。

## 共享 DDR 工作量为什么是下界

对重建出的每次端点 COPY，设 `d(t)=max(1,ceil(size(t)/60))`。

1. `_build_scene_b_tasks` 的每个 `add_copy_in/out` 生成一个明确的 DDR tensor 和一个本地 tensor；本地原 tensor 即便原先标为 DDR，也先转为 UB。因此这些新 COPY 一定满足 `_uses_ddr_bandwidth`，与原 tensor 的旧 `pos` 无关。
2. `_op_duration` 优先按 COPY 搬运 tensor 大小计时，不能沿用被删除的原始 COPY 的 `cycles`。这些重建 COPY 一次处理一个 tensor；Step2 重命名保持字节大小，不删除原操作，额外 spill COPY 只增加工作。
3. P2 发射时将 `float(duration)` 放入**所有核心共用**的 `ddr_remaining_work`。有 m 项活动时各获 1/m 的服务，总服务率为 1；已在时间片内完成的项被移除，剩余服务给其他项，不产生超额服务。
4. 没有 eligible producer、但有 eligible consumer 的 tensor，在每个消费核至少有一次输入 COPY。计数只取每个这种 tensor 一份，放宽多核复制成本。
5. 有 eligible producer，且有原始 COPY_OUT consumer 或没有 eligible consumer 的 tensor，在生产核至少有一次输出 COPY。计数同样只取一份。

将上述强制 COPY 的独占服务量求和得到 W。开始时刻非负，完成整个方案必须完成这些 COPY，故在共享服务模型中 `Makespan >= W`。输入和输出集合按是否有 eligible producer 区分，不会把同一 tensor 同时列入这两类；同一个被删除的 COPY 两侧的不同 tensor 则可能分别形成重建的输入和输出，必须按 P2 重建语义计数。

不能将这一项换为 `ceil(sum(bytes)/60)` 而声称等价：两个各 1 byte 的强制 COPY 各占 1 单位独占工作，总计 2，而合并字节取整仅为 1。后者仍可能是更弱下界，但丢失冻结实现的逐次取整信息。零字节 COPY 在源码中也占 1，尽管本批数据无零字节 tensor。

该证明针对源码定义的服务语义。实现用浮点水位和 `1e-9` 容差，测试没有穷举全部合法计划的 IEEE-754 舍入轨迹；本文不是该数值实现的机器证明。固定数据的小整数 COPY 时长本身可精确表示，不能因此把未完成的数值形式验证谎称已完成。也不能用“所有已测 Makespan 都大于 W”替代上述服务率论证。

## 原始依赖、spill 与 COPY 收缩的区别

`guaranteed_pred` 只纳入直接 eligible op-op 边，及同一原始 tensor 的 eligible producer→consumer 关系。它不把穿过被排除 COPY 的整条路径自动算作执行依赖。

对唯一 producer 的原始 tensor，逐条检查因果链：

- 同核且未 spill：生产者→原 tensor→消费者完整保留。
- 同核且 spill：生产 tensor 没有输入 COPY backing；第一次 spill 必须插入 COPY_OUT 建 backing。首次及后续 reload 的路径都经该 backing，仍须等待原生产者；所有生产边保持不变，消费者重接物理 incarnation。
- 跨核且未 spill：源生产者→源 COPY_OUT→外部 cross_link（还含非负固定延迟）→目标 COPY_IN→消费者。
- 跨核且目标 spill 复用输入 backing：reload 本身**没有额外的外部 cross_link**。因果仍成立的关键是原目标 COPY_IN 与 reload 都在 MTE2，Step2 把 reload 放在原 COPY_IN 之后的 `seq_ext`，冻结 Step3 按 `seq_ext` 的逐 pipe 投影固定 FIFO；P2 装载并保持该 FIFO。原 COPY_IN 未完成时，后续 reload 不能越过它。这一步不能仅靠改写后的 tensor RAW 边来证明。
- 图输入被 spill 后的 reload 同理；它至少仍需一次时长 d 的 COPY 才能提供消费者输入。图输出若重接 incarnation，沿首次生产/backing 或先前 reload 仍保留原生产因果，其最终强制 COPY 的独占服务时长至少 d。

于是对这些 guaranteed 边有 `start(v) >= finish(u)`。由输入端点下界递推

```text
F(v) = duration(v) + max(input_delay(v), max(F(u) : u in guaranteed_pred[v]))
```

归纳得到真实完成时刻不小于 F。对每个有强制输出的生产者再加 `output_delay`，取最大值得到端点路径下界。多个独立输入只取最大时长、多个输出也只取最大时长，属于放宽；未把 DDR 竞争重复加进路径。

唯一 producer 条件排除了“同一物理 tensor 同时由本核计算和远端 COPY_IN 生产、spill backing 只代表其中一支”的未证明情形。不能仅因为 100 图实测没有违反下界，就跳过这个域限制。

**COPY 收缩反例，未运行 E0。** 原始链为：

```text
u(M,100) → a(UB,60) → COPY_OUT → b(DDR,60)
         → COPY_IN → c(UB,60) → v(V,100)
```

计划校验将其收缩成 u→v；但 P2 重建时 a 是图输出，c 是图输入，b 没有 eligible 端点。不存在任何同时含 eligible producer 和 consumer 的原 tensor，所以没有把 u、v 相连的 cross_link。不同核心上可按源语义安排：输入 COPY 0..1、v 1..101；u 0..100、输出 COPY 100..101。两次 DDR COPY 不重叠，容量也充足。收缩后的 200-cycle 路径不是 P2 的必然完成路径；当前 `guaranteed_pred` 正确给出 100 的计算路径与 101 的端点路径。这个反例检查的是构造语义，不是新发布的官方成绩。

最后，每个 eligible 非 COPY 操作保持 `max(1,cycles)` 的固定时长；k 核每种 pipe 合计 k 个槽，故各 pipe 总工作除以 k 并向上取整是下界。三个已证明松弛取**最大值**仍是下界；相加通常会重复计算可重叠工作。逐图 B/L 的均值只能给平均加速比上界，不是可达到的预测或完成标准。

## 树 DP 状态支配与目标边界

审查对象是正整数权重、非空连通 in-tree、有效 children-before-parent 顺序、`1 <= requested parts`，实际 parts 为 min(requested,n)。`tree.py` 没有面向任意错误输入的完整参数校验；调用方必须保证这些前提。

固定阈值 B、节点 u、关闭块数 c，只保留最小开放块重量 x 足够：未来只会将 x 与另一开放块的非负重量相加，或切父边将它关闭。若 x1≤x2，同样的未来切/留决定凡对 x2 可行也对 x1 可行，且关闭块数不变。关闭块已经满足 B，树上没有其他通向祖先的边，因此无需记住它们的大小分布或身份。每个 child→parent 只有切或留两种状态转移，既不遗漏合法连通切分，也不会生成不连通块；回溯逐层 choice 可以恢复同一个可行状态。

阈值可行性单调，正整数权重允许在整数区间二分。结合根状态恰 k−1 个关闭块，可证明返回恰 k 个连通块的最小最大标量重量。标量状态支配不适用于附加边通信费用、pipe 工作向量、tensor 活跃集合或真实调度时刻；不能直接沿用此压缩构造所谓 P2 精确 DP。

一个更直接的边界例子：单核树有两个叶节点，分别 M=10、V=10，汇点 M=1，边为两个叶→汇。标量切分只能整树一块，C=21；按 pipe 与依赖允许两叶同时 0..10，汇点 10..11。仅这一计算模型就可有 11<C，因此 C 甚至不是一般多 pipe Makespan 下界。此例未运行 E0。当前 `TREE_DP.md` 已明确限制其最优性范围，无需修改其核心证明。

DFS 后序及各核投影能保证原 eligible 拓扑顺序和覆盖；它不是 spill 数、tensor 驻留量或官方运行可行性的独立证明。新增真实 COPY、内存边和最终执行合法性仍须由获批的独立 E0 验证。

## 本次验证结果与剩余事项

```text
.venv/Scripts/python.exe -X utf8 -B -m unittest tests.q2.feedback.test_bounds -v
```

初版 10 项纯测试通过（0.027 秒）；守卫落盘后新增 4 项拒绝测试，14 项全部通过，unittest 报 0.059 秒。随后补入 `bandwidth=True` 拒绝子例，最终 14 项仍全部通过（0.027 秒）。包括输入/输出判定、原 COPY cycles 排除、逐 COPY ceil、共享输入一次计数、零量规范化、COPY 收缩反例、直接依赖、不同 ID 的星/链/不均树全部切集 oracle，以及标量最优值的目标边界。树 oracle 对 3 种 5 节点树、32 种权重向量及 6 个 requested parts 共 576 个 DP 请求逐一核对最优值与回溯块数；仅用于小例测试，不进入 solver。父会话既有随机树测试仍独立保留。

未执行官方评分，未生成候选方案或伪造分数；审计者未修改 `bounds.py`、`tree.py`、`construct.py`。父会话已收紧 bounds 域声明和守卫。浮点执行器的全面数值形式验证、多 producer 域证明及全库可达性均不在这次通过结论中。真实树方法的首批成绩另见 `ROUND3.md`，来自父会话获批后保存的原件审计，不是这组纯理论测试的评分产物。

## 带前置与尾部路径的资源区间下界

新增 `energetic.py` 和 `bounds.py --energetic`，在同一唯一原始producer的证明域中加强前述松弛。这里只使用已证明保留的 `guaranteed_pred`，不把COPY收缩边重新放入路径。

令每个计算操作时长为 w(u)，保证开始时刻下界 R(u)=F(u)-w(u)。逆拓扑计算 Q(u)=max(output_delay(u), max(w(v)+Q(v): v为保证后继))，则任意合法完成时刻 T 中，u 必須在 T-Q(u) 之前执行完成。固定某个 pipe 与整数阈值 r,q，集合 S={u:R(u)≥r且Q(u)≥q} 的全部工作都处在 [r,T-q]，k核该pipe总服务率最多k。因此非空S给出

```text
T ≥ r + q + ceil(sum(w(u):u in S) / k).
```

取所有pipe和阈值的最大值，并与基础路径、pipe总负载、强制DDR工作下界取最大，仍是必要条件。向上取整适用于冻结整数cycle返回口径；前文关于浮点服务执行器尚未全面形式验证的边界保留。阈值只须取实际R、Q值：保持入选集合不变时提高阈值可加强约束，直到遇到某个入选操作的值。该离散族的最大值不等于全部可能调度约束的最强值，也没有给出可达性证明。

实现按R从大到小扫描。在排序后的Q坐标上加入操作w时，给所有q≤Q(u)的位置加w；线段树维护k*q+当前入选工作之和，用前缀加、前缀最大查询在O(n log n)内得到该族精确最强证书。只查询有非空集合的Q前缀，避免空集制造虚假大尾界。证书返回r、q、工作和操作数，并独立重算其集合总工作核对。每个核数/pipe分别计算，k≤5；端到端还需图索引及继承COPY收缩的实际成本，不能称全部输入上严格线性。

纯测试将小集合阈值全枚举作为独立定义oracle，另检查有公共V前置/后置且中间三个M操作的图：单核基础下界30，新区间界50，二核新区间界35。二核的三个不可分割10-cycle M工作实际至少占20周期，因此界35不可因此视为最优解40。这也明确展示该松弛仍可能不紧。COPY桥反例在新区间界中仍为101，没有误恢复200-cycle伪路径。

此新增理论尚未执行全100图扫描，也没有任何新solver/E0调用；不能用其未测数值宣称已经接近上界。独立源码审计与实际评分仍是不同证据。


后续交叉核对：2026-09-24读到P3固定9c8bd47的 `src/q3_yuanzhifang/head_tail_bound.py`，其已独立实现同一个完整阈值族与O(n log n)扫描，并已做全100图核验。本实现早期编写时尚未读取该源码；不把相同理论重新宣称新发现，也不重复整库扫描制造工作量，后续优先核对其固定数据与本域守卫。P3的原tensor逻辑别名守卫提示了必须明确的输入边界，本实现新增拒绝原始logical_tid字段；已测冻结图是否满足须按原件/已有census核定，不仅依赖方法名。新增两项路径/区间测试后20项通过0.085秒；别名守卫测试另行执行记录。
