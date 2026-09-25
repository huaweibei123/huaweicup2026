# Pro r05 ready-exchange 静态审查

审查对象：`AI chats/20260924-P2-异构流水与最优性界/r05-response-be229faa.md` 及同轮附件 `p2_r05_ready_exchange/{README.md,ready_exchange.py,ready_exchange_candidate.py,fixed_domain_audit.py}`。只读源码与已归档论述；未运行真实图、构造新候选或调用 E0/E1/E2。附件的合成测试脚本会写 `test_results.json` 到附件目录，因此本次没有在限写区外执行它。

## 已核

- **R5-09 数学等价成立，但域必须保持原样。** 对物理 tensor `t` 先移除整个批次的包 pin，其余 pin 的核集合为 `R_t`。批内目标核单射时，新引入且不在 `R_t` 的核互不重复，故 `|R_t∪{π(i):i∈A_t}|=|R_t|+Σ_i 1[π(i)∉R_t]`。无外部 pin 时，常数含 `−w_t`；重复触碰同一 tensor 的操作须先按包去重。固定边界项和不同物理 tensor 各自计数；不能推广到批内多包同目标核。`ready_exchange.py:124–141` 以 pin incidence 和暂定归属计数构造矩阵，`277–285` 先扣旧批次 pin 再加新归属，最后用全网 `net_cost` 复核；这与定理一致。
- **工作量与试放条件是条件性的。** 每个暂定源核最多取一个 ready 包，使原归属成为单射参照；每个目标核最多收一个包，故 `L⁻_{c,p}+w_{i,p}≤T̂₀` 的逐边检查足以保持全核/全 Pipe 工作量不变量。批次是分核事务，不是执行屏障；同批包互无依赖且目标核不同，按已承诺前缀的持久日历分别试放可以联合采用。`replay` 对 seed 与候选使用同一操作级 lag/FIFO 模型。它不证明官方 Makespan、COPY 争用、spill 或容量。
- **局部精确匹配与全程保护分层正确。** 阈值二分调用整数指派，字节预算和字节优先的编码成立；逐批暂定 connectivity 字节不增。最终共同代理时间另行重放，弱 Pareto 门槛失败则返回 seed。局部瓶颈改进不蕴含全局代理改进，代理改进也不蕴含官方成绩改进。
- **固定域审计口径有条件成立。** `fixed_domain_audit.py` 用低 lag 相等约束与异核同 Pipe 正长度重叠合并 flip 块，使用半开操作区间；其结论依赖输入完整覆盖全部静态 lag、Pipe 与物理超边，审计器本身不重建真实 DAG 的这些输入。

## 明显缺陷与待核接入

1. **真实规模预处理可无谓地变成二次时间。** `ready_exchange.py:205–207` 在每条 net 的校验里重建 `set(owner)`；若有 `H` 条 net、`P` 个包，这一步是 `O(HP)`，不在所宣称的 `O(kN log N+kI+Rk³ log k+E+N log N)` 内。应在循环外构造一次 owner 键集合，再谈 003 的端到端耗时。该项不破坏数学结果，但可能让原型在大图上远超 30 秒。
2. **真实 DAG 适配尚未验证。** `ready_exchange_candidate.py:23–68` 假定从旧链按 Pipe 切分后每段仍单 Pipe、连续操作有真实依赖，且 `DAGIndex` 的 contracted `succ` 与保留的 tensor/direct 操作边完全相同；`:61–62` 不符即拒绝。该检查保留了零字节时序边，但只验证“边对”覆盖，物理 pin/边界费用一致性仍要靠 `:73–77` 的独立 `mandatory_copy_work`。`build` 只对 `UnsupportedStructure` 回 seed；其他验证失败会显式抛出，不能把未跑过完整仓库的附件称为可用候选。
3. **日历与复杂度是待实测条件。** 附件使用自带 `calendar_avl.py`，README 却建议项目适配复用既有 `gap_calendar.py`；二者接口表面相同，真实接入必须确认持久试放不污染已承诺日历、`earliest/reserve` 的耗时及内存。复杂度式还依赖每包仅处理一次、incident 更新按关联量摊销、每批最多 `k≤5` 个包；实际时间另含旧 seed 构造、Python 数据结构、最终 `derive_multicore_plan` 与独立字节复核，不能把匹配调用时间当完整求解时间。
4. **质量保护未覆盖官方目标。** 候选只比较预 Step2 字节与静态代理时间，未建模共享 DDR/COPY FIFO、缓存/溢出及官方事件顺序。`build_from_seed` 的结构校验与独立字节复核必要，但无法替代 E0；在现有 baseline＋候选两评分协议里，未评分的旧 gap seed 也不能凭本构造获得官方 incumbent 保护。

## 最小值得试验与优先级

先修第 1 点，再以已冻结 003/k2 seed/witness 做**一次限时接入预检**：不按 case ID 分支、不重新搜索 seed；记录阶段包数、各批非原核允许边、严格字节下降批次、匹配调用数、完整构造墙钟、共同代理时间，以及独立预 Step2 字节。先核与 seed 的计划/输入/配置身份；若无代理弱 Pareto 改进即停。只有预检在明确预算内形成可验证计划，才考虑另行安排官方成对复评。此处没有执行该试验，也未把合成反例提升为真实收益。

**不应阻塞当前已有三格 20–29% 官方改进的 cut-retime 全量取证。** r05 提供更宽的重排域和可信的条件性字节子问题，但真实 DAG 适配、端到端时间与官方 Makespan 均未证实；先完成已获收益路线的同一固定版本全量证据，再用独立预算检验 r05 是否带来额外 Pareto 改进。
