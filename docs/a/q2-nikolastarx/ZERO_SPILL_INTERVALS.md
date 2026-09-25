# Singleton P2 的零 spill 闭区间证书

`src/q2_nikolastarx/zero_spill_intervals.py` 的 `certify(graph, plan, config)` 只读原图、提交计划与 L1/UB 容量，不构造完整 P2 Task，也不调用 E0/E2。返回 `supported`、逐核 `peaks`/`per_core`、`zero_spill_certificate`。`supported=false` 时不作 Step2 判断；`supported=true` 且证书为 `false` 表示未 spill 的原 priority 序列超容量，Step2 可能插 spill，也可能因无 victim 报错。该结果不能用于否定 E2 Makespan 候选。

## 计算与适用域

令本核第 `i` 个 singleton eligible op 对应提交的 `core_schedules` 位置。对每个物理原 tensor，在每个接触它的核取本核 eligible 生产/消费位置的闭区间 `[first,last]`，将 `size` 计入原 `pos`（DDR 在 P2 被物化为 UB）。每条跨核 direct op→op 边，在源、目的核分别加一个 UB、`size=data_size` 的单点区间；同核 direct 边只施加拓扑约束。对 L1、UB 分别扫区间差分，报告峰值及所处 eligible op。两个池、所有核都不超容量，才给出零 spill 证书。区间建立与差分扫描为 `O(|V|+|E|+|T|+Σ区间数)`，不展开调度周期；完整入口另含 `DAGIndex` 及官方校验的拓扑排序等开销，不能把扫描复杂度当作全部求解复杂度。

严格守卫要求：全部子图 singleton；物理 tensor 不带 `logical_tid`；每个物理 tensor 至多一个 eligible 生产 op；原 tensor `size`、direct `data_size`、L1/UB 容量为非负整数；原 tensor 位置仅 L1/UB/DDR；计划通过官方结构校验；同核顺序对代表的 eligible 依赖拓扑合法；由原 tensor/direct 表达的 eligible 依赖与 `DAGIndex` contracted 依赖完全一致。因此 contracted-only COPY 路径等未建模结构被拒绝。暂不声称支持多 eligible producer 或 Step2 以外的内存机制。

冻结官方 P2 的 `_prioritize_task_seq` **不是直接使用** `core_schedules` 作完整 Task op 序列：它先从 Step1 的合法序列取 op，再按子图优先级稳定分桶，并校验重排后的 Task 拓扑。singleton 时，每桶仅有一个 eligible op；输入、跨核 COPY_IN 在其首消费桶内且先于该 op，输出、跨核 COPY_OUT 在其生产桶内且后于该 op。上述条件下，各 COPY 的片上驻留集合包含于关联 eligible op 的闭区间驻留集合；eligible op 的 alloc-before-free 检查点又实际达到该闭区间和。Step2 首次 spill 前的 resident 等于该和，归纳即得“峰值均不超容量 ⇔ Step2 不插 spill 并完成”（若超容量，Step2 可能无 victim 而报错）。证书实现没有执行 `_prioritize_task_seq` 或完整 Task builder；守卫外的排序和 COPY 语义不能由该等价式覆盖。

`python3 -m unittest tests.q2_nikolastarx.test_zero_spill_intervals -v`：4 个极小合成测试通过。测试直接调用冻结 Step2 局部函数作差分，覆盖边界 COPY_IN/OUT、跨核 direct 临时 UB、L1/UB、alloc-before-free、顺序变化和拒绝条件；没有真实图或评分调用。例：同核 8B 输入由 op1、op3 使用，7B 输出由 op2 产生；顺序 `1,2,3` 的 L1 峰为 15B，`2,1,3` 为 8B，不能仅按未排序的输入计划估峰。本证书不保证 Step3 调度、共享 DDR、Makespan 或官方全场景合法性。
