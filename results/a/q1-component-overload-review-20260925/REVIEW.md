# component_overload 固定版本独立结构审查

**可执行结论：未发现阻塞 054/050 五核两格小试验的实现错误；没有必须先修的代码项。** COPY 收缩、同波装箱、保留组件合包、统一拓扑放置与同核顺序的组合证明成立。此结论只覆盖输入/输出合同、Task 增广 DAG 与等待公式，不代表 Step2 容量可行、官方成绩改善或未来真实图验收。

## 固定范围与验证

目标提交 `3c6e41b938c764d207de45584fb526c64f4eb845`：

- `src/q1/component_overload.py`、`tests/q1/test_component_overload.py`、`docs/a/Q1_COMPONENT_OVERLOAD.md`。
- 为核对组合证明，读取同提交 `heavy_suffix.py`、`sink_peel.py`、`bounded_tasks.py`、`component_pack.py` 及官方 `stub_multicore_cut_and_schedule.py`、`evaluation_validation.py`。官方 P1 等待语义沿用已逐字核对的冻结源码 `multicore_cut_evaluate_problem_1.py:318–329`。
- 未修改作者 worktree。执行时作者 HEAD 已因其他归档推进至 `933ff8a4…`；被导入的实现、依赖、原测试和配置在执行前后逐字节核对，均等于指定 `3c6e41b…`，详见 [result.json](result.json) 的固定源码哈希。
- 命令：`python3 -B results/a/q1-component-overload-review-20260925/probe.py ../q1-overload-list-20260925`，从本独立 review worktree 执行。可把最后参数换成包含相同固定文件字节的只读 checkout。
- 原有6项合成测试与新增6项独立合成测试全部通过。未读取 case 原图，未执行真实图 construct、Task 编译或 E0/E1/E2；检查这些编译/评价模块没有被加载。脚本只向本审查目录写结果。

## 1. 合同与 quotient DAG：通过

`construct:115` 先运行既有 fallback 链，因此 core 域 `type(int), 1..5`、非空且唯一的 compute IDs、非负整数 cycles、原始图合法性均已在进入新构造前验证。新阶段三处负载计算统一使用 `max(1,cycles)`（`:32/:61/:133`）；没有把零 cycles 当免费操作。输出严格两字段、仅覆盖非 COPY compute、保留原 compute ID 与 mapping 插入顺序，不修改原图；最终由 `derive_multicore_plan` 加 `validate_task_order` 再核对。

COPY 收缩使用官方同一 helper（`:122–123`）。所以中间 COPY 路径不会把本应有关联的 compute 错分为两个弱组件。共享的外部 COPY 输入若没有 compute 上游，只形成多个 compute 的共同输入，不制造 compute 间边；把这类组件当数据上独立是正确的，输入复用/容量仍可能关联。

对一个 active DAG，若 `u` 只到达一个 sink，则其 active 后继到达的 sink 集合非空且为该单例的子集，因此仍在同一 packet。不同单例 packet 之间没有边；剩余多 sink 部分是 predecessor-closed。反向排列剥离所得 waves 后，每条跨 packet 依赖都指向后波。`:164–165` 只合并同一组件同一波的独立 packets，不会制造 quotient 环。不同 COPY 收缩弱组件之间没有边；`:173` 合并完整 retained 组件同样安全。无可拆包、预算超限的组件保持完整，且发生预算例外时不会使用半成品 waves。

`_place:63–75` 还显式核对商图无环，原测试中的 `[1,3] / [2]` 非凸链收缩反例确实在 placement 前被拒绝。

## 2. 全局 placement 与 core 序联合证明：通过

`:85–101` 的 ready 仅包含所有数据前驱已被放置的 Task。每次追加到某个 core 时，为它赋予严格递增的统一 placement rank。因此：

- 数据边的 rank 严格增加；
- 任一 core 队列是这一个 placement 序列的子序列，新增 core 边的 rank 也严格增加。

两类边联合仍是 DAG。这里“已放置”不必是“已在真实模拟中完成”：证明需要的是拓扑顺序，代理时间仅影响合法候选中的择核，不能使拓扑方向倒退。独立组件穿插在不同组件 waves 之间也不破坏证明，不需要一个人为的全局 wave barrier。

末尾 `split_large_tasks` 会先核对原联合 DAG，只在一个 Task 的内部独立分量之间切块，然后在原 core 位置用同 core 链替代。将每个原 Task 在某个联合拓扑序中替换成其有序块链：跨原 Task 边保持原 block 顺序，块内新增边只有链的前向边，所以仍无环。原 Task 内具有依赖的节点由 union-find 保持在同一块。新增合成测试用更小阈值实际覆盖了这个组合步骤；没有为测软切块而构造大型真实图。

## 3. 官方同核/跨核等待：通过

`_place:89–92` 使用

`start(t,c)=max(previous_finish(c)+same_wait, max_p(finish(p)+(core(p)!=c ? cross_wait : 0)))`，

未使用过的 core 无 previous gate，且空前驱集合给0。这与官方 P1 `task_release_time` 对应：上一 Task 结束后同核等待100；远端数据前驱结束后1000；同核数据前驱本身不额外再加100。因为所有同核前驱已在当前核链更早处，上一 Task 的完成已经涵盖其完成，不会漏掉隐含同核条件。

新增合成见证：根工作10，两个分支工作1000，K=2；placement 得 `[[root,branch1],[branch2]]`，代理开始时刻为 `[0,110,1010]`，分别检查同核 gate 只算一次和远端+1000。参数实际从固定 config 读取，而非把这两个数字当可调优化变量。

这只是**等待公式正确**。Task 权重取最大 compute Pipe 工作，遗漏局部原依赖所需串行时间、FIFO、COPY、内存约束，不能因此把代理完成时刻称为 E0。`placement` 还位于软切块之前，不能直接当最终计划的时长或下界；文档已明确这两点。

## 4. 正整数 threshold：通过，解释边界清楚

判断 `W(C,p) > (W(all,p)+K−1)//K` 与 `W(C,p)>ceil(W(all,p)/K)` 对正整数工作等价。严格大于比较没有误写为 `>=`。新增合成检查：

|组件工作|全图该 Pipe 工作|K|向上取整均分值|该组件拆分触发|
|---:|---:|---:|---:|---|
|3|9|3|3|否|
|4|10|3|4|否|
|5|11|3|4|是|

全零 cycles 的五 compute 合成图按 `max(1,cycles)` 得总工作5，三节点 fork 组件工作3，K=3、阈值2，正确触发，Task 权重全部正数。任一 Pipe 上不可能有K个组件都严格超过均分值，因此每 Pipe 至多K−1个超载组件的说法成立。

这个触发器只说明“整个组件必须留一核”比该 Pipe 理想均分值更强地限制方案。它不证明理想均分可达到，不证明该 Pipe 是整体瓶颈，也不证明拆分能补偿新增 gate/COPY。文档没有把它升格为收益定理。

## 独立新增的6项测试

1. 严格 `ceil` 阈值的整除/非整除/越界三点。
2. 零 cycles 归一为正工作，输入保持不变。
3. V、M 两个不同 Pipe 的组件同时拆分，加两个 retained 组件；四者共享同一外部输入，检查组件数、统一 rank 的全部数据/core 边、确定性、覆盖与原顺序。
4. 两个连续 COPY 形成的内部桥保持组件归属和跨 Task compute 依赖。
5. 同核与跨核 gate 的具体代数见证。
6. 后置软切块保留原增广 DAG block 顺序。

没有新增失败反例；无需以泛泛的性能风险阻塞计划中的两格有界试验。运行结果应明确新方案会重新装箱 retained 组件，可能改变共享输入 COPY 数，不能继承上一“保持旧 bundle 前移”方案的流量不变结论。已有 docs 已写明这一点，未要求热改。
