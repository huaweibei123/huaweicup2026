# Singleton 方案的管线依赖下界

本工具用于在官方评价前排除不可能严格改善 Makespan 的候选。它不调用 E0，不生成计划，不证明 COPY、内存容量或整套执行合法性；小下界也不保证好成绩。

## 已证明的适用范围

- 问题3的冻结执行模型，每核合并为一个 Task，每条 Pipe 只有1个执行槽。
- 每个原始非 COPY 操作独占一个子图，所有这些操作使用 `PIPE_M` 或 `PIPE_V`，cycles 是非负整数，实际时长为 `max(1, cycles)`。
- 方案覆盖、图结构和同核原依赖顺序通过既有校验。
- 可计入的计算依赖只有：原始直接计算 op→op 边，或同一原 tensor 的 eligible producer→eligible consumer 边。
- **不能无条件计入 COPY 收缩产生的边。** `Index`/方案校验的收缩图与 P3 `_build_scene_b_tasks` 的建图路径并非同一个定义。如果经过原始 COPY 的收缩新增了上述两类之外的计算依赖，工具直接拒绝，不能把该路径默认为官方跨核 COPY 或加500延迟。正常图输入/图输出 COPY 不在两个 eligible 计算节点之间，本轮12个方案均通过此守卫。
- `cross_core_delay_cycles` 必须来自实际配置，未提供时默认为0，只给无通信延迟的保守下界。当前冻结配置为500，代码没有硬编码500。

超出范围时 `analyze` 抛出 `UnsupportedBound`，而不是输出貌似精确的分数。整数范围之外的定制时长、非singleton子图、原计算搬运管线也不在本证明内。

## 下界及源码依据

令每个原计算节点 `v` 的时长为 `w_v`。建立增强DAG：

1. 保留上述已确认的原计算依赖边。
2. 将每核提交次序投影到每条M/V管线，给相邻计算节点加入FIFO边。
3. 原计算依赖若跨核，边间隔取配置 `d`；同核依赖和FIFO边间隔为0。同一节点对的重复约束取 **max**，不相加。

用动态规划计算

\[
S_v=\max_{u\to v}(S_u+w_u+d_{uv}),\qquad L=\max_v(S_v+w_v).
\]

所有官方成功执行必须满足这些不等式，因此 `L ≤ T_E0`。工具同时返回 `d=0` 和实际配置延迟两个结果、实际最长路操作ID、跨核路径边及按核连续分段。增强图成环时拒绝，不把循环压成有限下界。

冻结源码入口：

- `data/raw/a/official/code/multicore_cut_evaluate_problem_3.py` 的 `_prioritize_task_seq`：按子图顺序排列；singleton 使原计算操作的优先级顺序没有桶内歧义。
- 同文件 `_build_scene_b_tasks`：eligible tensor producer/consumer 与直接 op-op 边跨核时，均生成 source COPY_OUT→target COPY_IN 的 cross link。两端计算依赖保留。即使直接边 `data_size=0`，仍有 cross link；本工具仅使用其配置延迟。
- 同文件 `external_release`：目标 COPY_IN 的释放不得早于源 COPY_OUT 完成加 `d`。源 COPY_OUT 必须在源计算后，目标计算必须在 COPY_IN 后，故原跨核计算边至少有间隔 `d`。
- `schedule_step2.py` 的 `Build seq_ext`：沿原seq逐节点保留并插入spill节点，不重排原操作。
- `schedule_step3.py` 构造 `planned_pipe_orders`：明确固定 `seq_ext` 的逐Pipe投影。新加入的COPY、内存补边和容量等待只会增加限制，不能消除本工具计入的原计算FIFO约束。
- 同文件 `_op_duration` 与 `PIPE_SLOTS=1`：原计算操作时长与单槽互斥规则。

不计 COPY 服务时长、DDR/Cache争用、spill、额外内存依赖；这些不是零成本假设下的实际预测，而是为了保持下界。尤其不能把“DDR COPY_IN 26cycles”当通则，因为P3可能命中Cache。

增强图上的构造和最长路为线性规模；当前实现为了稳定输出对原边排序，耗时 `O(E log E + V + E)`，并复用官方图/方案校验和 `Index`，它们的耗时另计，不能宣称整个入口纯线性。

## 062/5核反例

实测算法提交 `b84e3670452603af1f08169f4dfb5809df8cd31a`，原件在 `results/a/q3-nikolastarx/capacity-20260924/run/`。fragment 方案的计算负载更均衡，但其资源顺序形成更长依赖链。

| 构造 | 仅计算FIFO下界 | 加跨核500下界 | E0 Makespan |
|---|---:|---:|---:|
|balanced|671532|672532|673177|
|fragment|1005144|1007644|1010340|

fragment的无延迟最长路按核分段为 `1→3→4→1→4→2`，各段计算量 `167676, 167436, 251184, 83736, 167484, 167628`。这是原树依赖与管线FIFO边共同串起的长链，不是单条原树祖先路径。即使全部搬运免费，该候选仍超过已经实测的673177，因而可以免E0淘汰。

完整timeline显示fragment核2的M工作537600、M完成前空闲472246、M后尾部494，共1010340。最大M空隙为420024→842422；核4的COPY_OUT在841793完成，核2相应输入在842293释放、842319完成。两方案spill均0、Cache命中均0；跨核新增COPY字节12288→76800不是33.7万cycles退化的主要解释。

## 零评价回读验证

`dependency-audit.json` 对本轮全部12个已完成计划逐一检查计划/结果/图/配置及冻结官方源码的SHA，并从完整结果核对每核M/V原操作序列。12/12均有下界≤E0，全部逐ID管线投影一致。这里是原件读取与数学界检查，**没有新增E0，也不构成独立复跑**。

| 图/核 | balanced 下界/E0 | fragment 下界/E0 |
|---|---:|---:|
|002/3|93192 / 93527|117904 / 119342|
|002/5|84536 / 85129|66248 / 67948|
|062/3|1341812 / 1342199|1181952 / 1183248|
|062/5|672532 / 673177|1007644 / 1010340|
|063/3|399336 / 399671|421360 / 422182|
|063/5|335744 / 336337|338944 / 340898|

10个合成单测覆盖跨管线可重叠、重复边max、tensor/直接边重合、负载均衡仍串行、增强图循环、非singleton拒绝、COPY桥拒绝、正常输入COPY、时长与参数边界。有限测试用于防实现回归，证明依据是前述执行约束。

## 调用方式与使用边界

```python
from src.q3.pipe_bound import analyze, UnsupportedBound
bound = analyze(graph, plan, cross_core_delay_cycles=500)  # 必须对应本次冻结配置
lower = bound["with_cross_core_delay"]["lower_bound_cycles"]
```

```sh
uv run python -m src.q3.pipe_bound GRAPH PLAN --config data/raw/a/official/data/config.txt
uv run python -m unittest tests.q3.test_pipe_bound -v
uv run python -m src.q3.pipe_bound --audit-batch results/a/q3-nikolastarx/capacity-20260924/run/batch.json --config data/raw/a/official/data/config.txt -o NEW_AUDIT.json
```

`-o`拒绝覆盖已有结果。下界大于现有合法方案的E0 Makespan，可拒绝候选；等于时只能说明不能**严格改善Makespan**，不能排除搬运量等次要指标改善。下界较小仍需官方验证，不能据此接受候选。此工具尚未接入在线求解器，也没有因此增加当前实验预算。
