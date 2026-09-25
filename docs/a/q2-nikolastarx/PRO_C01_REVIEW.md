# C01 审查：可证范围与最小补件

依据：`AI chats/20260925-P2-零spill通信与流水联合构造/c01-response-799ca0a0.md` §2–3；冻结官方 `data/raw/a/official/code/`。本次仅读源码，未调用构造或评价器。

1. **发射等式有条件成立。** 官方 `schedule_step3.py:30` 固定每 Pipe 单槽；P2 `multicore_cut_evaluate_problem_2.py:374–477` 在完成事件后推进 Pipe 队首、检查全部本地前驱和全部外部 OUT 的 `end+delay`，就绪即发射。因此对**完整 prepared 图**、实际 `pipe_ops`、实际完成时刻，`s=max(D,A,F,R)`没有另一个独立的发射门槛；共享 DDR 改变的是 COPY 完成时刻。`D/A`须按实际 `execution_graph` 区分，重合边取并集，不能用原图推断；`F`须用 Step3 的 Pipe 顺序。若少了内存边、spill COPY 或跨核连接，等式残差不能称 DDR 等待。官方最终 `step3_by_core` 仅输出内存依赖**数量**（P2:581–590）。

2. **缺口是 prepared 快照，不是新评价器。** `schedule_step3.py:583–608,675–704` 已有 `memory_dependencies`（source、target、kind 等）、`execution_graph`、`op_preds`、`pipe_ops`；P2 `_build_scene_b_tasks` 在 245–272 行持有各核 prepared tasks 和 `cross_links`。现有 E2 位于 `q2-feedback-s8ee/output/q2-e2-paircheck-603b-s8ee/research/a/e2_search/scene_b.py:84–91`，编译时取得 tasks，随即 pack 并删除；`evaluate_record(debug=True)` 只返回 native 调试量，不恢复具体内存边。最小后续动作是在**已有编译/准备边界**为指定计划导出这些字段及图/计划/配置哈希，保留运行口径；不修改调度和浮点事件器。本次禁止的重新准备未执行。`zero_spill_intervals.py:18–126` 只证明受限 singleton 的 Step2 无 spill，不证明无 Step3 内存边。

3. **接收闭包命题需限定对象。** P2:133–205 对每个 `source_core→target_core` 的 tensor 连接仅建一对 COPY，目标锚在该核最早消费者。因此固定唯一生产者在 `a`、`a≠b`、重建规则不变时，删除该 tensor 的 **a→b 跨核对** 当且仅当 `b` 无消费者。不能解释为删除该 tensor 的所有 COPY：边界输出写回仍可能存在（P2:172–189），其他目标核或 direct edge COPY 也独立存在。补偿包不能把消费者送回 `b`。窗口公式（C01 §3.4）对固定计算时长 `d`、可行开始区间 `[r,D-d]`、`r+d≤D` 及单槽不可抢占 Pipe 是单操作**必要**重叠；`r,D` 若由错误执行边、遗漏 retained 跨核关系或把 COPY 收缩验证边当执行边导出，就不安全。`fifo_bound.py:78–118` 已明确分开 `D_val/D_exec`；其下界与窗口检查均不能当官方可执行性证明。

4. **“覆盖全部旧紧路径”仅是启发式准入。** 固定时长、固定未编辑约束图中，若一条最长路完整保留，单改其他边无法降低该图最长路；C01 §2.4 自己也限定此命题。真实候选会改 COPY 集合、FIFO 和共享 DDR 时长，未编辑 COPY 的完成也可能变；因此漏覆旧紧路径不能安全判定候选无官方收益，更不能判非法。可用作 8 种子/32 候选预算下的保守筛选，弃用应记为“未搜索”，而非下界拒绝。

**最小动作：**先为一份已有且已核 SHA 的计划取得 prepared 约束快照，核对每个 trace 操作的四门槛与 `s`，包括具体内存边；若出现残差，先停在契约/记录修复，不启动 RCX 评分。然后才用该见证选一个接收闭包做构造与独立 E0 证伪。
