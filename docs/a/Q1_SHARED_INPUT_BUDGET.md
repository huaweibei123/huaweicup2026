# P1：共享输入代价选择有效核数，再细分 Task

实现：`src/q1/shared_input_budget.py`。这是独立候选，不与 heavy-suffix 混成 portfolio；固定读取 161cdb35 源线的 bounded/component-pack 机制。合成契约测试通过，首批044/046/090五核官方原件已归档；没有本方法全100成绩。

## 为什么做

静态审计入口：`results/a/q1-input-structure-20260924/README.md`。044/046/090 的均衡组件各自读取相同的大权重集合，但计算/搬运比例不同。所有核都用上会重复读取权重；只减少 Task 内 spill 不能消除跨 Task 权重副本。审计中的简单代理偏向 2/4/5 个有效核，但本实现不使用这些 case ID 或硬编码选择。

同时参考 Fang 固定提交 `617f7fab5baca3889b08f8e712eaabf1d1238b53` 的 `results/a/q1-yuanzhifang/stage-c-analysis-20260924/README.md`：051 输入按 Task 重复，008 内部边界搬运显著增加，071 的 local_makespan 并非全局实际 duration 下界。本方法不使用 local_makespan，不把任何差额单独解释为 DDR 竞争。

## 构造

1. 校验原图；用官方 COPY 收缩邻接求弱组件、拓扑深度、外部输入使用关系。原计算节点 ID、原 op 插入顺序、原图与配置均保留。
2. 若独立组件少于请求核数 K，或者全图外部输入并集不超过 activation（默认 524288 bytes），调用一次原 bounded(graph,K) 回退。这只是机制激活条件，不表示其他图没有优化空间。
3. 对 `a=1..K`（K≤5）计算静态装箱/输入集合元数据。装箱的工作优先级和 tie-break 与冻结 component_pack 一致，尺寸超过 4096 ops 的块按 bounded 的独立组件 first-fit 软分成 1024 ops 块；不可分的大组件继续保留。这里没有调用 constructor、derive、Step1/2/3 或 evaluator，也没有生成 K 份提交文件。所有元数据计算仍是在线求解成本。
4. 每个候选块独立按深度切窗：新增输入使当前 union 超过 262144 bytes 时切开。单层超预算如实保留；若某块超过 32 窗，则只让该块回退为一个完整块。不会与其他块合并。
5. 用下述静态成本选 a，仅调用一次 **bounded(graph,a)**。保留的是“所选 a 的 bounded 编译边界”，并非原 K 核方案的全部 Task 边界；后者会保留原先的权重副本，使少核收益消失。
6. 独立细分这份基底的每个 Task，保留其原 core 顺序位置；第一个窗口沿用原 Task ID，其余取得新 ID。即使 a=1 也执行本方法的局部窗口逻辑，不调用旧 input_windows 的单核提前回退。最终扩为 K 条 `core_schedules`，未启用核留空，输出仅有官方两个字段。
7. 官方 derive/Task-order 检查最终输出；检查候选元数据 Task 数与真实构造一致，以及新增依赖均保持在完整组件所属核内。无在线评分和质量选优回退保证。

## 代价模型及其边界

对每个静态配置，Task 指该配置预期 bounded 块进一步细分得到的窗口。`external` 是没有直接计算生产者的 tensor 集合，是边界统计定义，不等于只有权重。

- **输入复制**：每个 Task 的外部输入集合各计一次，包括同核不同 Task；不是按 core 并集计一次。`input_repeat_proxy_bytes = ΣTask |inputs(Task)| − |global external|`。
- **内部边界**：对每个 tensor 统计生产者/消费者所在元数据 Task。无本地生产者的消费者 Task 加一次 COPY_IN；生产者 Task 若有外部消费者、原 COPY_OUT 或没有计算消费者，则加一次 COPY_OUT。保留所有不同目标 Task 的读取数，高扇出不简化成固定 `2×payload`。`cut_tensor_payload_bytes_once` 仅用于诊断，绝不直接代替边界复制量。
- **原图/分区差额**：按原 COPY_IN 输出、COPY_OUT 输入统计原图字节；静态新边界字节减去原图字节得到 `partition_added_copy_proxy_bytes`。这不包含 Step2 之后的 spill/backing/incarnation 改写。统计没有执行官方 Task 编译链，因此仍称代理。
- **DDR 服务**：对每一预期 COPY 使用 `max(1,ceil(size/60))` 后求和，保留逐 COPY 取整；不能改成只对总 bytes 做一次 ceil。
- **计算与 gates**：每个 Task 取 `max_pipe Σop max(1,cycles)`，然后按 core 把其 Task 项求和，加入 `100×max(Task_count−1,0)`。不能先对全核 Pipe 总量取 max，后者会漏掉分窗拆开互补 Pipe 的损失。当前路由保持整组件同核，故无真实跨核依赖等待；读取并报告官方 1000-cycle 配置但不将其错误累加到无跨核边的方案中。

最终成本为 `max(最大逐核计算+gate项, DDR服务项)`；相同时偏好较少静态 COPY bytes，再偏好较多有效核。固定带宽与 gate 从官方 config.txt 读取；容量阈值是本方法公开的启发式参数，不修改官方容量。

**这些项不是一般 Makespan 下界、不是 E0 预测，也不是零 spill 证书。** 仍遗漏细粒度依赖、容量/UB峰值、spill重载、FIFO、时序重叠与启动/收尾效应。减少输入副本可能把私有输入和内部状态集中到少量 Task，反而加剧 spill。single-layer 超预算和阶段数回退都会进入 diagnostics。代理最小与真实结果最优不能等同。

## 无环证明

各完整弱组件之间无计算边，所以选 a 后的组件装箱及组件块 core 顺序构成合法基底。把一个旧 Task 替换成同核链，链顺序按递增深度窗口；原图 Task 内依赖只会前向，跨旧 Task 依赖及 core 序仍保持旧块序。新图若有环，缩回旧 Task 后要么成为旧增广 DAG 的有向环，要么完全位于一条前向链内，两者均不可能。因此细化保留无环；该证明不涵盖内存可行性或性能。

## 复杂度与实现效率限制

N/E/F/C 分别为节点、收缩边、外部输入关联数、组件数。图视图/深度近 O(N+E+F)，排序 O(C log C)。最多 K 个元数据配置，装箱逐核比较带 O(K² C) 项，每配置窗口和 tensor 使用统计近 O(N log N+E+F)。冻结 bounded 的 first-fit 块处理最坏有 O(C²) 项，本实现元数据也继承它；不能把整套算法宣称严格线性。官方邻接/收缩、最后一次 bounded/derive 验证另计。

每次仅保留当前配置的块/窗口元数据，配置摘要为 O(K²) 级核统计（Task IDs 不枚举为提交计划），图和临时归属字典主要 O(N+E+F)。首批三格端到端solver为75–79毫秒，包含读取输入、在线元数据、构造/验证与落盘，外部E0为0.131–0.241秒，单列记录；非独占本机计时不等于受控速度比较。

## 合成验证与待测范围

`uv run python -B -m unittest tests.q1.test_shared_input_budget -v`

10 项合成测试涵盖：带宽主导选单核并继续切窗、计算主导保留多核、K 条输出与插入顺序、基底 Task 不重合并、4096/1024 软块中按 Task 重复读取、阶段上限/超预算、回退仅一次 bounded、COPY 收缩组件、非法参数、逐 COPY 取整、不同窗口的互补 Pipe、内部高扇出，以及 CLI 输出契约/拒绝覆盖。其中多个行为在同一项测试核对。没有运行真实 case 或任何 evaluator；测试确实调用了合成图 constructor，不能将本次全部软件构造次数写成零。

初次预声明批次044/046/090 K5已按父会话授权完成，实际3solver+3外部E0，无重试或旧基线重跑。固定算法288dd520caa5c7baaa1413e4021eb2d4221b6e66；三格Makespan分别从132892/131039/542638降到64624/103846/319844，额外DDR同步下降、spill均为0，实际活跃核2/4/5。完整证据与范围见`results/a/q1-input-structure-20260924/SUMMARY.md`；这些选定机制样本不证明一般spill证书、最优性或全100效果。代理与实测仍明显不同，应以diagnostics和原E0如实报告。

构造命令模板（执行实验必须另设固定批次和预算，不覆盖既有结果）：

```sh
uv run python -B src/q1/shared_input_budget.py INPUT_GRAPH --cores 5 --output RUN/plan.json --diagnostics RUN/diagnostics.json
```
