# 固定 owner 的容量安全相邻交换

`capacity_safe_retime.retime(graph, seed, target, config)` 只调整 singleton 计划的每核顺序。入口要求 seed 的 `zero_spill_intervals.certify` 为 `supported=true` 且 `zero_spill_certificate=true`，target 也落在同一证书适用域，二者 `node_to_subgraph` 和子图所属核完全相同。失败抛出 `UnsupportedStructure`；输入不变。返回计划及尝试、接受、依赖拒绝、容量拒绝次数和是否到达 target。

算法按 target 的每核 rank，先左到右、再右到左各扫一次相邻倒序对，至多 `2Σ_core(max(0,n_core−1))` 次尝试。仅当交换的两个 eligible op 没有相互依赖，且新位置的 L1/UB 闭区间驻留均不超容量时才接受。每个原物理 tensor 的本核 touch 位置集合维护闭区间端点；只触碰二者之一的 tensor 会改变端点。跨核 direct 边的临时 UB size 随端点 op 移动。计算交换后的两个位置，再提交 touch 集合、驻留量与顺序；其余位置的闭区间量不变，故由 seed 的零 spill 证书归纳保证每次接受后仍为零 spill。全部 owner 保持不变。

预处理时间/空间为 `O(V+E+T)` 加入口两次证书成本。每次尝试扫描二 op 的 touch 集合差；每个受影响 tensor 用位置集合重新求 `min/max`，故尝试代价为 `O(Σ受影响tensor的本核touch数)`，极端高扇出时可退化到 `O((V+E)·E)`；这是有意保留的简洁原型，不声称对高扇出图最优。两次扫后仍可能停在容量或依赖局部障碍，`target_reached=false` 不代表全局不可改善。这里的零 spill 是冻结 P2 的原 priority/Step2 条件证书，不保证 Step3、共享 DDR 或 Makespan 改善；没有运行完整 builder、E0 或 E2。

验证：`python3 -m unittest tests.q2_nikolastarx.test_capacity_safe_retime -v`，5 个合成测试通过（含20个固定随机种子的逐次全量证书重算对照）。覆盖成功相邻交换后重新 `certify`、容量拒绝、非法依赖 target 拒绝、跨核 direct 的 UB 单点迁移。另在此前已保存的005/009/015固定seed和target上只做构造与容量证书核对，0新E0/E2；结果见 `results/a/q2-nikolastarx/capacity-safe-diagnostic-20260925/`。三个构造均保持零spill且计划改变，尚无Makespan证据。


随后对固定015/K5修复计划执行单次官方E0（Colab，0 E2/0重试）：Makespan
40828→40701（下降0.3111%），spill仍0，added DDR仍317952B。原件与哈希见
`results/a/q2-nikolastarx/capacity-safe-diagnostic-20260925/official-015-report.json`。
这是固定seed机制探针，未纳入295统一算法或新的完整批次，不能外推全量收益。
