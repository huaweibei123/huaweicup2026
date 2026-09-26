# tensor_packet 独立结构审计

日期：2026-09-24。本审计只读 `tensor_packet.py`、方法文档与冻结官方 P2 重建/调度源码，并增加独立小例测试；没有运行 E0/E1/E2、官方 Step2/Step3、全 100 图构造或网络追查，没有修改根实现和主测试。

结论：在唯一原始 tensor producer、有效 DAG 和合法核数等入口条件内，未发现本方法的无 spill COPY 计数、串行收缩、候选优先级推进或共享组分层的正确性反例。审计发现的重复前驱扫描复杂度问题已由父会话改为增量维护，独立测试确认语义等价。下面的证明保证结构与计数，**不保证官方执行无死锁、容量可行、没有 spill 或 Makespan 更优**。

## COPY 身份与计数

核对的冻结源为 `45f647b395b84e9569f418fd33d62c2b8eb4d190:data/raw/a/official/code/multicore_cut_evaluate_problem_2.py` 的 `_build_scene_b_tasks`。其计数单位不是每条 consumer 边，而是 tensor 在哪些核心生产/消费：

| 类别 | 官方无 spill COPY 身份 | 当前实现 |
|---|---|---|
| 无 eligible producer 的输入 | 每 `(tensor,消费核)` 一次 COPY_IN | `('input',tid,core)` |
| 跨核 tensor | 每 `(tensor,生产核,消费核)` 一对 COPY_OUT/IN | `('tensor',tid,source,core)` 缓存到达 |
| 最终输出 | 有原始 COPY_OUT consumer，或无 eligible consumer：每生产核一次 COPY_OUT | `final` 集合，唯一 producer 被放置时单独计入 |
| 直接 op-op 边 | 每条跨核原边单独一对 COPY | `('direct',edge_id)` |

原始 COPY 节点不会直接搬进任务。输入 tensor 原 `pos` 即使为 L1/UB，P2 也会重建其 DDR 输入；有 eligible 端点的原 DDR tensor 则在本地转 UB。每次生成 COPY 的独占工作为 `max(1,ceil(size/bandwidth))`，与被删除原 COPY 的 `cycles` 无关；直接零字节边仍需两次各 1 cycle 的 COPY。

唯一原始 producer 守卫保证每个 produced tensor 只有一个生产核。多个 consumer 落在相同目标核时只需一个跨核 pair；落在不同核时各需一个 pair。即使该 tensor 同时满足最终输出条件，最终写回也要另外计入，不能被跨核输出复用。当前 `final` 与 `arrivals` 的计数符合这一差别。

`propose` 的临时 `incoming` 先对同一个 packet 内重复使用去重；选中方案后写入全局 `arrivals`，对未来 packet 去重。未选候选的临时字典和时钟不写回，故不会把未执行的候选 COPY 计入累计服务。直接边的缓存 key 不带目标核仍足够：一条原边只有一个终点操作，且该操作只在一个最终 packet/core 被接受一次。

共享链和共享 cohort 路径将整个弱连通分量放在同一核，分量间没有 eligible 依赖，故没有新增跨核 tensor 或直接边 COPY。各核的外部输入集合取并集，全局输出服务单独计一次；cohort 之间共享同一输入且落在同核，也通过已记录输入集合避免重复。内部私有 tensor 的大小、输入/输出数量可以不同，它们不影响按位置拓扑合法性，但仍会影响真实存储与时序。

`no_spill_ddr_service/bytes` 是**固定分核的无 spill 服务需求/字节**，不是 Makespan 预测。最终 `pipeline_packets` 会改变同核顺序，保持分核不变，所以这些 COPY 数量仍适用；之前 EFT 时钟却不再是最终顺序的完整时间线。若出现 spill，实际需求会增加。DDR 服务量与局部 pipe 时钟只通过启发式目标结合，没有模拟真实公平共享。

穿过被排除 COPY 的依赖还需要区别处理：`u→COPY_OUT→DDR→COPY_IN→v` 在 eligible 索引中收缩为 u→v，但官方重建可能只是两个独立端点 COPY。当前 COPY 计数按原 tensor 视图处理，正确计入输出和输入，没有凭空添加跨核 pair；时钟/优先级仍保留较强的收缩依赖，属于保守构造约束，不能称其为官方必然完成路径。

## 为什么串行收缩不会产生环

轻弱分量整体收成一个 packet。弱分量没有与其他分量相连的 eligible 边，整体收缩不产生新的外部连接。

重分量只合并满足 `outdegree(u)=1` 且 `indegree(v)=1` 的 u→v。该边两侧不能存在绕过此边的 u→…→v 路径：u 没有其他后继，v 没有其他前驱。串行链内部也没有外部进入中间点或从中间点退出的 eligible 边。若收缩后的 packet 图有环，将每个链 packet 的进入点到退出点展开即可得到原 DAG 中的环，矛盾。

按 children-before-successors 的原拓扑序扫描时，新链不会覆盖已归属于另一 packet 的节点。否则第一次相遇点会有两个不同的链前驱，违反 indegree=1，或链起点本已被跳过。实现另对 packet 商图作完整拓扑排序和覆盖检查，属于必要的防错检查，不替代上述证明。

这里的“串行”针对 COPY 收缩后的 eligible DAG。一个轻分量可以包含 fork/join，作为完整 packet 仍按其原拓扑序暴露节点，不能因 packet 名称把它当成原图本来就是链。其计算坐标也不是真实执行的串行强制时刻。

## 有界窗口推进的证明与增量实现

证明前提：每个节点恰属于一个 packet；packet 内顺序为原 eligible 拓扑序；`groups[core]` 是同一个全局 packet 拓扑派发序在该核上的投影。实际 `packet_eft` 的 ready 队列确保派发只取所有前驱 packet 已分配的节点，因此满足最后一个前提；函数不承诺任意外部随意重排的 groups 都能推进。

设最早尚未完成的全局派发 packet 为 P。其所有前驱 packet 都在它之前，因此已经完成。P 所属核的更早 packet 也均完成；窗口按该核队列前缀补入且非空核 W≥1，所以 P 必已开放。P 暴露的下一节点的 packet 内前驱位于更早位置，亦已排入；packet 外前驱已由先前 packet 完成。至少该节点可选，候选集不可能为空。每轮排入一个新节点，故有限节点数内结束。

这里的“完成”是优先级生成器把节点/packet 排入理想坐标表，**不是官方运行时已经完成**。算法维护前驱先于后继的排入次序；各核投影因而合法。真实 COPY、内存补边和固定 pipe 队列可能造成不同等待与可行性问题，仍须独立 E0。

审计初版发现每轮对 admitted 头节点重扫全部 `pred[u]`：一个高入度且长时间等待的头节点可能多次扫描同一组边，不能用一次 incidence 总量给出原先的近线性上界。父会话已将其改为：

- `unresolved[u]` 初始化为前驱数；
- `predecessor_release[u]` 初始化为 0；
- 每排入 u，沿每条 u→v 仅执行一次计数递减与 `max(...,finish[u])` 更新；
- 候选检查直接读取计数和最大前驱坐标。

归纳不变量为 `unresolved[u]=尚未排入的前驱数`，`predecessor_release[u]=已排入前驱完成坐标的最大值（空集为0）`。计数归零时该最大值即旧定义的完整最大前驱坐标，因此候选 key 和 tie-break 与旧扫描定义完全相同。100 个随机小 DAG 的完整序列与最终坐标比对一致；一个已开放的 64 前驱 join 等待另核有限窗口的测试，确认当前实现 predecessor 集迭代 0 次、successor 总计仅迭代 64 条边。

## 两类共享守卫应分别表述

`shared_signature` 检查每个作业都有逐位置连续链边，并匹配 pipe、时长和全局共同输入的消费位置。它允许不同作业含不同的额外快捷边。因此它证明的是**主链位置兼容**，不是逐边严格 DAG 同构；快捷边仍指向后续位置，不妨碍按位置生成拓扑序。独立小例中第一条链多了 1→3 快捷边，第二条链没有，对该路径的接受与合法性均验证通过。

`shared_cohorts` 的签名进一步含每个节点的前驱位置集合。相同完整签名给出明确映射“作业 A 的位置 i ↔ 作业 B 的位置 i”，在所有位置逐项匹配前驱集合，因此确实是**COPY 收缩后 eligible DAG 的有序同构**，并保留 pipe、时长及重复外部输入 ID 的位置标签。它不是包含所有私有 tensor ID、大小、形状和内存布局的完整 tensor 图同构，也不保证找到所有可能重编号的图同构。

同 cohort 按位置 i，再按作业 j 排列。每条分量内边从较小位置到较大位置，仍向前；不同弱分量间没有边。不同 cohort 在同核依次拼接也不会新增逆向原依赖。因此合法性不依赖各组共享多少 tensor，或是否启用全部 requested cores。

组内枚举的 r 是允许使用的候选核心前缀规模；greedy placement 未必保证每个候选核心都分到作业。顶层 `active_cores=sum(bool(sequence))` 才是整个方案实际活跃核数。报告时不要只从 cohort 的候选 r 推断每组实际用了多少核。

## 复杂度与模型边界

建议区分 n（eligible 节点）、E（收缩后的 eligible 边）、I（原 tensor/direct incidence）、J（packet 数）、k≤5、W≤8，并另列冻结 COPY 收缩成本 `T_contract`。

- 已有 eligible 图后的拓扑/packet ready 队列操作可用 O((n+E)log n) 粗界；packet 形成及 tail 递推线性于该图。
- 每个节点/相关 incidence 对 k 个候选核各处理一次，EFT 分核主体为 O(k(n+E+I))，不含前述堆与冻结校验成本。
- 修正后的流水优先级为 O(n+E+kWn)，每条边只更新一次，候选扫描每轮至多 kW 个头节点。窗口不是内存容量上界。
- cohort 算术选择对每组最多 k 个 r。每个 r 的作业分配还会比较至多 r 个核，因此计算量一般含 O(k²·作业数) 项，输入集合运算另依赖 I；k 固定很小，但不应将其描述为只做 k 次常数时间比较。
- 到达缓存按输入 tensor/core 和 produced tensor/source/core 保留；唯一 producer 下每个 tensor 最多 k 份目标记录，直接边各有自己的记录。没有缓存实际评分结果。

`T_contract` 不能无条件省略：官方 `_contract_excluded_copy_nodes` 从每个 eligible 源重新遍历可达 COPY 子图。s 个 eligible 源分别经独立 tensor 汇入一条长 L 的 COPY 链，再到一个 eligible 汇，满足唯一 tensor producer，原 incidence 与收缩边数均为 O(s+L)，遍历却可能为 O(sL)。因此“忽略官方校验后全部索引都 O((n+e)log n)”对一般合法输入仍需加此项；父会话已据审计反馈在主文档单列它。结构型算法的有限次数与低复杂度不等于其代理模型一定准确。

## 独立验证记录

测试文件为 `tests/q2/feedback/test_tensor_packet_audit.py`，执行：

```text
.venv/Scripts/python.exe -X utf8 -B -m unittest tests.q2.feedback.test_tensor_packet_audit -v
```

9 项通过，unittest 0.231 秒。范围包括：

- 60 个随机 tiny tensor DAG × 1/2/4 核，共 180 个无 spill COPY 计数核对；
- 同一 source/destination pair 的两个远端消费者仅一对 COPY，另保留最终写回；
- 零字节直接边逐边 COPY、原 COPY 桥的两个重建端点；
- 主链快捷边差异与不同前驱位置签名的 cohort 分离；
- 全部 1024 个按固定拓扑标签生成的 5 节点 DAG：收缩后无环、节点覆盖、商图边一致；
- 100 个随机小 DAG 的增量流水与慢版直接定义一致，以及 64 前驱等待头的边访问计数。

所有构造均为测试内小例，原件未写方案、未调用任何评分。主方法文件、原主测试和协议由父会话维护，本审计只新增独立测试及本文。后续十图实测需要固定最终源码/spec 和真实计时，不能用这些测试或父会话的零 E0 全库结构扫描替代。
