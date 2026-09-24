# P2 固定计算 FIFO 的候选下界

2026-09-25，`nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894` 的有界理论子任务。

实现：[fifo_bound.py](../../../src/q2_nikolastarx/fifo_bound.py)；验证：[test_fifo_bound.py](../../../tests/q2_nikolastarx/test_fifo_bound.py)。本模块未接入任何求解路由，本轮 **0 solver / E0 / E1 / E2 调用**。只运行合成静态测试、读取既有方案与官方结果。

## 结论与接口

`fixed_fifo_lower_bound(graph, plan)` 返回当前 **singleton 方案固定分核、固定计算 FIFO** 的必要 Makespan 下界。`supported=True` 表示下面的静态条件与重建证明适用；**不表示官方完整合法、零 spill、零死锁或全局最优**。结论以该方案在冻结 P2 语义下成功执行为条件。输出包括：

- `makespan_lower_bound_cycles`、已有 assigned-pipe work 下界及两者差值；
- 每 `(core, pipe)` 的计算周期总量；
- 可加和核验的关键路径，节点的 core/pipe/周期与每条边的理由；
- `reconstruction_guard`：singleton、每原 tensor 至多一个 eligible producer、两种依赖边计数、被排除的 COPY 收缩边与合并图无环性；
- `official_execution_validated=False`。不支持时返回原因码，数值为 `None`，调用者须回退，不能当作无穷大下界。

不支持范围包括非 singleton 方案、多 eligible producer tensor、图/方案结构错误及 `D_exec + FIFO` 有环。后者这里只报告无有限 DAG 证书，不假装已完成官方展开图审查。原图必须通过冻结输入验证器，此外要求 `op` 类型名为字符串。允许周期为 0 的计算，时长统一为 `max(1, cycles)`；非 COPY 的 MTE 操作也按所属 Pipe 处理。

## 数学对象：D_val 不能直接充当 D_exec

令 `V` 是所有非 `COPY_IN/COPY_OUT` 的原始操作，`d(v)=max(1,cycles(v))`。复用 `DAGIndex`，但严格区分：

1. **`D_val`**：`DAGIndex.pred/succ`，即方案验证器穿过被删除原 COPY 操作收缩得到的依赖。只用于结构验证与诊断。
2. **`D_exec`**：只含两个 eligible 端点之间的原始直接 op→op 边，及原 tensor 的 eligible producer→eligible consumer 边。这里不穿过原 COPY 操作。
3. **`F`**：把每核提交的 singleton 顺序投影到各 Pipe，仅在相邻计算操作间加边。同核不同 Pipe 的先后优先级不是执行串行边。

构造 `H=(V,D_exec∪F)`，若为 DAG，取加权最长路

\[
L=\max_{v\in V}\left[d(v)+\max_{u\in pred_H(v)}L(u)\right],
\]

空集合取 0。任何适用的官方执行都满足 `Makespan≥L`。每个 `(core,pipe)` 上的全部计算串成路径，因此 `L≥max_{core,pipe} work(core,pipe)`，不会弱于既有 assigned-pipe work 下界。

**必要反例。** 原图只有 `A(PIPE_M,10) → COPY_OUT → B(PIPE_V,10)` 三个操作、没有 tensor。同核 singleton 顺序 A,B 通过 `D_val` 的先后检查，但 P2 重建时直接丢掉两条含原 COPY 端点的边，A/B 没有计算依赖。`D_val` 的 20 周期路径不能作官方执行下界；本模块返回 10。该反例是冻结源码推出的合成语义 fixture，未调用 E0，不是正式 case 成绩。

## 重建证明与适用边界

**固定计算 FIFO 保留。** singleton 使每个 eligible 操作拥有唯一子图 rank。P2 `_prioritize_task_seq` 按该 rank 对 Step1 序列稳定排序；Step2 插入 COPY 而不改变原操作的相对顺序；Step3 使用展开序列的 per-pipe 投影；最终多核事件器只放行每条 Pipe 当前队首，完成后才推进。故 `F` 中的每条边都是实际先完成、后开始的约束。不能把此推论推广到同一子图含多个计算的方案，也不能把完整跨 Pipe 优先级顺序全加成串行边。

**计算数据依赖保留。** 对每条 `D_exec` 边：

- 原始直接边同核保留，跨核则构造 `producer → COPY_OUT → external release → COPY_IN → consumer`。
- 单 eligible producer tensor 同核保留 producer→tensor→consumer。若 Step2 spill，producer→第一次写 DDR backing→后续 reload→consumer 仍构成依赖链；重用 backing 不等于重新绕过原 producer。
- 该 tensor 跨核时，各目标核只有初始跨核 COPY_IN 作为本地生产入口。它依赖源 producer 的 COPY_OUT。后续 reload 即使重用已有 DDR backing，初始 COPY_IN 仍先于 reload 出现在展开序列的固定 MTE2 FIFO 中，因而保留源 producer→consumer 的先后关系。

“每原 tensor 至多一个 eligible producer”是保守的重建证明域；它排除同一目标 tensor 同时有本地计算 producer 和多个异地 COPY 生产者时的 incarnation/backing 歧义。这里只做条件外拒绝，没有宣称全部多生产者图都错误。原 COPY 生产者本身不计为 eligible producer。

Step3 内存依赖、插入 COPY、共享 DDR 带宽及跨核延迟只能在上述保留计算约束之外增加等待。本模块不将这些资源的时长加进 `L`，不把 Step3 的本地 Makespan 当作最终 P2 下界。冻结配置中每 Pipe 容量为 1；所有保留计算时长均为整数。最终事件器的计算结束时间是 `now+max(1,cycles)`；这里不使用 DDR 浮点服务量或其 `ceil(...-1e-9)` 作为时长证据。

归纳沿 `H` 任一拓扑序：实际 `end(v)≥d(v)+max end(pred_H(v))≥L(v)`，取最大即得。证明为**必要条件**，不构造可执行时间表。无环与单生产者检查不能覆盖容量、COPY FIFO 或新增 memory edges 的全局合法性。

### 冻结源码入口

- `stub_multicore_cut_and_schedule.py:20–89,114–243`：原邻接、COPY 收缩、exact coverage、同核依赖顺序检查。
- `multicore_cut_evaluate_problem_2.py:43–59,68–86,133–231,245–268`：rank 排序、计算保留、tensor/直接边重建、Step2/3 接续。
- `schedule_step2.py:304–341,407–480`：DDR backing、incarnation 消费者改接、展开序列保留原操作顺序。
- `schedule_step3.py:28–31,76–85,279–289,595–608`：每 Pipe 单槽、计算时长、固定 FIFO、额外内存依赖。
- `multicore_cut_evaluate_problem_2.py:374–412,465–477,574`：跨核 release、FIFO 队首、计算时长、最终 Makespan。

这些行号相对 `data/raw/a/official/code/`。源码 SHA-256 固定如下；若换评价器，必须重新审计而不能沿用本证明。

| 文件 | SHA-256 |
|---|---|
| `stub_multicore_cut_and_schedule.py` | `0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892` |
| `multicore_cut_evaluate_problem_1.py` | `2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f` |
| `multicore_cut_evaluate_problem_2.py` | `0b39f84d5ec0a7fba9a4c92a598a9044b97ab79c71393824c1ba130ecfe6c464` |
| `schedule_step2.py` | `2836baac176f4e0bdd9eec59b8d9ce254e209e5f7a251e23837ab684312fa0c3` |
| `schedule_step3.py` | `50053db0436f1d166dd75436693ba3af49b5c339576beb6e7299477f6b69fc7a` |
| `evaluation_validation.py` | `103206b8c5c25e37de50cc3193de3989d7c1e01d4a11cc5f509dedd8f9be9a64` |

## 已归档六个结果的静态核对

原输入为 `data/raw/a/official/data/case_{016,062}.json`。读取既有
`results/a/q2-nikolastarx/{vector,tree}-pilot-20260924/run/{case}-k{k}/plan.json`
及相邻 `final/result.json.gz`。**没有重新执行官方评估**。六份方案均通过本证书域，均没有 COPY-only 收缩额外边；每条关键路径周期和等于 L，work 值与既有 `assigned_pipe_lower_bound` 完全一致，且 `work≤L≤归档 E0 Makespan`。

| 候选 | assigned work | FIFO L | L 比 work 提高 | 归档 E0 Makespan | E0−L | L/E0 |
|---|---:|---:|---:|---:|---:|---:|
| vector 016 k2 | 3,859,470 | 3,863,435 | 3,965 / 0.103% | 4,170,750 | 307,315 | 92.632% |
| vector 016 k4 | 1,933,700 | 1,937,665 | 3,965 / 0.205% | 2,552,270 | 614,605 | 75.919% |
| vector 016 k5 | 1,937,665 | 1,937,665 | 0 / 0% | 2,243,707 | 306,042 | 86.360% |
| tree 062 k2 | 1,388,400 | 1,513,704 | 125,304 / 9.025% | 1,514,488 | 784 | 99.948% |
| tree 062 k4 | 774,000 | 1,005,132 | 231,132 / 29.862% | 1,008,337 | 3,205 | 99.682% |
| tree 062 k5 | 614,400 | 670,344 | 55,944 / 9.105% | 673,563 | 3,219 | 99.522% |

这是一项有用的研究停止判断：062 若维持当前分核和每 Pipe 计算 FIFO，只改变 M/V 的交织优先级或 COPY 行为，即使完全去掉额外等待，最多分别省 784 / 3,205 / 3,219 周期。要进一步大幅降低 Makespan，必须改分核或至少一个计算 FIFO。它**不**证明 062 当前全局最优；其他计算 FIFO/切分仍有空间。

016 纯 V 没有保持计算 FIFO 仍可调整的 M/V 交织自由度。证书与 E0 的差值提示当前原计算图之外存在等待，但不能仅据该差值断言全由固定 500-cycle 通信延迟造成，仍需从已有 timeline 追因。尤其 k4 零 spill 并不消除其 614,605 周期差值。

函数调用用时单次为 0.34–0.62 秒（既有本机 Python 3.14 环境，模块预先导入，输入 JSON 已读入，包含本函数内索引和结构验证）；这是静态调用观察，不是端到端求解耗时或性能承诺。最长路新增部分复杂度 `O(|V| log |V|+|E_exec|+|F|)`、空间 `O(|V|+|E_exec|+|F|)`；复用 `DAGIndex` 与官方 `derive_multicore_plan` 的 COPY 收缩和排序检查可能更贵，不能把新增 DP 的复杂度冒充整个入口的最坏复杂度。

### 输入与归档身份

图 SHA-256：016=`76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef`；062=`fa99943eab55b174047687337a4bcd81c3967e052e22eaabf3fb7740914df2b4`。

| cell | `plan.json` SHA-256 | `result.json.gz` SHA-256 |
|---|---|---|
| 016 k2 | `009338de55db3bbe3c89696400573d4a7e44d6999a333bee43f080c753fcc53b` | `6e24f290a23bd006910e4c9a9203d704861544b1d019a6dbc1e8f4644164ec37` |
| 016 k4 | `57563e380c32663f73afea7a0228e57d09431468b767b8b112c3eb0bd721d83f` | `9d4e8fb51f95dd605006c7e7c77cc8ed2a5bbded6f6664b115bab60346e796dd` |
| 016 k5 | `a193acb4bee1e82a7e133e67272bbbe7566a6b3c6db6d7f6de7800af3365baa1` | `594aca5a151e4034e84d257440d48824a145f6bea3b21e860047abdceeee178e` |
| 062 k2 | `487bad5bd9686c21f03884cb7e418bca2874a7f45bda3ac0993a6c2b0a3ed9c0` | `a4d91b864c171a661d867665b8fe429b682bfd914829d9a7109e0db4fda77aee` |
| 062 k4 | `20c84ec5b47b1fc64f44e99ec503c149853763d1c0d9cecb419c55b263179e76` | `9e6030bbd1e37b5510df646b725e955ea05de51cbd7839c58317cd190c3c7e3b` |
| 062 k5 | `269447a8dad413aad6bd1b79314511064a640eeed337d4c3c94e383dda46ce40` | `490381208f20cbaa2d81456a659f629724f752706f5500253d6bde0285fb15ad` |

## 测试与潜在接入条件

执行 `uv run --no-sync python -m unittest tests.q2_nikolastarx.test_fifo_bound -v`，13 tests 通过。覆盖跨核 tensor/直接边、不同 Pipe 优先级不串行化、相同分核不同 FIFO、删除 COPY 反例、多生产者/非 singleton 拒绝、原 COPY 与单个 eligible producer 并存、图输入没有计算 producer、跨核 FIFO 环、输入异常、0 周期、MTE 非 COPY 计算、空图、确定性 witness 与不修改输入；另独立枚举 3 个操作、每个 start 在 0–8 的 729 个整数时间组合，检查下界不超过任何可行放置的 Makespan。该微型枚举不是求解器或正式 case 实验。

独立只读审查未发现阻塞性正确性问题，并特别复核了“跨核初始 COPY_IN 与 reload 的固定 MTE2 FIFO”桥接条件。静态测试本身不构成 COPY 重建实测；此处依赖的是上述冻结源码论证和适用域，六份归档结果的数值符合只是一项一致性检查。

根会话决定是否接入。若候选只接受**严格更小 Makespan**，且已有 E0 确认的 incumbent 为 B，则有证书 `L≥B` 可跳过该候选的评分；`unsupported` 必须继续既有流程。若未来允许同 Makespan、更低 DDR 或其他 Pareto 目标，等号不能直接剪除；只凭本界也不能剪掉尚未确定计算 FIFO 的整个分核或搜索分支。实现与静态证书没有改动现有 solver、评分次数或实验矩阵。
