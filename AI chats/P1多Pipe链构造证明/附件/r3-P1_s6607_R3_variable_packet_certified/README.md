# P1 R3：可变包宽、带ID顺序的编译商、限定算法类证书

## 身份与结果

研究基点：`huaweibei123/huaweicup2026@1517a8964cc2cd4ec8e4eb322cfb27894d2b4b06`。
本包是独立研究原型，没有提交 GitHub 写操作，没有接入统一算法。

唯一预注册的真实图候选：`source_inputs/data/case_084.json`、五核。JSON 原件 SHA-256 为
`1af22ac8dd69090ed25be62ae1bbb18a922ce99a8cffb2be4f89e7a1234794ee`。
输入来自本会话挂载的官方附件，哈希与固定仓库 summary 一致。
冻结官方七个 Python 文件、config、response_compile.py、response_oracle.py 的身份在清单中。

**新结果是 Fraction 模型结果，不是新 E0 成绩。**

| 项目 | 本轮候选 |
|---|---:|
| 模型 Makespan | 390425 cycles |
| scheduled COPY | 22268010 B |
| extra DDR | 9031680 B |
| spill | 0 B |
| Task 数 | 200 |
| 代表 Task 静态编译 | 210 |
| 最终原图逐 Task 重编译 | 200 |
| 读图至 plan fsync | 8.418897155 s |
| 新进程完整墙钟 | 10.557587902 s |
| E0/E1/E2 | 0/0/0 |

Python 3.13.5、Linux x86_64、共享容器、一个子进程；不把该墙钟与用户 M5 数据比较为提速倍数。
原计划 397542 来自用户冻结静态记录；不是本轮重新运行 packet_dp 得到的结果。
本包代数复演该已知动作序列得到同样模型值，详见 comparison_derivations.json。

## 运行

本包自带最小冻结依赖树。不要覆盖既有输出。

```sh
python -B src/variable_packet.py INPUT.json --cores 5 \
  --output NEW/plan.json --diagnostics NEW/diagnostics.json
```

也可显式使用完整的固定仓库：

```sh
python -B src/variable_packet.py INPUT.json --cores 5 --repo /path/to/frozen-checkout \
  --output NEW/plan.json --diagnostics NEW/diagnostics.json
```

必须保持本清单绑定的官方与 response 模块字节。原型只读这些模块；不修改它们。
`archived_recognizer.py` 只复用 R1 的图视图、严格链识别、结构验证函数；其旧 Step1/时间模型不被调用。

```sh
python src/cycle_certificate.py results/variable_q/diagnostics.json --output NEW/cycle.json
python src/bellman_certificate.py results/variable_q/diagnostics.json --output NEW/bellman.json
```

这两个命令不生成计划、不运行编译器或 E0。cycle 脚本用 scipy.linprog **提出**势函数，
再以 Fraction 验证全部不等式；浮点 LP 结果未经精确检查不会作为证书。
Bellman 脚本从已记录的成本表独立反向计算并检查所有边。

## 1. 状态的严格含义

预先固定每核链列表，按原图确定性排序并 round-robin 分核。任何链的计算节点不跨核。
在同步 Task 完整结束的边界，状态表示：每核已发起 n 条；其最后 r 条只欠最后一个 M。
欠返程的身份必须恰好是该固定列表的后缀，不能在相同计数下任意更换链。

一个推进 Task 包含旧 r 条返程、新 q 条链中的前 q-s 条完整链、新 q 条链的后 s 条前缀。
所有旧返程都在该 Task 完整退休；下一状态是 (n+q,s)。drain 取 q=0,s=0,r>0，状态变为 (n,0)。
禁止空 drain。所有数据边和核内顺序边均沿每核动作序向前，故联合 Task DAG 无环。

每种位置的并集足迹为：

\[
F_p(r,q,s)=rF_{R,p}+(q-s)F_{W,p}+sF_{P,p}\le C_p.\tag{R3-A01}
\]

不同链的 tensor 私有，所以这里是精确的不同 tensor 总和；它仍是对**同时存活量**的保守上界。
单生产者与总并集不超容量保证无 SPILL；全程只需 virgin credits，因而没有 MEMORY_REUSE 边。
这些结论不消除 Step1/FIFO，也不消除共享 DDR 与 Task 完成门控。

固定源图、列表与后缀后，(n,r,q,s) 唯一确定成员集合。P1 Task 结束时四个 Pipe 和 DDR 在途项已清空。
因此在所有核确实共同释放的模型域内，没有必须携带的旧物理缓存状态。
初始门控用每条边都加 gate、最后减一次 gate 的记账方式处理，不需要额外 history 位。

无后缀约定时，计数不充分：本包三链微图在相同 n=2,r=1 下，留下不同旧链，
实际官方编译的 M FIFO 分别为 [201,3] 和 [103,201]；模型时长为 32 与 42。
这是同一图的两种成员选择，不是修改该图的 ID。最小补充状态是待返程链的身份集合。

## 2. 终端不等长余数

同步前缀只推进到所有核共同的长度 B。round-robin 分配使各核剩余零或一条新链。
在 (B,r) 的共同释放边界，精确计算两种固定尾部宏：

* 旧返程与本核未开始的完整余数链并入一个 Task（并集容量不允许就拒绝该宏）；
* 先 drain，再在本核执行完整余数链。

对尾部**所有核的全部 Task**显式执行 Fraction 模型；不再依赖相同签名，也不添加跨核屏障。
源状态只需 (B,r)，因为各核余数与旧返程身份已由原列表决定。尾部内部若还要逐步决策，
则需要每核进度、释放偏移、FIFO 前缀和在途 DDR 剩余量，不能继续用单一 (n,r)。

更早开始异步尾部、改变分核、跨多个 Task 保留尚未执行的旧返程、任意选择待返程集合，
均不在本原型最优性结论的算法类中。

## 3. 编译前等价不是无序图同构

缓存 key 是以下有序对象的完整 tuple，而非只用一个哈希：

1. 原计算操作按数值 ID 升序，保留 op/pipe/cycles；
2. 原 touched tensor 按数值 ID 升序，保留本地位置、字节、生产/消费操作的上述 rank；
3. 按原完整图谓词得出的 input_boundary/output_boundary 位；
4. 本地直接计算边的 rank 对。

缓存仅存在一次构造进程内，固定编译器与配置不变。若将来持久化，编译器全部依赖和配置身份也必须入 key。
SHA 只用于审计展示，缓存命中比较的是完整结构 tuple。

**充分性证明。** 相同 key 给出保持计算 ID 顺序、tensor ID 顺序和边界谓词的双射。
官方边界 COPY ID 均在该原输入全部 op ID 之后，且按 sorted touched tensor、input 后 output 的次序单调分配。
故生成 ID 的具体起点和中间避撞空洞不影响 Task 内相关操作的相对次序。
TaskProjection 的 COPY_OUT 标记同样不改变这个序型。
于是 Step1 的深度、COPY 类型优先级、数值 ID 破同分均对应，所得序列对应。
由单生产者和总 footprint 证书，Step2 没有插入选择，Step3 没有内存补边；
FIFO 投影、数据前驱、逐 COPY 工作量与 DDR 标记对应。因此返回的 port signature 与搬运字节相同。
不声称 cross_task_traffic 等所有诊断元数据都相同。

通用实现可对每条实际转移的各核成员重新构造该 key，只对新 key 官方编译。
本包再提供更强但易检验的充分条件：
各链的内部**有序**描述相同，而且每条链的计算 ID 块及 touched-tensor ID 块在链列表上互不交错并递增。
该条件一次检查全部链；任意“旧后缀返程—新完整链—新前缀”的有序并集只由 r,q,s 决定。
所以每个三元组只需一个真实代表编译；不需遍历 n 和 core 编译。
互相交错的 ID 块被此快路径拒绝，不做无证据的无序归并。

这是冻结 no-spill/no-reuse 子集的编译签名等价，不是任意图、任意内存行为、任意源码版本的等价定理。
它也没有证明 Fraction 与官方全局 binary64/EPS 运行的普遍零差分。

## 4. DP、复杂度与验证层次

n 从零到 B。每层先将所有可达 r>0 用 drain 向 r=0 闭包，再沿全部容量可行 (r,q,s) 边推进到 n+q。
每边成本是对应 K 核同步 quotient 的完整响应加 gate；次级比较 scheduled bytes、Task 数，不混合单位。
终端比较尾部宏成本，最后减去不存在的首个 gate。

若返程上限为 R、新链数上限为 Q，则状态数 O(BR)，转移松弛 O(BRQ²)。
在 ordered-block 证书域内，官方代表编译数为 O(RQ²)，最后完整计划再逐 Task 编译一次。
每次编译、Fraction 响应和原图解析的成本另外计算；不把完整 CLI 声称为 O(n log n)。
本包代表编译预算512、最终编译预算2048；失败即拒绝，不自动扩预算或改比例。

最终从完整原图重新调用冻结官方 Step1/2/3，逐 Task 比較 port signature，重算完整计划响应及 scheduled bytes。
这个终检只证明选中计划通过所列核验，不能单独证明未选边准确。
未选边的保证来自前述有序 key / 全族序块证书和每一类型的真实代表编译。
例如真实两条路成本10、9，代理报10、100，第一条终检通过仍不代表最优。

## 5. 本轮的容量结构与新周期

原件静态核验得到，每链前缀 / 返程 / 整链足迹：

| 部分 | L1 B | UB B |
|---|---:|---:|
| P | 10752 | 18626 |
| R | 6144 | 4608 |
| W | 16896 | 18626 |

UB 条件化为：

\[
18626q+4608r\le131072.\tag{R3-A02}
\]

Qmax 和 Rmax 均为7，皆由容量与图宽导出；不写入选择器常数。
DP 的主要循环为 r=6,q=5,s=4 与 r=4,q=6,s=6，其 UB 足迹为120778与130188。
代表同步响应分别10115、9445；再各加100门控。首轮是 r=0,q=6,s=6，响应8405。
19个循环后每核发起215条，最终 pending=6；两核额外各一整链的合并尾部显式响应6480。

\[
8405+19(10215+9545)+100+6480=390425.\tag{R3-A03}
\]

这比冻结397542模型少7117周期、约1.7903%，但多92160B额外DDR。
是完整响应与装包的联合变化，不能归因于仅减Task数或仅提高容量利用。
仅把冻结路径尾部合并的代数值为396101；它不是本轮第二个候选构造。

## 6. 限定范围的下界与最优性证书

给转移图每条边定义：

\[
c_e\ge\lambda q_e+h(s_e)-h(r_e).\tag{R3-A04}
\]

所有普通边及 drain 都精确核对后，路径上相加给出：

\[
C\ge\left\lceil\lambda B+\min_r\{h(r)+\psi(r)\}-h(0)-g\right\rceil.\tag{R3-A05}
\]

* 固定容量包宽的子类：lambda=9111/5，41条不等式检查，有限下界392842（已允许本包两种尾部宏）。
* 可变包宽的子类：lambda=19760/11，210条不等式检查，有限下界387703。
* 新周期的 cost/q 比恰好19760/11，所以这是该转移图的最小周期比，而不只是 LP 猜测。

**390425 低于固定包宽子类的392842下界**：在声明的模型与构造域中，改善确实需要越过固定包宽限制。

另外，独立反向 Bellman 标签对43884条有限图不等式作整数检查，源标签390525。
选中路径含人工首门控的成本同为390525，减100得到390425。
因此390425是**本包明确列出的有限同步算法类，在Fraction/整数退休模型中的最优值**。
不是全 P1 最优，也不是已验收的官方 E0 值。

R2 全图下界335819的私人真spine、完整链连续FIFO、全内部切口最低154服务等条件继续保留。
本轮没有把模型390425替换为官方全局上界；已有官方上界仍以本机保存的399121为准。
719仍仅为R2放松下界中的交叉位置，没有作为本原型切链比例。

## 7. 实账与边界

* 一个预注册候选进程，成功、无重试，210代表+200最终静态Task编译；0 E0/E1/E2。
* 一个五项微检验进程，4次小Task官方静态编译；0候选、0 E0/E1/E2。
* 周期势函数和反向Bellman证书各一个后处理进程；0编译、0候选、0 E0/E1/E2。
* 结构读取、哈希检查和已有动作序列代数复演不计为性能实验。

总新增静态 Task 编译414次，真实图候选构造1次，E0/E1/E2均零。
详见 results/ledger.json、results/state_cache_tests.json、results/cycle_certificate.json、results/bellman_certificate.json。

失败边界：非私人输入、非单生产者、内部COPY桥、非同型链、ID块交错、超出保守footprint、
编译后有spill/MEM、第一处不同步后继续用单一状态、任何签名/流量/模型复核不一致。
前三类可交给现有一般算法；ID块交错可另实现逐边完整prekey缓存，但不能当作本包快路径已支持。
异步/错相需要恢复在途DDR和各核释放偏移，不能仅在现有DP成本上添加一个经验折扣。
本轮没有构造异步候选，没有扩大官方或全100实验。
