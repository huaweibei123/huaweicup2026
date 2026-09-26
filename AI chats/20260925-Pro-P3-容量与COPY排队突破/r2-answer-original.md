## 实际读取的文件与本轮核验范围

**新包已解压并实际读取。** ZIP 为 **81,961 bytes**，SHA-256 为：

`20323b3cf625a6210d7fa619b22fc7d59c6767b9c3d543c0864eeb2e0640f586`

包内共 **20 个文件**；`input-manifest-r2.json` 登记的 **18 项**大小及哈希全部吻合，另外两项是问题文件和清单本身。清单声明来源提交为 `1673d9945ffe264873e252d71535e6995a06085f`；我没有将此表述为对私有仓库 HEAD 的联网核验。

| 范围 | 本轮实际读取情况 |
|---|---|
| 问题及算法 | `r2-question.md`；完整读取 `wave_tail.py`、`wave_capacity.py`、`whole_job_bound.py` 和 `test_wave_tail.py`。测试源码已读，**未运行包含构造调用的测试集**。 |
| 新包说明与记录 | `WAVE_TAIL.md`、`WAVE_CAPACITY.md`、`WHOLE_JOB_BOUND.md`、`PRO_R1_READBACK.md`、`OFFICIAL_OBJECTIVES.md`；两个实验 `REPORT.md`；完整解析 whole-job 证书、100 图 head/tail JSON、读取分账 JSON、wave-tail 运行 manifest。 |
| 官方语义 | 新包冻结 config、P3 evaluator、Step2 的相关完整执行路径；首包 Step1，以及 Step3 的时长、固定 Pipe 顺序、内存补边和执行准备路径。下文简称 **E3、S2、S3**。 |
| 首包原始数据与依赖 | 重新完整解析 `case_067.json`；读取 `baseline.py` 的索引路径和 `construct.py` 的 `SharingIndex`；重新校验首包清单 59 项。 |
| 未取得或本轮未重读 | **12,237,901 对应的原计划及原始 E0 result/trace 没有取得**；044 新 37,581 的完整计划/result/trace、新版 `pipeline_capacity.py` 未包含在增量中，本轮只读取其报告。原题 PDF、首轮旧方案的八组完整 trace 本轮未重新通读。 |

此外，本轮**实际运行了静态图索引、原作者 guard/DP、独立 whole-job 证书复算，以及符号顺序的最长路计算**；没有调用候选 `build/main`、`derive_multicore_plan`、Step1/2/3 或 E0，没有落盘正式提交计划。这不改变原 wave-tail 批次 **0 cold / 0 E0** 的历史事实。

**本轮最重要的结论：不必立即放弃“只切一个余量作业”，但必须放弃“所有尾段都追加在相同末波”的相位安排。** 原安排的主要损失，在零 COPY 松弛里就已经出现；不是补上四个 500-cycle 常数就能解释或修复。

---

# A. 正确下界、原构造的静态诊断与反例

## A1. Whole-job 排除成立，没有发现漏洞

我重新执行了独立 `certify`，**逐分量节点集哈希、分量数量、M/V 工作量等全部返回字段均与包内证书一致**：

\[
J=71,\qquad L=124,\qquad
W_M=829\,792,\qquad W_V=33\,248.
\]

原始 COPY 均通过源/汇端点守卫；另一个使用官方 COPY 收缩逻辑建立的索引得到相同作业结构。因此，不存在“漏掉 COPY 桥接，误认了 71 个独立分量”的证据。

每个完整作业固定归一核时，至少一核承担 15 个作业。官方每核 M Pipe 只有一个在飞操作，普通计算操作按其 `cycles` 服务，故：

\[
M_{\mathrm{E0}}\ge15W_M
=\boxed{12\,446\,880}
>12\,237\,901.
\]

该证明不要求作业连续执行，不受 wave 宽度、Cache 命中或 COPY 调整影响。**首轮完整作业 wave 的主指标路线应撤回；其 DDR、墙钟价值可以另议。**  
来源：`whole_job_bound.py:16–75`；`whole-job-bound-067-k5.json`；S3 `27–37、74–82`。

067 的通用 head/tail 界也能从当前原图直接复核。每个作业的独占输入、最终输出均为 16,384 B；最后一个 M 后还有两个各 1,072-cycle 的 V。因此所有 M 工作必落在长度不超过 \(M_{\mathrm{E0}}-274-2418\) 的时间窗口内：

\[
M_{\mathrm{E0}}
\ge274+\left\lceil\frac{71\times829\,792}{5}\right\rceil+2418
=\boxed{11\,785\,739}.
\]

这里独占输入首次读取不能靠其他核预热，最终 COPY_OUT 使用 DDR。**这是必要界，不是最优值，也不是已经找到相应计划。**

## A2. 对指定 singleton 顺序，应使用“原依赖＋必然 FIFO＋最快 COPY”的最长路界

对一个固定的两字段方案，构造只用于分析的约束图 \(H\)：

1. 保留原始计算依赖。
2. 对每核的 M、V 操作，按 singleton 子图顺序加入相邻 FIFO 边。
3. 对官方必然生成的输入、输出、跨核 COPY，加入相应节点及数据边。
4. 对 **不同子图桶**内的同 Pipe COPY，加入稳定分桶必然产生的前后关系；同桶内尚未运行 Step1 才能确定的相对顺序，**不擅自补入**。
5. 跨核加入：
   \[
   \mathrm{COPY\_OUT}\xrightarrow{500}\mathrm{COPY\_IN}.
   \]

COPY 使用乐观服务时间：

\[
d^-(\mathrm{OUT},B)=\max(1,\lceil B/60\rceil),
\]

\[
d^-(\mathrm{IN},B)=
\begin{cases}
\max(1,\lceil B/60\rceil),&能证明首次必 miss，或条目大于 Cache；\\
\max(1,\lceil B/250\rceil),&其余情况允许乐观命中。
\end{cases}
\]

**不能把跨核激活读一概按 DDR miss 计入下界**：源端 spill/reload 等行为可能影响 Cache；允许最快命中更安全。

对节点 \(v\)，保存最早完成状态：

\[
F(v)=d^-(v)+
\max_{u\to v}\{F(u)+\lambda_{uv}\}.
\]

\[
L_{\mathrm{FIFO}}=\max_vF(v),\qquad
M_{\mathrm{E0}}\ge\max\{L_{\mathrm{FIFO}},L_{\mathrm{head/tail}}\}.
\]

这是可证必要界，因为它只删除约束、缩短服务时间；它没有加入任何 E0 不保证的顺序。S2 保留原操作相对序，S3 固定其 Pipe 投影，最终 E0 只发射队首。容量补边、spill COPY、共享带宽竞争和未知桶内次序被放松，故**不能将这个最长路结果当作 E0 上界或预测值**。  
来源：E3 `51–67、166–242、436–474`；S2 `443–456`；S3 `281–287、595–609`。

特别注意：尾作业并非只有四条相邻段通信。按本轮得到的切点，原图有 **12 个实际 source-core→target-core COPY 对，单向字节和 61,440 B**，包含跨多个段的残差。源、宿两端基础搬运合计 122,880 B。DP 的切点 frontier 和 **131,072 B** 不是这个实际通信量。

因此，递推必须保留这些真实前驱的完成状态，不能只保留“上一段最后一个操作的释放时刻”。

## A3. 原末波追加方案，已经几乎用完了赢当前最佳的空间

本轮对真实 067 静态执行原 guard 与两遍 DP，得到：

```text
guard：通过
bmax：6
cuts：[0, 20, 44, 66, 94, 124]
尾段 M 工作：[157104, 166368, 157104, 174608, 174608]
尾段 V 工作：[  9744,   4512,   1648,   3376,  13968]
每核完整作业 M 基础工作：14×829792 = 11617088
minimax 工作量目标：11791696
```

这些是**本轮静态执行所得参数，不是历史中止批次生成过的计划，也不是官方运行结果**。

三个符号顺序的必要界如下。后两种构造在 B 节定义。

| 符号顺序 | 原计算依赖＋M/V FIFO，零 COPY | 加最快跨核 COPY 路径 | 再加必然输入/输出、已知 COPY 桶间 FIFO |
|---|---:|---:|---:|
| 原 `wave_tail`：同末波、尾操作追加 | 12,218,400 | 12,220,723 | **12,221,271** |
| 主路线：首波容量阶梯、尾操作优先 | 11,856,672 | 11,856,672 | **11,857,220** |
| 备用：完整作业前缀隔开尾段 | 11,886,192 | 11,886,192 | **11,886,740** |

完整静态记录见:chatgpt-content-reference{index="0"}[本轮核验记录](sandbox:/mnt/data/p3r2/r2_static_audit.json)。

原末波方案中：

\[
12\,218\,400-11\,791\,696
=\boxed{426\,704}.
\]

**不计任何 COPY，尾部因果依赖与计算 FIFO 就让必要界比工作量峰值高出 426,704 cycles。** 四个相邻跨核路径的最快 COPY＋释放延迟，在该最长路径上再增加的只是 2,323 cycles；输入/最终输出另加 548。

所以当前最主要问题不是“500 是否太大”，而是**各核在同一末波追到自己的尾段入口后，队首等待沿尾作业传播，把多个核的剩余工作串联起来**。

原方案最后的必要界仍低于 12,237,901，故不能严格宣布它不可能赢；但只剩：

\[
12\,237\,901-12\,221\,271
=\boxed{16\,630}
\]

cycles 容纳所有尚未计入的影响。**我不建议把本轮有限 E0 预算优先花在它上面；这是预算选择，不是数学排除。**

## A4. 一个很小、可嵌入官方语义的反例

取两个核、三个相同串行作业 \(A,B,T\)，每个有四个 M 操作，每操作 1 cycle；中间 tensor 均为 1 B，共同输入只在首位置使用，容量充足。每核一个完整作业，尾作业 \(T\) 在位置 2 切开。原末波追加顺序为：

```text
core 0：A0, T0, A1, T1, A2, A3
core 1：B0, B1, B2, T2, B3, T3
```

两核工作量均为 6。零 COPY 理想模型却存在长度 7 的必然路径：

\[
A_0\to T_0\to A_1\to T_1
\to T_2\to B_3\to T_3.
\]

这里 \(T_1\to T_2\) 是数据依赖，其余相关关系由 M FIFO 固定。核 1 的 \(B_3\) 本可做独立工作，却不能越过未就绪的 \(T_2\)。

采用冻结配置后，1 B 跨核路径至少需要：

\[
1+500+1=502.
\]

于是这个拆尾方案至少需要 \(7+502=509\) cycles。相反，不拆作业、两核分别放两个和一个完整作业时，没有跨核释放等待；所有计算和必需 COPY 的串行服务量合计仅 17 cycles，容量又足够容纳全部数据，因此这个例子中整作业方案的官方执行也不会达到 509。

这是解析反例，**没有运行该例的 E0**。它说明降低负载峰值不保证降低 Makespan。

COPY FIFO 还有一个独立风险：目标核若形成

```text
MTE2：[等待远端的 I_tail, 已可读取的 I_local]
V   ：tail consumer
M   ：independent consumer
```

即使 M/V 计算队列互不阻塞，`I_local` 也不能越过 `I_tail`。这正是为什么仅有计算 FIFO 界还不够，而上述必然 COPY 桶间约束值得保留。

---

# B. 优先路线：把尾段放到首波，用容量阶梯建立相位差

## B1. 主路线：`wave_stair`，仍然只切一个作业

保留原两遍 DP 得到的切点，不搜索新切点。仍然把前 70 个完整作业均分给五核。

修改两处：

**第一，尾段移入首波，而非末波。第二，同一位置先排尾操作，再排该核首波中的完整作业操作。**

不同核的首波完整作业数不再相等，而形成递增阶梯。这个阶梯不是人为时间戳或等待，而是实际可执行的独立工作。

### 容量阶梯的直接计算

令

\[
\Phi_r(p,b)=W_r(p)+A_r(p)
+(b-1)\max\{F_r(p),F_r(p+1)\}.
\]

从各空间约束求每个位置的最大代理宽度 \(\beta(p)\)。对尾段 \([a_c,a_{c+1})\)，首波完整作业数允许上限为：

\[
U_c=
\min_p\left[
\beta(p)-\mathbf1\{a_c\le p<a_{c+1}\}
\right],
\]

再截到不超过该核完整作业数 \(q\)。

取：

\[
h=\min_c(U_c-c),\qquad n_c=h+c.
\]

若 \(h<1\)，这条阶梯构造不适用；不修改容量、不硬塞额外作业。

067 静态得到：

\[
U=[6,6,5,5,6],\qquad h=2,
\]

故首波完整作业数为：

\[
\boxed{n=[2,3,4,5,6]}.
\]

剩余完整作业按全局代理宽度 6，分成最少数量的均衡波次：

| 核 | 尾段 | 完整作业波次大小 | 尾段放置 |
|---|---|---|---|
| 0 | `[0,20)` | `[2,6,6]` | 首波，相关位置 tail-first |
| 1 | `[20,44)` | `[3,6,5]` | 同上 |
| 2 | `[44,66)` | `[4,5,5]` | 同上 |
| 3 | `[66,94)` | `[5,5,4]` | 同上 |
| 4 | `[94,124)` | `[6,4,4]` | 同上 |

这里核 4 在其尾段位置会出现“六个完整作业＋一个尾操作”。**这不是把全局容量宽度从 6 改成 7**：使全局代理最紧的位置在 52、57、62、67，核 4 的尾段不覆盖这些位置，必须按位置检查。

五核首波的 L1 代理峰值分别是：

```text
361472, 394240, 459776, 492544, 492544 B
```

均不超过 524,288 B；UB 代理为零。**这些仍只是 W/A/F 代理峰值，不是官方峰值，更不是零 spill 证书。**

### 为什么阶梯有理论依据，而不只是另一组参数

先看一个明确限定的理想模型：所有计算在同一条管线上，位置 \(p\) 的周期为 \(d_p\)，忽略 COPY 和容量。定义：

\[
P(p)=\sum_{j<p}d_j.
\]

核 \(c\) 首波有 \(n_c\) 个完整作业，在自己的尾段内 tail-first。若没有外部等待，尾段末操作 \(p=a_{c+1}-1\) 的完成时刻为：

\[
E_c=(n_c+1)P(a_{c+1})
-P(a_c)-n_cd_{a_{c+1}-1}.
\]

下一核首个尾操作的本地预定开始时刻为：

\[
S_{c+1}=n_{c+1}P(a_{c+1}).
\]

当 \(n_{c+1}\ge n_c+1\) 时：

\[
S_{c+1}-E_c
=
(n_{c+1}-n_c-1)P(a_{c+1})
+P(a_c)+n_cd_{a_{c+1}-1}
\ge0.
\]

所以在这个理想单管线模型中，阶梯能避免尾段入口因前一段未完成而等待；各核最终只承担自己的工作量。跨多个段的残差也可以用实际生产、消费位置检查同类不等式。

**这个定理不能原样搬到 M/V 双管线。** 例如某尾段以 V 开头，它可能比“单管线前缀时刻”更早到达队首。本轮对真实 M/V 模板使用 A 节完整递推后，仍存在局部入口等待，但最快跨核延迟没有抬高主路线的全局计算最长路：

\[
L_{\text{zero-copy}}=L_{\text{fast-cross}}=11\,856\,672.
\]

这证明的是**该松弛模型中的临界路径不再沿四个尾段交接串联**，不是证明官方通信全部隐藏。

### 合法控制范围

只改变 compute 的子图次序与核归属，保持 canonical singleton。

tail-first 会把该生产者的 COPY_OUT 锚点一起前移；但同一生产者产生的多个 COPY_OUT，仍不能独立指定相互顺序。目标 COPY_IN 仍由最早本地消费者所在子图决定。波次不是运行时 barrier，首波不是显式预加载阶段。

全部尾作业跨核边都从较小核号指向较大核号。因此，**在各核 Step3 本地执行图有效的前提下，跨核边不会新增回环**：任何跨核路径核号严格增加，无法返回原核。该结论不代替本地 Step2/3 有效性检查。

### 离 11,785,739 还有多远

主路线当前静态必要界为 **11,857,220**，已经比通用界高 **71,481**。因此这份固定顺序本身也不能达到 11,785,739。

但相对于当前门槛，尚有：

\[
12\,237\,901-11\,857\,220
=\boxed{380\,681}
\]

cycles 空间。令实际 E0 与该必要界的差为 \(G\ge0\)，则它赢当前最佳的条件是：

\[
\boxed{G<380\,681}.
\]

这是可检验条件，不是对 \(G\) 的预测。它比原末波方案只剩 16,630 cycles 的余量更值得首先检验。

## B2. 备用路线：用完整作业前缀隔开各尾段

若主路线在 E0 中仍表现为严重的远端入口阻塞，再试更保守的相位隔离：

```text
core c：
    先做 c 个完整作业
    再做自己的完整尾段
    再做剩余 14-c 个完整作业
```

前缀和后缀内部仍使用容量 wave；尾段是一个连续的 singleton 序列，不改成大子图。适用条件包括 \(q\ge k-1\)，且前缀本身能按允许的 wave 构造。

在理想单管线模型中，设单作业工作 \(D\)，前一核尾段工作 \(s_{c-1}\)，下一核尾段开始前的相位余量至少是：

\[
cD-\big((c-1)D+s_{c-1}\big)
=D-s_{c-1}>0.
\]

它用一个真实完整作业量级的独立工作隔开交接，而不是靠两个相近位置的先后关系隐藏等待。

本轮静态必要界为 **11,886,740**，比主路线略差；它也减少了尾段与完整作业同位置的权重复用。因此只作为第二个、诊断方向明确的候选，**不再引入多尾、折返核映射或 E0 扫参**。

当前证据没有证明必须放弃单尾。真正要放弃的是：**把负载均衡后的尾段放在几乎相同的局部相位上，再期待 FIFO 自动填补等待。**

## B3. 状态、递推及完整构造伪代码

切点仍沿用已修正的两遍 DP。令：

\[
C(a,b)=\max\left\{
qW_M+P_M(b)-P_M(a),
qW_V+P_V(b)-P_V(a)
\right\}.
\]

第一遍：

\[
D[j,b]=\min_{a<b}\max\{D[j-1,a],C(a,b)\}.
\]

得到 \(T^*=D[k,L]\)。第二遍仅允许 \(C(a,b)\le T^*\)：

\[
Q[j,b]=
\min_a\left\{
Q[j-1,a]+\mathbf1_{j>1}\,\mathrm{frontierBytes}(a)
\right\}.
\]

保留 parent 重建切点。**第二遍仅优化切点字节代理，不声称最小化真实通信或 Makespan。**

```text
CONSTRUCT(G, cfg, k, mode, target):
    # 本次冷进程内读取、索引、计算；不加载当前图的预制参数表
    X = build_validated_index(G)
    data = strict_serial_template_guard(X)
    if guard fails:
        return NOT_APPLICABLE     # 实验不评分 active_fallback

    J, L = number_of_jobs, template_length
    require J = q*k + 1, k >= 2, L >= k

    compute W[p,r], A[p,r], F[p,r] from full tensor lifetimes
    compute per-position beta[p] from Phi(p, b) <= capacity
    B = min_p beta[p]
    require every rebuilt current-op input/output footprint fits

    cuts, Tstar = TWO_PASS_TAIL_DP(m, v, k, q, frontier_bytes)
    if Tstar >= target:
        return PRUNED_BY_WORKLOAD

    full[c] = jobs c, c+k, ..., c+(q-1)*k
    tail = final job

    if mode == STAIR:
        for c:
            U[c] = min(q,
                       min_p(beta[p] - indicator(cuts[c] <= p < cuts[c+1])))
        h = min_c(U[c] - c)
        if h < 1:
            return NOT_APPLICABLE

        for c:
            n = h + c
            first = full[c][0:n]
            seq[c] = []

            for p in 0 .. L-1:
                if cuts[c] <= p < cuts[c+1]:
                    append tail[p] to seq[c]       # tail-first
                append job[p] for job in first

            rest = full[c][n:q]
            for wave in BALANCED_MIN_WAVES(rest, max_width=B):
                for p in 0 .. L-1:
                    append job[p] for job in wave

    else if mode == PREFIX:
        require q >= k-1
        for c:
            seq[c] = POSITION_MAJOR_WAVES(full[c][0:c], B)
            append tail[cuts[c]:cuts[c+1]] to seq[c]
            append POSITION_MAJOR_WAVES(full[c][c:q], B)

    verify coverage and each full job has exactly one owner
    verify all tail cross edges go from lower to higher core
    verify local compute order is topological

    # 没有调用 Step/E0；下图只用于求界，绝不写回原图
    H = BUILD_MANDATORY_RELAXATION(G, seq, cfg)
    if H has a mandatory constraint cycle:
        return INVALID_ORDER

    Lfifo = LONGEST_PATH(H)
    if max(Lfifo, head_tail_bound(G, k)) >= target:
        return PRUNED_BY_NECESSARY_BOUND

    read_certificate = CHECK_BURST_CLOSURE(G, seq)
    # 不通过时撤去共享读取上界声明，不把代理写成定理

    mapping = canonical singleton mapping over eligible compute IDs
    plan = {
        node_to_subgraph: mapping,
        core_schedules: map seq[c] through mapping
    }
    derive_multicore_plan(G, plan)       # 冷求解计时内
    write exactly the two-field plan
    write diagnostics separately
```

必要界构造不能漏掉残差或自行假定桶内 COPY 顺序：

```text
BUILD_MANDATORY_RELAXATION(G, seq, cfg):
    add every original compute with its actual cycle count
    add original logical compute dependencies
    add consecutive M edges and consecutive V edges from each seq[c]

    for every tensor:
        identify eligible producers and consumers by core

        add mandatory per-core graph-input COPY_IN
        add mandatory graph-output COPY_OUT

        for each actual source_core != consumer_core:
            add source COPY_OUT anchored to last local producer
            add destination COPY_IN anchored to first local consumer
            add COPY_OUT -> COPY_IN with lag 500
            connect the actual producers and consumers

        assign every COPY its safe optimistic duration

    for each core and each MTE pipe:
        group mandatory COPY nodes by anchor-subgraph rank
        for successive nonempty groups:
            add "all previous-group nodes finish
                 before any next-group node starts"
        # 同桶内不添加未经证明的顺序
        # 可用零时长 entry/exit 分析节点线性编码，不作二次全连接

    return H

LONGEST_PATH(H):
    F[v] = 0 initially
    for v in a topological order:
        F[v] = duration_lower[v] +
               max(F[u] + edge_lag[u,v] for u in predecessors[v])
    return max_v F[v]
```

在本轮严格单生产者结构下，索引、张量分析、必需 COPY 图与最长路均为线性规模；计入确定性拓扑排序及切点 DP，保守时间复杂度为：

\[
O(N\log N+E+kT+kL^2),
\]

空间：

\[
O(N+E+kT+kL).
\]

\(k\le5\)，没有相位枚举、切点 E0 扫描或在线 E0。前端/验证的实际墙钟仍必须计入，不能仅报告 DP 内核耗时。

---

# C. 首轮结论的保留、收紧与最小证伪实验

## C1. 哪些保留，哪些必须重推

| 首轮结论 | 本轮处理 |
|---|---|
| 完整作业归核可以作为 067 主指标突破 | **撤回。** 12,446,880 的必要界已经排除。 |
| 长残差必须计入 F/A，`shared + max(single-op)` 不能证明容量安全 | **保留。** 044 的成功实例不能推翻这个反例，也不能把代理升格成零 spill 证书。 |
| 完整作业归核消除跨核激活 COPY | 对完整作业仍成立；**尾作业不成立**。当前切点有 12 对 COPY，而不是仅四对。 |
| \(W\times\text{wave 数}\) 共享读量界 | **必须检查 COPY 插入后的 burst 条件。** 不能因 compute 消费连续就自动迁移。 |
| 首轮整体 COPY/dirty-spill 字节上界 | **不能直接沿用。** 分裂后出现核内 tensor 副本、源端 COPY_OUT 消费和目标端 DDR backing，必须按重建后的 `(core,tensor)` 重算。 |
| 完整 Step2 输入序列及图身份保持不变时的安全合并等价性 | **保留原条件。** 但本轮不合并，避免增加 Step1 成本和混淆变量。 |
| 044/k4 37,581、spill 0 | 作为新包报告的已测事实保留；它不是本轮复评结果，也不证明全图族有效、完整求解器提速或零 spill 定理。 |

### 共享读取界如何重新表述

对每个共享权重 \(w\)，应按每核的真实消费 burst 数 \(g_{c,w}\) 写：

\[
B_{\mathrm{shared}}
\le\sum_{c,w}|w|\,g_{c,w}.
\]

一个可用的充分条件是：相邻两次消费 \(w\) 之间，自动 COPY 要么不申请新的片上数据，要么只申请下一次消费 \(w\) 所需的输入；该次计算的全部输入、输出能同时容纳，并且没有未计入的旁路 COPY 分配。

证明要点：若此期间发生溢出，下一次权重消费所需的数据集合本身放得下，超过它的驻留项必有更晚的下一次使用；S2 的最远下一次使用规则会先逐出那些项，而不是迫使当前 burst 的 \(w\) 重载。检查必须覆盖入口 COPY、尾段输入、源端输出及直接跨核边生成的额外 buffer。  
来源：S2 `157–202、224–289`；E3 `166–242`。

**这里给的是需要核对的充分条件，不是声称本轮已运行完整官方 COPY 序列并验收了它。**

条件成立时，主阶梯每核仍为三波，尾部消费融在对应位置的 burst 内：

\[
B_{\mathrm{shared}}\le15W
=\boxed{55\,824\,000\ \text{B}}.
\]

备用前缀方案的完整作业波次数合计为 16，隔离尾段最多再读一整套分摊权重：

\[
B_{\mathrm{shared}}\le17W
=\boxed{63\,267\,200\ \text{B}}.
\]

两者都不承诺零私有激活 spill，不承诺 Cache hit，也不以命中率替代 Makespan。

## C2. 最多 2 cold / 4 外部 E0

只保留下面两个候选，切点和完整作业核归属完全相同，不引入第三个尾分割方案：

| 候选 | 冷构造 | 外部评分 | 目的 |
|---|---:|---:|---|
| C1：首波容量阶梯、tail-first | 最多 1 次 | 同一计划 P2、P3 各 1 次 | 首先验证相位重排能否赢 **12,237,901** |
| C2：完整作业前缀隔离尾段 | 最多 1 次 | 同一计划 P2、P3 各 1 次 | 仅在 C1 仍出现明显尾入口阻塞时，检验更大相位隔离是否有效 |

**不冷跑 whole-job；不优先复评旧末波候选；不为补对照扩大预算。** C1 已经达到目标且机制清楚时，可停止在 1 cold / 2 E0。资源门槛继续使用既有门槛；派发前失败就是未派发，不自动重试。

### 跑前淘汰证书

真正能够数学淘汰的条件是：whole-job 界、固定候选工作量界或固定候选 FIFO 必要界 **不小于 12,237,901**；以及必然约束图存在不可执行回环、单操作必要同时驻留量超过容量。

需要区分：**W/A/F 代理超限只是这条保守构造不接纳该宽度，不证明允许 spill 的所有计划均不可能。** 原末波方案剩余空间很小，也只是本轮不优先试验的理由，并非严格淘汰证书。

### 预先登记的 signature

对 C1，最重要的正向 signature 不是高命中率，而是：尾段关键交接明显前移，最终临界等待不再连续跨越四个尾段入口；M 服务量保持原 DP 分配，没有因改变归属重新出现 15 个完整作业的热点核。

同时保存每条跨核传输的：

\[
\text{COPY\_OUT end},\quad
\text{release=end+500},\quad
\text{COPY\_IN start/end}.
\]

但

\[
\text{COPY\_IN start}-\text{release}
\]

只能先称为“额外接收延迟”，不能全部记成 FIFO 损失：它还可能来自前一条 MTE2 服务、本地依赖或内存补边；早已生产的长残差晚些读取也不一定损害 Makespan。只诊断实际影响后续关键计算的等待，不能累加重叠窗口冒充可回收收益。

DDR 另报官方 extra、spill、共享权重首次/重复读取、私有数据 spill，以及按字节 hit。P2/P3 必须使用完全相同的计划字节，不能让 Cache 对照混入重新构造。

### 停止条件

C1 的实际 \(M_{\mathrm{P3}}-11\,857\,220\) 若达到或超过 380,681，则没有赢当前最佳；不能把“比旧 15,686,331 好”宣布为本轮成功。

若失败主要仍沿尾入口和 COPY 队首传播，可以用唯一剩余额度执行 C2。若尾交接已经退出临界路径，失败主要来自大规模私有 spill、内存补边或权重读取，则**不把 C2 当作盲目再试一次**；停止本轮，保留这条证伪结论。

C2 的静态余量为：

\[
12\,237\,901-11\,886\,740=351\,161.
\]

两次都不能赢，就停止这个固定单尾相位家族的本轮试验，不自动扩成波宽、切点或核排列扫描。条件性读取界若在已确认充分条件下被突破，应先查实现或证明缺口，也不继续靠 E0 调参掩盖。

## C3. 成本口径

本轮已计时的图专属静态计算，包括重复索引/DP、符号最长路、独立证书和端点核验，累计约 **4.711 秒**。这是本环境的静态研究脚本计时，**不是完整冷求解时间**；解压、源码阅读、推导、工具启动及未统一计时的前置工作不包含其中，不能说整个研究只用了这些秒数。

部署时必须在冷求解里重新计算 guard、切点、\(\beta/U/h\)、符号证书、验证和落盘；不能把本轮的 `[0,20,44,66,94,124]`、`[2,3,4,5,6]` 做成当前图查表后声称在线零成本。外部最终 E0 单列。5–10 分钟仍是效率建议，不是本轮自设的质量淘汰线。

**建议本轮就实现 C1：同一条尾作业、同一组工作量切点，改成首波容量阶梯与 tail-first。** 已经能证明原末波顺序的大部分空间消耗在因果/FIFO 串联，而不是不可避免的负载量；现在应检验这种串联能否通过合法优先序真正消除，而不是继续降低一个已经不足以代表 Makespan 的工作量目标。