## 实际读取范围与身份核验

已解压附件。ZIP 实际大小为 **2,901,468 bytes**，SHA-256 与你给出的  
`bb91c542e94abdba7aef3e87a85841308744aec1720189b2ff1dd4636b5e02e5` 一致。压缩包有 **60 个文件**；`MANIFEST.json` 登记其余 **59 个文件**，逐项大小和 SHA-256 均吻合。清单记录的资料 HEAD 为 `c514edf0a8ef95861fc5cfbcc6719ffd5fdd4e07`；这不是对私有仓库当前 HEAD 的联网核验。

| 范围 | 本次实际读取情况 |
|---|---|
| 入口与原题 | 已读 `START_HERE.md`、`MANIFEST.json`、原题 PDF 的文本；另检查了第 5、13、14 页渲染，核对任务边界、执行过程和 Cache 语义。 |
| 冻结官方实现 | 已读 config、P3 evaluator，以及 Step1/2/3 中决定调度、spill、内存补边和 Pipe 队列的执行路径；核对了 validator、方案解析和 CLI。P1 只读了本题使用的公共辅助函数，P2 做了与 P3 的相关源码差分，**没有把两者的全部主循环都算作已通读**。 |
| 已有构造 | 已读 `baseline.py`、`construct.py`、`active_stages.py`、`pipeline_stages.py`、`pipeline_setup.py`、`pipeline_capacity.py`、`pipeline_coalesced.py`，及对应方法说明、报告、CSV 和 coalesced postmortem。 |
| 原始图与保存方案 | 完整解析了 044、067 原图及四份保存方案；核对覆盖、核归属、共享输入、作业模板和张量生命周期。 |
| 完整 result/trace | 完整解析 **8 组 result/trace**，逐操作核对 **33,142 条操作记录**，另核对跨核释放时刻和 P3 Cache 事件。不是只读了摘要或截图片段。 |
| 缺失或未独立取得 | **073 原图、完整方案/result/trace 不在包内**；队长固定 V2 的可执行构造与原始 trace 也不在包内。对它们仅采用包内报告所述数字，不称为独立复评。包内引用但未附的测试源码、运行台账和其他私有材料也不算已读。 |

本次没有运行新方案构造、官方 Step1/2/3 或 E0；执行的是解压、哈希、完整保存记录解析和结构算术复核。:chatgpt-content-reference{index="2"}[只读复核记录](sandbox:/mnt/data/q3_analysis/read_only_audit.json)与:chatgpt-content-reference{index="3"}[可复现复核脚本包](sandbox:/mnt/data/q3_p3_read_only_audit.zip)已附。

**结论先给出：优先做两件事。**

**第一条主路线：把完整作业放回同一核，用容量约束的小 wave 连续消费同一位置的共享权重。** 这是对已有 `active_stages` 的实质修补，不是重新命名其 position-major 顺序。它避免要求整段权重常驻，也直接消除跨核激活 COPY 队列和相应的 500-cycle 释放依赖。

**第二条配套路线：建立合法的 COPY 锚点编译规则，只做“完整 Step2 输入序列不变”的安全合并。** 不再把“计算 Pipe 顺序相同”当成合并安全证据。它用于保住已有质量并探索求解墙钟下降，本身不承诺降低 Makespan。

---

## 一、证据中最重要的两项新增发现

### 1. `pipeline_capacity` 目前还存在一个先于容量模型的问题

`pipeline_capacity.py:91–92` 对原图中的所有 tensor 检查：

```python
if any(t["pos"] not in SPACES for t in tensors.values()):
    ...
```

其中 `SPACES = ("L1", "UB")`，而 `baseline.py` 中 `index.graph` 保留原图，并没有预先删去 DDR tensor。044 原图含 **72 个 DDR tensor**，067 含 **192 个**。

因此，**对于这两份原图，当前容量构造会触发 `unsupported_tensor_memory_space` 并回退，而不会进入容量 DP。** 这是从源码与输入推导出的结论，不是本次跑出的构造结果。

修复时不能简单地把所有 DDR tensor 当成 L1/UB 占用，也不能一概忽略：官方 P3 会把**直接关联 eligible compute 的原始 DDR tensor**在核内重建为 UB；原始 COPY 的 DDR backing 则不计片上容量。044、067 经本次结构复核，没有前一种直接关联 compute 的 DDR tensor，但通用实现仍需区分。  
（来源：`pipeline_capacity.py:80–92`；冻结 P3 evaluator，以下简称 **E3**，`141–174`。）

### 2. 067 当前巨额 spill 的主体可以比报告说得更明确

保存成绩如下；073 一行仅来自报告。

| 保存方案 | P2 Makespan | P3 Makespan | 官方额外搬运 B | spill B | 按字节 hit |
|---|---:|---:|---:|---:|---:|
| 044/k4 singleton pipeline | 40,927 | 40,927 | 135,168 | 0 | 0 |
| 044/k4 cold-setup DP | 64,211 | 41,738 | 1,731,840 | 1,622,016 | 0.6167698916 |
| 044/k4 四阶段合并 | 97,641 | 97,641 | 135,168 | 0 | 0 |
| 067/k5 pipeline | 15,686,331 | 15,686,331 | 210,882,560 | 202,303,488 | 0 |
| 073/k5 pipeline，报告值 | 3,337,352 | 3,337,352 | 110,682,624 | 109,504,512 | 0 |

对 067 的完整 Cache 事件按 **`(core_id, logical_tensor_id)`** 分账：

\[
\begin{aligned}
\text{共享权重首次读} &= 3,721,600\ \text{B},\\
\text{共享权重重复读} &= 202,303,488\ \text{B},\\
\text{其他 tensor 首次读} &= 5,452,800\ \text{B},\\
\text{其他 tensor 重复读} &= 0.
\end{aligned}
\]

也就是说，**该保存方案的全部 202,303,488 B spill，均对应共享权重重新读入。** 044 cold-setup 的 1,622,016 B 也具有同样的共享权重重复读对应关系。以上是对保存事件的重新分类，不是根据两个汇总数字相等而猜测。:chatgpt-content-reference{index="4"}[复核记录中的 `read_classification`](sandbox:/mnt/data/q3_analysis/read_only_audit.json)

这决定了突破顺序：**先缩短同一权重的核内复用间隔，而不是先追求更高 Cache hit。** 044 setup 已经说明，较高 hit 可以只是在补偿被构造自己制造出来的重复读，并不意味着方案更好。

---

## 二、E0 真正给了什么控制权

冻结配置为每核 L1 **524,288 B**、UB **131,072 B**；共享 DDR **60 B/cycle**；跨核 COPY 释放延迟 **500 cycles**；只读 FIFO Cache **1,048,576 B**、独立读带宽 **250 B/cycle**。

合法方案的控制链是：

\[
\text{分核、子图划分及核内子图顺序}
\longrightarrow
\text{核内重建图及 COPY 归属}
\longrightarrow
\text{Step1 序列的稳定分桶重排}
\longrightarrow
\text{Step2 spill}
\longrightarrow
\text{Step3 Pipe FIFO 和内存依赖}
\longrightarrow
\text{最终事件模拟}.
\]

这里有三个必须严格区分的层次。

### 子图不是运行时 barrier

P3 把同核所有子图合成**一个 Task**。子图顺序用于改变核内编译的优先序，不表示“整个子图执行完，下一子图才能开始”，更不会在 wave 边界清空 L1 或 Cache。

图输入 COPY_IN 归属于该核**最早消费它的子图**；图输出及跨核 COPY_OUT 归属于源核**最晚生产它的子图**。随后，Step1 原始序列按子图顺序稳定重排，桶内顺序仍由 Step1 决定。  
（E3：`51–67、69–215、244–279`。）

### 最终执行服从编译出的队首，而不是动态选择“最有价值 COPY”

Step3 将扩展序列投影为每条 Pipe 的 FIFO。最终 E0 只尝试队首；即使后面的 COPY 已具备数据条件，也不能越过前面的未就绪操作。

而且 Step3 先在核内模拟中生成内存复用依赖，将其固化进 execution graph；最终多核阶段不重新运行内存分配策略。因此：

> **零 spill 不代表没有内存复用约束，更不代表 MTE3 不会阻塞。**

044 coalesced 已提供直接证据：M、V、MTE2 顺序不变，MTE3 在核 0/1/2 改变，Makespan 从 40,927 增至 97,641。例如合并方案中，核 0 的 op 77 在 1,848 结束，其 COPY_OUT `1000001606` 到 **21,197** 才开始；紧邻前项 `1000001949` 在 21,188–21,197 执行。这个窗口是排队诊断证据，**不能整段加总成换序后必然可回收的收益**。  
（Step3：`281–296、407–422、595–612`；E3：`443–475`；包内 `diagnostic-02/POSTMORTEM.md` 和完整 trace。）

### Cache 不能被方案直接钉住或同步预热

Cache 在 COPY_IN **发射时**查询，在 COPY_IN 完成时进行插入处理；命中不提升 FIFO 位置。两个核同时冷读同一 tensor，可以都 miss。核内 `core_schedules` 也不能表达“核 1 等核 0 把某权重放入 Cache 后再读”。

因此，“共同权重小于 Cache 就能实现跨核一次加载”的推断也不成立。首版构造应当按 **Cache 全 miss 仍有意义**设计，命中作为额外收益。  
（E3：`398–434、487–511、539–581`。）

---

## 三、容量代理为何失效：不仅是缺一点 safety margin

### 一个小型反例

修复 DDR guard 后，原代理仍然不充分。取 L1 容量为 8 单位，每单位 65,536 B；两个相同作业按 job-major 执行，共享权重 \(w\) 大小为 1，仅在各作业的第一个操作使用。

每个作业为：

```text
u1: x(1), w(1) → a(1), r(3)
u2: a(1)       → b(1), s(3)
u3: b(1), r(3) → c(1)
u4: c(1), s(3) → d(1)
```

最大单操作非共享 incident footprint 为 5，所以原代理判定：

\[
1+5=6\le 8.
\]

但第一个作业执行 \(u_2\) 时，输入尚未释放、输出已经分配，活跃集合包括：

\[
\{w(1),r(3),a(1),b(1),s(3)\},
\qquad \text{合计 }9>8.
\]

必须 spill。按冻结 Step2 的最远下一次使用规则，这里 \(w\) 的下一次使用在第二个作业，晚于 \(r\)，因而可先逐出 \(w\)。

**这个反例针对的是代理，不是本次新增的官方测试成绩。** 其机制正对应 Step2 的 `alloc → spill check → execute → last-use free`，加一个固定百分比余量没有一般性修复作用。  
（Step2，以下简称 **S2**：`157–202、224–289`。）

### 真正的零 Step2 spill 证书是什么

对官方重建图和实际进入 Step2 的完整序列 \(S\)，计算每个片上 tensor 的首次、末次使用位置 \(f_t,l_t\)，生产者也算使用。检查：

\[
\forall r,i:\qquad
\sum_{\substack{t:\operatorname{pos}(t)=r\\f_t\le i\le l_t}}
|t|
\le C_r.
\]

这才是该固定序列上的零 Step2 spill 条件；必须包括自动插入的 COPY 和输入/输出瞬态重叠。对于已确定、合法的序列，可用生命周期事件扫描计算。

但它仍然**不是 Makespan 证书**：Step3 可以为了异步执行下的空间复用而加入额外依赖。

真实图还含有不能忽略的长残差。067 有从位置 11 延续到位置 112 的 tensor，另有 23→99、35→86、47→73；这些长存活量不能用“相邻两层激活”代替。:chatgpt-content-reference{index="5"}[结构复核记录](sandbox:/mnt/data/q3_analysis/read_only_audit.json)

权重与激活需要联合考虑，这也与已有数据流研究的建模结论一致；但那些研究允许的硬件映射控制不能直接当作这里 E0 的控制权，下面的保证仍以冻结源码为依据。:chatgpt-content-reference{index="0"}

---

## 四、路线一：完整作业归核，做容量受控的共享权重 burst

### 4.1 为什么暂时不继续修“永久空间阶段”

067 的共同权重：

\[
W=3,721,600 > 5\times524,288=2,621,440.
\]

因此，“每段权重在所属核全程常驻、每段之间跨核流水”的构造类别，已经没有全部权重同时驻留的可能。这个不可能性只针对该常驻模型，**不针对所有分段、重排算法**。

可以设计超过核数的虚拟阶段、折返映射和跨核 wave，但这会重新引入折返 FIFO、残差跨段 COPY，以及局部内存依赖与跨核释放组合成环的问题。仅检查子图 DAG 不够，官方还检查展开后的 Pipe、内存、跨核依赖联合图。第一轮不宜把复杂性继续堆到这里。  
（`evaluation_validation.py:226–243`。）

**更可靠的第一版：空间上按完整作业分核，时间上按小 wave 分段。**

### 4.2 具体顺序

结构守卫要求：作业间没有计算依赖；模板的操作、Pipe、周期和私有 tensor 连接模式一致；共同权重的消费者位置一致。首版进一步要求每个共同权重在每个作业中只由一个位置的一个 compute 使用。

对每个核：

```text
wave 0:
    position 0: job a, job b, job c, ...
    position 1: job a, job b, job c, ...
    ...
    position L-1: job a, job b, job c, ...

wave 1:
    同样的 position-major 顺序
...
```

每个 compute 先保持 singleton 子图。这不是运行时 barrier；它是能够通过两个提交字段表达的**静态核内优先序**。

已有 `active_stages` 已经做了 position-major，但把该核**全部作业**一起展开，其资源模型预设 zero-spill。这里新增的核心是：**用完整残差 frontier 限制每个 wave，再明确区分共享权重 reload 与私有激活 spill。** 未分 wave 的 `active_stages` 必须作为对照，不能略过。

### 4.3 一个不扫参的 wave 大小公式

对单作业、每个存储空间 \(r\)，定义：

- \(F_r(h)\)：执行到位置 \(h\) 之前仍跨越该边界存活的私有 tensor 总字节；
- \(A_r(p)\)：执行位置 \(p\) 时，私有 tensor 的完整活跃量，含输入与新输出重叠；
- \(W_r(p)\)：仅供位置 \(p\) 使用的共同权重总字节。

一个大小为 \(b\) 的位置 burst，其**当前 wave 活跃工作集包络**为：

\[
\Psi_r(p,b)=
W_r(p)+A_r(p)
+(b-1)\max\{F_r(p),F_r(p+1)\}.
\]

取满足所有位置和空间约束 \(\Psi_r(p,b)\le C_r\) 的最大整数 \(b_{\max}\)。这是直接算术，不需要枚举切点或调用 E0。

**重要限制：这个包络仍不是官方零 spill 证书。** 其他位置、其他 wave 的权重可能因未来还要使用而继续驻留；官方最远下一次使用策略有时会逐出长残差，而不是先逐出所有“当前 tile 外”的权重。不能再次偷换成“包络可行，因此官方零 spill”。

它的作用是确定一个有结构依据的 cohort 宽度；真正要保证的是下面更窄、但更可靠的共享权重复用性质。

### 4.4 067 的静态候选参数

对包内 067 全图复核，最紧位置为 52、57、62、67：

\[
W(p)=294,912,\quad A(p)=33,792,\quad
\max(F(p),F(p+1))=32,768.
\]

于是：

\[
\Psi(p,6)=492,544\le524,288,
\]

而

\[
\Psi(p,7)=525,312>524,288.
\]

得到 \(b_{\max}=6\)。

71 个相同作业分到五核，作业数为：

\[
[15,14,14,14,14].
\]

每核所需 wave 数均为 3。保持最少 wave 数，再均衡 wave 大小，得到：

```text
核0：5 / 5 / 5
核1：5 / 5 / 4
核2：5 / 5 / 4
核3：5 / 5 / 4
核4：5 / 5 / 4
```

这样不用“6/6/尾部”制造不必要的峰值。**这些是从输入推导出的拟议参数，不是已生成、已评分的方案。** 对 073 不能复制这些数字，必须在取得原图后重算。

### 4.5 能证明的保证：约束权重读次数，不冒充零激活 spill

**共享权重 burst 引理。** 在上述守卫下，使用 singleton、完整作业归核和 `(wave, position, job)` 顺序，且单操作的全部当前输入/输出可容纳，则每个共同权重在每核每个 wave 中至多加载一次。

证明要点如下。内部位置上，同一权重的 compute 使用连续出现；每次 compute 都将它列为当前操作不可逐出的 tensor。入口位置可能夹入下一 compute 专属的输入 COPY，这些即将使用的 buffer 与权重属于同一操作的必要足迹；足迹可容纳时，最远下一次使用策略不会被迫先逐出马上要用的权重。出口 COPY 同理不引入新的片上输出分配。wave 之间可以逐出该权重，但下一 wave 仍至多重新加载一次。

该引理允许私有激活 spill，也允许不同 wave 的权重重新读取。Step3 不再插入新的 spill，所以它约束的是最终方案实际会包含的 COPY 工作量。原始共享输入已有 DDR backing，被逐出时不需要新增脏写回。  
（S2：`157–202、224–289、304–383`。）

因此：

\[
B_{\text{shared-read}}
\le
W\sum_c q_c,
\]

其中 \(q_c\) 是核 \(c\) 的 wave 数。对上面的 067 候选：

\[
B_{\text{shared-read}}\le
3,721,600\times15
=
\boxed{55,824,000\ \text{B}}.
\]

这比旧方案保存事件中的共享权重总读量 \(206,025,088\) B 小很多；**它是条件成立时的上界，不是本次实测。**

还能给一个保守的总搬运上界。对非共享中间 tensor \(t\)，若有 \(d(t)\) 个原始 compute 消费者，冻结 Step2 最多建立一次脏 DDR backing，最多在各消费者前重新读入，因此：

\[
B_{\text{dirty-spill}}(t)\le(1+d(t))|t|.
\]

067 的完整结构满足私有输入只在首位置单次使用、最终输出只在末位置产生的守卫。由原图求和：

\[
\begin{aligned}
B_{\text{dirty-spill}}&\le121,415,680,\\
B_{\text{private-base-copy}}&=2,326,528.
\end{aligned}
\]

于是候选的 scheduled COPY 量有保守上界：

\[
\boxed{
B_{\text{COPY}}
\le55,824,000+121,415,680+2,326,528
=179,566,208\ \text{B}
}.
\]

旧流水保存值为 216,930,688 B。**这个结论提供的是 COPY 字节上界上的进展，仍不保证 Makespan 胜过固定 V2。** Cache 命中只会减少其中进入 DDR 池的部分，不是这个上界成立的前提。

### 4.6 COPY 队列方面能保证什么

完整作业归核后，作业内部 tensor 不跨核：

\[
\boxed{\text{跨核激活 COPY 对数量}=0}.
\]

因此它们对应的 MTE3 队首阻塞和 `COPY_OUT + 500 → COPY_IN` 链全部消失。MTE3 还可能包含最终输出和私有激活的脏 spill，不能说整个 MTE3 永不阻塞。

若另经精确 Step2 检查确认没有脏 spill，且各作业最终生产者都在同一 compute Pipe，则最终输出 FIFO 与这些生产者的 Pipe 顺序一致，可以排除 044 coalesced 那种特定的生产者/输出次序倒置。没有这些附加条件，不给这项保证。

---

## 五、路线二：COPY 锚点编译与保序安全合并

### 5.1 COPY 优先序的可编码边界

在 singleton 方案中，一个生成的 COPY_OUT 跟随其生产者所在桶。要让不同生产者的 COPY_OUT 按某顺序出现，可以对生产者桶增加顺序约束，再与数据依赖及要保留的 compute 顺序共同拓扑排序。

但这不是独立 MTE3 控制器。

一个明确的不可编码例子是：**同一 compute 生产两个需要 COPY_OUT 的 tensor。** 固定核归属和生成 ID 顺序后，这两个 COPY_OUT 总在同一生产者子图桶内；它们的相对顺序由原始 Step1 决定。不能只靠给该 compute 换子图 id，独立反转两个输出。

因此，提交前的原则应是：

> 先找能表达该 COPY 顺序的生产者桶顺序；桶约束冲突就拒绝该目标。不要先生成理想 MTE 队列，再假定存在等价提交方案。

### 5.2 安全合并的充分条件：保持完整 \(S\)，不只保持三条 Pipe

固定计算核归属、原图、`node_to_subgraph` 的键插入顺序及 ID 分配后，设某核原始 Step1 序列为 \(R\)。

旧方案按子图顺序形成桶：

\[
S=B_1\Vert B_2\Vert\cdots\Vert B_m,
\]

其中每个 \(B_i\) 都保持其操作在 \(R\) 中的相对顺序。

仅当：

\[
\max \operatorname{pos}_R(B_i)
<
\min \operatorname{pos}_R(B_{i+1})
\]

时，才允许合并这两个相邻桶。连续满足条件的最大区间可以合并。

这样，合并后重新按大桶稳定排序，得到的仍然是**逐项完全相同的 \(S\)**。

由冻结实现的确定性得到：

\[
\begin{aligned}
&\text{核内图和 }S\text{ 相同}\\
\Rightarrow\;&\text{Step2 spill、扩展序列相同}\\
\Rightarrow\;&\text{Step3 四条 FIFO、内存补边相同}\\
\Rightarrow\;&\text{P3 操作时间线、Cache 事件、搬运量、Makespan 相同}.
\end{aligned}
\]

改变的只是子图标签和展示跨度。这里的相同不是只比 Makespan，也不是只比四条 Pipe；**完整 Step2 输入序列与图身份**才是证明入口。

还须校验合并后的子图商图是否合法。对完整作业归核、无跨核计算依赖的构造，这项检查很直接；对一般多核图，不能省略。商图非法时保留原 singleton，不尝试不受控合并。

在“只合并连续桶、必须保持完整 \(S\)”的局部问题中，所有下降边界都必须保留，上述最大上升段给出最少桶数。**这不是所有合法子图划分中的最优性结论。**

### 5.3 墙钟收益必须实测，不能由子图数推定

合并可以减少方案体积、子图解析以及官方构造里反复 `core_orders[core].index(sg)` 的开销；但在求解器里获取 \(R\) 本身要付出前端重建和 Step1 成本。

因此我建议：

- 主路线的默认快速版本**不做安全合并，不在线调用 Step1/2/3/E0**，直接提交 singleton wave。
- 安全合并作为独立配套版本，只在同机端到端墙钟证明有收益后部署。
- 一旦合并版本不能保持完整操作时间线一致，停止该编译器分支；不靠“最后分数碰巧接近”放行。

---

## 六、完整构造伪代码

下面的 `INCUMBENT` 是调用方注入的现有生产构造。本包没有固定 V2 实现，不能在这里伪造。仅用包内材料搭原型时可接 `construct.py` 的 baseline，但不能把它自动等同于固定 V2。

默认路径没有在线评分，也不把当前用例的分析移出计时窗口。

```text
SOLVE_P3(graph_path, config_path, k, INCUMBENT, compress=False):
    start outer_wall_clock

    G   ← read_and_validate_original_graph(graph_path)
    cfg ← read_frozen_config(config_path)
    # 不修改 G、cfg，不添加提交字段

    X ← BUILD_TEMPLATE_INDEX(G)
        # 建 eligible compute 的前驱/后继关系
        # 求独立计算连通分量，每个分量取确定性拓扑序
        # 为每个 tensor 建 producers / consumers / owner / position
        # 比较各作业的操作、Pipe、cycles、完整私有 tensor 连接签名
        # 识别共同输入，而非仅按 tensor 大小猜权重

    if not STRICT_WAVE_GUARD(X, cfg, k):
        return WRITE_AND_FINISH(INCUMBENT(G, cfg, k))

    # 首版生产触发器：常驻空间分段的充分失败条件。
    # 这不是 E0 性能判别定理；其他输入保留现有生产方法。
    if shared_L1_bytes(X) <= k * cfg.L1:
        P ← INCUMBENT(G, cfg, k)
        if compress:
            P ← SAFE_COMPRESS(G, P, cfg)
        return WRITE_AND_FINISH(P)

    groups ← distribute identical complete jobs evenly over k cores
              using stable job IDs as tie-breaker

    for each memory space r:
        for every private template tensor t:
            f[t] ← first incident compute position
            l[t] ← last incident compute position
            # 包含长残差；输入输出重叠保留

        F[r, h] ← sum size(t) where f[t] < h <= l[t]
        A[r, p] ← sum size(t) where f[t] <= p <= l[t]
        W[r, p] ← sum shared weight sizes used at p

    bmax ← largest relevant group size
    for each r, p:
        H ← cfg.capacity[r] - W[r,p] - A[r,p]
        D ← max(F[r,p], F[r,p+1])

        if H < 0:
            return WRITE_AND_FINISH(INCUMBENT(G, cfg, k))
        if D > 0:
            bmax ← min(bmax, 1 + floor(H / D))

    if bmax < 1:
        return WRITE_AND_FINISH(INCUMBENT(G, cfg, k))

    for core c:
        n ← number of jobs in groups[c]
        if n == 0:
            order[c] ← []
            continue

        q ← ceil(n / bmax)
        waves ← split groups[c] into q consecutive balanced groups
                # 每组大小 floor(n/q) 或 ceil(n/q)

        order[c] ← []
        for wave in waves:
            for position p = 0 .. L-1:
                for job j in wave:
                    append compute[j,p] to order[c]

    # 固定键顺序；一个 eligible compute 一个子图
    mapping ← singleton IDs in a fixed canonical compute-key order
    P.node_to_subgraph ← mapping
    P.core_schedules[c] ← [mapping[u] for u in order[c]]

    CHECK_SUBMISSION_SCHEMA_AND_QUOTIENT_DAG(G, P)
    CHECK_EACH_JOB_HAS_ONE_CORE(P)
    CHECK_COMMON_WEIGHT_BURSTS(X, P)
    CHECK_SINGLE_OP_INPUT_OUTPUT_FOOTPRINTS(X, cfg)

    # 这里只记录可证的字节上界及结构描述，不在线声称 E0 分数。
    record_sidecar(
        wave_sizes,
        shared_read_upper_bound,
        conservative_dirty_spill_upper_bound
    )

    if compress:
        P ← SAFE_COMPRESS(G, P, cfg)

    WRITE_AND_FINISH(P):
        write exactly {node_to_subgraph, core_schedules}
        finish required cleanup
        record outer_wall_clock
        return P
```

守卫和合并子程序如下：

```text
STRICT_WAVE_GUARD(X, cfg, k):
    require independent jobs and at least k jobs
    require identical full template signatures
    require only supported compute / memory semantics
    require no inter-job compute edges or shared writable tensors
    require each common weight:
        no eligible compute producer
        exactly one compute consumer per job
        same consumer position in every job
    require private graph inputs:
        one compute consumer, at first position
    require final outputs:
        one producer at last position, no later compute consumer
    require every compute's current inputs + outputs fit each space
    otherwise reject, without inventing tensor splitting
    return true


SAFE_COMPRESS(G, P, cfg):
    # 只做官方前端到 Step1 为止，不调用完整 _build_scene_b_tasks；
    # 后者还会执行 Step2/3，不能误计成“轻量前端”。
    # 前端精确复刻 E3 的核内图、COPY 锚点和全局 ID 生成规则。
    graphs, anchors, R ← FROZEN_FRONTEND_THROUGH_STEP1(G, P, cfg)

    for core c:
        B ← partition R[c] by the subgraph anchors,
             list buckets in P.core_schedules[c] order
        S_old ← concatenate(B)
        pos ← positions in R[c]

        groups ← []
        current ← first bucket
        for next bucket Bnext:
            if max(pos[current]) < min(pos[Bnext]):
                current ← current concatenated with Bnext
            else:
                append current to groups
                current ← Bnext
        append current to groups

        remap each maximal group to one subgraph
        preserve original node_to_subgraph key iteration order

    Pnew ← remapped legal two-field plan

    if quotient DAG or schedule checks fail:
        return P

    # 通过固定归核与锚点映射推导新桶，不再重复运行 Step1。
    S_new ← stable_bucket_order(R, remapped anchors, new schedules)

    if any core graph/ID identity changed or S_new != S_old:
        return P

    return Pnew
```

首个原型不加多位置 tile 搜索、不搜索 wave 相位，也不加跨核 Cache 预热策略。先证伪这个最小构造。

### 复杂度与保证边界

模板索引、生命周期事件和输出规模为 \(O(N+E)\)；使用普通排序/堆实现确定性拓扑和签名时，可保守记为 **\(O((N+E)\log N)\)**，空间 \(O(N+E)\)。wave 大小选择是 \(O(L)\) 级算术，没有 \(kL^2\) 切点 DP，也没有在线 E0。

安全合并额外成本为：

\[
T_{\text{frontend}}+T_{\text{Step1}}+O(N+E),
\]

不能把冻结 Step1 或官方解析的实际成本武断地称为线性。需要精确 Step2 spill 审计时，可以对唯一候选运行一次；但其时间必须计入求解墙钟，**不是默认快速路径**。

能够保证的是合法编码、特定结构下的权重 burst 读量上界、去除跨核激活 COPY，以及满足条件时的合并执行等价。**不能保证**零激活 spill、Cache hit、优于 V2、最优 Makespan，或安全合并一定加快冷求解。

---

## 七、最小证伪实验：最多 6 次冷构造、12 次外部 E0

每个新方案只做一次 P2、一次 P3 外部评估，固定同一图、配置、环境和资源。P2 在这里仅用于同方案无 Cache 对照，不扩展成另一条优化路线。

| 次序 | 冷构造对象 | 比较对象与主要证伪问题 |
|---|---|---|
| C1 | 044/k4：原 pipeline 构造后做安全合并 | 对照包内 singleton 的 40,927；检查完整操作时间线等价，不只是 Makespan。 |
| C2 | 067/k5：固定五核，完整作业归核，**全本核作业一个 position-major wave**，singleton | `active_stages` 的受控宽 wave 对照，隔离“取消空间流水”的收益。 |
| C3 | 067/k5：本文容量 wave，singleton | 对照 C2，检验小 wave 是否值得付出更多权重重载；也对照旧 pipeline。 |
| C4 | 067/k5：与 C3 完全相同，但安全合并 | 对照 C3，要求执行等价，再比较求解端到端墙钟。 |
| C5 | 067/k5：现有 pipeline 原构造冷重跑 | 给 C2/C3 提供同机墙钟基准，避免拿历史异机秒数作结论。 |
| C6 | 073/k5：取得完整原图后，按相同结构规则构造容量 wave | 检验可迁移性；无原图则不执行，也不硬套 067 的 wave 参数。 |

共 **6 次冷构造、12 次外部 E0** 上限。C6 材料仍缺失时可以不花预算；也可将这一名额用于取得固定 V2 代码后的同机对照，但不能两项都加跑而仍称未超预算。

### 预期 signature

**C1/C4，安全合并：** 四条 Pipe 的操作顺序、逐操作开始/结束、Cache 事件及搬运量应完全一致；只允许子图标签、跨度展示和子图数量改变。任何不一致都直接否定该实现的保序声明。

**C3，容量 wave：** `cross_core_transfers` 应为空；共享权重总读量应不超过 **55,824,000 B**；私有激活 spill 必须单独分账，不能混进权重读取收益里。Cache hit 可能仍为零，这本身不构成失败。

**C2 对 C3：** 这是本轮最重要的比较。C2 的权重读量可能更少，而 C3 应当以更小激活 frontier、更少容量引起的等待来补偿额外 wave 重载。若做不到，就没有理由保留容量 wave 的复杂性。

### 停止条件

安全合并只要一次不等价，就停止合并分支，不扩大合并规则。共享读量超过证明上界，则停止该 burst 实现，先查守卫、锚点或排序错误，不继续调 \(b\)。

若 C3 没有胜过 C2，且没有形成明确的 Makespan—墙钟优势，就停止 wave 大小调参；更简单的完整作业 position-major 可能已经足够。若 C3 只胜过旧 pipeline、仍未达到报告中的固定 V2 **13,422,709 cycles**，只能报告局部改进，不能宣布解决了 067 的剩余差距。073 同理，其 V2 报告值 **2,627,067** 只是尚待独立复评的对照。

墙钟必须包含读取、索引、构造、可选前端/Step1/Step2、验证、回退和写盘；任何在线 E0 的调用与等待也必须包含。外部最终 E0 单列。此次预算很小，能证伪明显退化，**不能靠一个冷样本宣称稳定的 P50/P95 提速**。

搬运统计同时保留三项：官方 `scheduled_copy - original_copy`、实际进入 DDR 池的 COPY 工作量、按字节 Cache hit。官方额外搬运口径会计入被 Cache 服务的 COPY，不能直接把它全部叫作实际 DDR 总线流量。  
（E3：`260–288、539–581、675–682`。）

---

## 最终建议

**下一步不是继续给 cold-setup DP 添加一项罚函数，也不是把 singleton 粗暴收成几个阶段。**

先实现 **完整作业归核、4–5 作业小 wave、同位置权重连续消费、singleton 输出** 的最小版本。它直接针对已经从完整 trace 确认的权重重复读，并在结构上移除了跨核激活输出队列这一整类问题；默认零在线 E0，求解复杂度也比继续做切点搜索更可控。

随后才测试**完整 Step2 输入序列保真的安全合并**。这一顺序把两类风险分开：先检验调度构造是否真正压低 Makespan，再检验编码压缩是否真正压低求解墙钟，不再用一个抽象目标改善或几条 Pipe 顺序相同来替代官方执行证据。