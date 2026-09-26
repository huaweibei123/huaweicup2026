# P2 singleton eligible 同 Pipe FIFO 弧审阅（R5）

结论：在**合法 singleton 计划且冻结 P2 完成局部编译和全局执行**的条件下，可以从每核 `core_schedules` 的 eligible 顺序中，分别投影出每条 Pipe 的 eligible 列表，并对其中相邻两项加入零额外通信 lag 的完成→发射弧。这些弧是官方固定 Pipe FIFO 的子序列约束，可用于强化 R5 的物理 eligible 最长路径。不能把每核整个 `core_schedules` 链成串行依赖，也不能把投影中两 eligible 之间可能插入的 COPY/spill 时间另加到该零 lag 弧上。新增弧后仍按实际操作时长计顶点权。

## 冻结源码链

`derive_multicore_plan` 验证 singleton 映射覆盖与核内子图顺序（`stub_multicore_cut_and_schedule.py:114-196,217-242`）。P2 每核将 eligible 原 op 加进本地 Task，`step1_schedule` 得到完整局部拓扑词，`_prioritize_task_seq` 按 `subgraph_order` 稳定分桶且再次校验拓扑（`multicore_cut_evaluate_problem_2.py:43-59,85-86,244-250`）。singleton 时每桶只有一个 eligible op；所有 eligible 的相对顺序恰为该核 `core_schedules`，不依赖 Step1 对各桶内部的选择。基础 COPY 可能混在桶中，但不会改变 eligible 子序列。

Step2 对逻辑 tensor 生成新 incarnation、重接 consumer 边，原 op 的 ID 和 Pipe 保留；它的 `seq_ext` 构造逐一遍历原 `seq`，只在前后插入 spill op（`schedule_step2.py:291-429,443-456`）。因此投影掉新 spill op 后仍是原 `seq`，其 eligible 子序列未变。`_build_extended_graph` 原样组装该序列（`:473-489`）。Step3 直接按 `seq_ext` 投影固定 `planned_pipe_orders`，成功时原样作为 `pipe_orders` 交给 `prepare_step3_execution` 的 `pipe_ops`（`schedule_step3.py:281-287,579-581,675-703`）；内存复用边只增依赖，不重新排序 Pipe。全局 P2 仅允许每条 Pipe 的 `pipe_cursor` 指向当前 op 发射，前项完成时才推进 cursor 并唤醒下一项（`multicore_cut_evaluate_problem_2.py:381-412,455-483`）。所以对同核同 Pipe 的相邻 eligible `u,v`，即使实际 FIFO 中夹着 COPY/spill，也有 `start(v) >= end(u)`；零 lag 弧安全。

## 用法和边界

按 `core_schedules` 顺序把 subgraph ID 还原成 eligible op ID，按原 op 的 `pipe` 分四个列表，只给每个列表的**相邻项**加 `u→v`、边权 0。它与真实 tensor/direct 物理弧并存；若同一对已有数据弧，保留两弧或取更大的通信权，不能相加。然后运行一次 DAG 最长路径，顶点仍用 `max(1,cycles)`。中间 COPY/spill 的 FIFO 时间和容量等待被忽略，故下界保守；跨不同 Pipe 的相邻 `core_schedules` 节点没有此必然先后，可同时运行。例：同核顺序 `a(M,2), b(V,3), c(M,5)`，即使 `b` 在清单中夹于两者，所加弧只有 `a→c`，路径下界 7；把 `a→b→c` 串起来得到 10 是无依据的。

**入口合法不保证加入 FIFO 后无环。** `derive_multicore_plan` 只检查 contracted 子图 DAG 和每核直接依赖的先后（`stub_multicore_cut_and_schedule.py:188-231`），未在此合并所有核内顺序与跨核依赖查环。具体四 eligible 反例：核 0 顺序 `A,B` 且两者同 M Pipe，核 1 顺序 `C,D` 且两者同 M Pipe；原图仅有跨核 direct 边 `B→C` 与 `D→A`。原图和 contracted DAG 无环，各核无反序依赖，入口可接受；加入必然的 Pipe FIFO `A→B`、`C→D` 后得到 `A→B→C→D→A`。此计划在完整执行中没有可比较的正常 `M`；不能对带环图套最长路径、给出有限下界并声称官方成功。实现须显式检查扩展 eligible DAG，带环就拒绝增强量并报告候选失败/未知，不能悄悄求值。即使 eligible 小图无环，局部 `_prioritize_task_seq`、Step2/3 仍可能因容量、FIFO/内存复用约束失败；全局 `validate_execution` 将所有 COPY、完整 Pipe FIFO、内存边和跨核 link 合并查环（`evaluation_validation.py:226-243`）。若不是 singleton、`core_schedules` 与实际 P2 `seq_ext` 不匹配，或实现未来改变 Step2 原 op 子序列保持性，不能照此加弧。

本审阅只给精确模型中从源码可追溯的 FIFO 必要顺序。冻结 DDR 使用浮点和整数事件投影，整套 `W/P/D` 下界仍须区分理想模型与机器级严格证书；本次没有运行真实图、Step2、Step3 或 E0，也没有声称任何新增官方成绩。

## `ideal_bounds.py` 窄代码复审

后续只读 `src/q2/feedback/ideal_bounds.py`、对应八项纯合成测试及它复用的 `service_profile`；主会话报告相关 19 项单测已通过，本复审没有重跑。物理弧只从唯一 eligible producer 的真实 tensor 消费者及原图 direct eligible 边建立；跨核取 `2*逐条COPY服务+delay`、同核 0。`_longest_path` 对平行边和多前驱维护 `max(release)`，不会把多个输入相加。Pipe 工作按 `(core, pipe)` 累加，FIFO 只沿各核 singleton 顺序同 Pipe 相邻 eligible 加零 lag 弧，增强图在取最长路径前会查环，检测到环即拒绝。返回名称和模块说明均明确这是**固定 B 候选、理想模型**的必要下界，不能当全局最优下界或官方 E0 成功证书。`service_profile` 现已为跨核 direct 的归一化大小加入 `<=2^31` 守卫，覆盖上一轮指出的高整数取整差异；tensor 大小、eligible cycles、bandwidth 也有限域，delay 单独限制到非负 `<=2^31`。这些守卫仍不构成冻结浮点事件误差证明。

一处**元数据口径**需改名或加说明：`ignored_contracted_pairs` 计的是 `index.succ` 中**完全没有任何物理弧的 (u,v) 端点对**，不是实际被排除的原 COPY 收缩路径数量。若 `u→v` 同时有真实 direct 边和一条穿过原 COPY 的路径，该值为 0，但那条收缩路径确实没有进入关键路径图。它不影响 `ideal_lower_bound_cycles`，不可将此字段当“全部忽略的 COPY 路径数”用于解释诊断。另 `candidate_lower_bound` 对同核 direct 边也计算一个随后被零 lag 覆盖的 `service`；在已守卫数值域内只增加少量算术成本，不改变下界。

本次结论限于上述静态源码和测试覆盖面；未执行真实图构造、Step2/3 或 E0，未审计生产环境机器浮点误差，未验证任何保存方案的官方 Makespan。
