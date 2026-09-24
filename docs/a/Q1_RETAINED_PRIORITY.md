# P1 retained bundle 就绪优先级候选

本候选只把纯 retained 合包的 ready key 改成包内最大单组件的 Pipe 工作；EFT 持续时间仍使用完整 Task 工作。它针对整包优先级压住多波拆分组件的现象，是待评估的机制消融，尚无本候选的官方成绩。

基线固定为 `3c6e41b938c764d207de45584fb526c64f4eb845` 的 `src/q1/component_overload.py`。入口保持该模块，默认行为不变；显式开启：

```sh
python -B src/q1/component_overload.py <graph.json> --cores 5 \
  --retained-component-priority --output <plan.json> --diagnostics <diagnostics.json>
```

Python API：`construct(graph, cores, retained_component_priority=True)`。算法身份为 `q1-component-overload-retained-priority`，variant 为 `retained-largest-component-ready-priority`；不传开关仍为旧 `q1-component-overload-list`。最终计划仍严格只有 `node_to_subgraph` 与 `core_schedules`。

## 唯一行为差异

原算法已确定 COPY 收缩弱组件、超载拆分波、同波装箱、retained 组件装箱。设 Task t 的完整工作权重为

`w(t) = max_p sum_{u∈t, pipe(u)=p} max(1, cycles(u))`。

原优先级为 Task 数据 DAG 的 compute tail：`tail(t)=w(t)+max_{s∈succ(t)} tail(s)`。新候选维持所有这些权重、Task 集和依赖，仅对由完整 retained 弱组件组成的独立 Task 使用

`priority(t) = max_{C contained in t} max_p sum_{u∈C, pipe(u)=p} max(1,cycles(u))`。

其余 Task 仍取 `tail(t)`。优先级仅进入 ready heap；EFT 候选仍是 `start(t,c)+w(t)`，没有用较小的 priority 隐藏整包工作。并列规则继续是 Task ID 与原择核规则。单组件 retained Task 的优先级自然不变；零 cycles 仍按 1 计。

私有 `_place` 参数 `ready_priority_overrides` 只接受数据 DAG 中没有前驱/后继的有效 Task，且优先级为正整数、不大于完整工作。这是防误用检查；调用方通过完整 COPY 收缩组件来提供语义身份，未将任意末端 Task 当 retained。

## 不变量与适用范围

- Task 成员、Task ID、compute 覆盖、mapping 插入序、COPY 收缩及装箱均不变。官方 `multicore_cut_evaluate_problem_1.py:111–159` 的 Task 边界 COPY 只依赖 Task 成员与原图，因此**预 spill 的全部边界 COPY 集与字节不变**。换核和换序仍可能改变 spill、DDR 服务时刻和 Makespan；这里不是总搬运不变证明。
- 每次仍只放置 ready Task，并追加到某核队尾。数据边与 core 序边都沿统一 placement rank 增加，增广 DAG 无环。固定同核 100/跨核 1000 的等待公式未改。
- 后置 `split_large_tasks` 的分块只依赖同一原图、原 Task 成员与 Task ID，故两种 priority 得到相同分块；块链仍替代原核序中的原 Task。诊断中的 placement 时间、tail 与 priority 都在 soft chunk **之前**，不得把它们当分块后的实际时间。
- 原有单核、组件数不足、无可拆超载组件、peel 预算失败等 fallback 条件与计划不变；只有候选身份写入 diagnostics。
- 在已有弱组件工作上增加 O(V) 元数据和 max 聚合；不改变原渐近复杂度，不引入搜索、模拟或在线评价。

## 静态四图对照

来源为 `8f0009ac4a934c2161943b70530e418eb55f9366` 的封存 Task 数据和 `84080acedc0e44fbdebdf7aa4166e8a32003dc80` 的审计。只重算初始 ready key，**没有调用真实图 construct、placement、Task compiler 或 E0/E1/E2**。

|图|角色|最高 split root tail|原来高于它的 retained 包|新优先级下高于它的包|
|---|---|---:|---:|---:|
|031|退化目标|19258|5|0|
|077|退化目标|20602|5|2|
|053|原本改善的对照|82265|5|0|
|087|原本改善的对照|124645|5|0|

这证明规则改变了要检验的排序关系，不预测动态 placement、真实启动时刻或官方收益。053/087 同样会改变排序，必须防止为修复目标而损害已有改善。032/057 的 retained 单组件本身已较长，本规则未必有效；068 是另一末段混合/排序问题，未声称能一并解决。

细项、文件哈希与可复跑脚本位于 `results/a/q1-retained-priority-20260925/`。测试覆盖 priority/duration 分离、共享输入、COPY 桥、后置切块、零 cycles、fallback 和结构校验。未改变冻结官方代码。

## 最小后续验收建议（不是新实验授权）

串行、固定一个候选：先 031/077 五核两格；若两项都未改善，停止，不追加用例。若出现改善，再检查原已改善的 053/087。最多 **4 次真实图 solver + 4 次外部 E0**，不重跑已有旧方案，不进行任何内部选优或参数搜索。可沿用封存 runner 的每格 solver 30 秒 / E0 90 秒超时，最多 480 秒子进程墙钟预算，失败或超时保留原件并停止；这些是建议的实验上限，不是官方时限或完成时间预测。

每格先比对新旧 `node_to_subgraph` 与 Task 边界字节，出现变化即停止机制验收；随后记录首 split 启动时刻、完整 duration 权重、官方 M、spill、总额外 DDR 和求解端到端墙钟。首 split 提前而 M 不改善将否定“改启动优先级已足够”的假设。任何对照退化都保留，不能据这四图建立 case-ID 选择表或宣称全 100/500 改善。
