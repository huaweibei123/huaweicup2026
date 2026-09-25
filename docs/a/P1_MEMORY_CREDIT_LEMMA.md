# 固定内存复用边为何足以约束重调度

范围：冻结官方 P1 的一个成功 Step3 执行图，管理 tensor 各有唯一 producer，容量和带宽固定，无原图/Step2 spill。本文讨论容量约束及响应状态，不证明有理数与 E0 binary64/EPS 事件时间一致，不扩大旧 DP 的搜索域或最优性范围。

## 引理：容量信用链

设某一内存位置容量为 C。将初始 VIRGIN credit 想象为总长度 C 的抽象字节标号集合。官方 `schedule_step3.py` 的 `consume_free_credit` 只拆分和顺序消费信用，`release_tensor` 将该 tensor 所占信用归还；没有物理地址或碎片算法。分析时给这些信用附上标号，不改变程序选择。

每个 tensor 的分配取得与其大小相等的标号集合；任一标号的相继持有者形成有限链。若标号由 tensor x 转给 y，官方在 `memory_dependency_parts` 中加入 x 的所有消费者到 y 的 producer 的前驱关系；若 x 无消费者，则加入 x 的 producer 到 y 的 producer 的关系。若同一对已经是数据边，execution_graph 保留原边即可。每个标号只在 x 释放后才能被编译期后续分配消费。

考虑任意满足这个固定 execution_graph 前驱约束的后续调度，操作的输出在发射前分配、输入在所有消费者退休后释放：

1. 有消费者的 x：上述全部消费者均在 y 的 producer 发射前退休，因此 x 对标号的占有已结束。
2. 无消费者的 x：其 producer 已在 y 的 producer 发射前退休，死输出的占有已结束。
3. VIRGIN 标号没有先前持有者。

沿每个标号的持有链归纳，任意时刻至多有一个驻留 tensor 占用该标号。不同 tensor 的同时驻留标号集合不交，总和不超过 C。这给出一个容量可行的抽象分配见证，不要求后续调度重放原 Step3 的分配时刻或释放顺序。

代码中跳过 `source_op == producer_op` 的情况不会破坏本限定域的证明：唯一 producer 的新输出在该操作发射前取得信用；同一操作的输入只有退休时才释放，因而其本次释放不可能在编译时成为本次输出的已可用信用。死输出同理。没有初始无 producer 驻留 tensor 是本文适配器的范围约束。

因此，Step4 可以使用固定的完整 MEM 前驱，而不把地址、当前占用或信用队列加入动态响应状态。这个结论不要求总 tensor 足迹 ≤ C。后续调度的占用峰值仍可能不同于 Step3 报告的峰值；本文仅证明不超过容量，不能把编译期峰值当作后续实测值。

注意：`memory_dependencies[].reused_bytes` 会对同一信用的每个同步源分别记账，不能把这些边的字节数直接求和当作独立内存需求或 DDR 流量。

## 完成前缀的充分性

每条 Pipe 固定 FIFO、单槽执行。其已完成操作集合始终是一个前缀。对操作 u，将所有真实数据/MEM 前驱在 Pipe p 的最大序号记作 need[u,p]。则“所有前驱均完成”等价于对每个 p 有 completed[p] ≥ need[u,p]；无需逐个保留已经完成的前驱集合。原操作持续工作量、DDR 标志、Task 门控和在飞服务状态仍然必须保留。

这论证 `compiled_memory_response.py` 的状态适配范围。若未将 MEM 前驱完整编码、改变 FIFO、容许多槽乱序完成、允许跨核 Task 依赖却未建模，均不能直接套用此结论。

## 缓存与同步分组仍是独立条件

内存状态可以被固定边表示，不等于原图相对 ID 顺序足以确定这些边。官方 `consume_inputs` 和 `release_dead_outputs` 遍历未排序的 Python set；释放信用顺序可能随实际整数 ID 改变。[两个合成 Task 的反例](../../results/a/p1-memory-cache-counterexample-20260925/README.md)已在 Python3.12.13 下显示，接受同一有序描述的链可以有不同直接 `PortOp.need` 签名。该例差异为冗余祖先边，未证明响应值不同；它位于旧编译器拒绝的 MEM/总足迹超容域，不能据此废弃旧限定域或已复评的成绩。

目前研究探针逐位置、逐核编译实际 Task；只在实际编译后的归一化签名相同后复用响应。同步 DP 的正常转移必须确实让各核同起同止；不能对不同签名的若干 Task 仅计算最慢结束时间，就凭空插入 P1 两键接口不可提交的组间屏障。最终不等余数允许单独整体响应，因为之后没有同步组。

源码依据：`data/raw/a/official/code/schedule_step3.py` 的 `add_free_credit`、`consume_free_credit`、`allocate_tensor`、`release_tensor` 及 execution_graph 构造；`multicore_cut_evaluate_problem_1.py` 的激活、退休和发射循环。冻结源码哈希记录于 `results/a/p1-memory-response-probe-20260925/*-certificate.json`。本文件是本机源码数学审查，不是新增 E0 实验。
