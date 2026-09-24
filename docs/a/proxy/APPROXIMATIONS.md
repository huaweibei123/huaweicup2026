# E2 两条算法路线：近似、风险与开发池证据

> 状态：Problem 1 的内部研究原型，尚未通过质量或发布验收。`proxy-rank-v0` 输出无量纲排序分数；`proxy-task-event-v0` 输出未校准的 Makespan 估计。两者都不输出官方结果 JSON 或官方 Trace。

## 1. 能力边界

当前实现由 `prepare_graph` 将一张图验证并索引为常驻上下文，再由两条独立路线评分。第一条 `evaluate` 的标识为：

- `interface: internal-e2-v0`
- `engine: proxy-rank-v0`
- `engine_version: 0.1.0`
- `capability: rank_only`
- `numeric_kind: none`
- `checks.execution: unchecked`

第二条 `evaluate_event` 标识为 `engine: proxy-task-event-v0`、`algorithm_direction: coarse_task_event_list_schedule`、`capability: makespan_estimate`、`numeric_kind: estimate`，但仍标记 `checks.execution: unchecked`。

两条路线都只支持 Problem 1。`prepare_graph(problem=2)` 和 `prepare_graph(problem=3)` 均明确抛出 `ProxyUnsupportedError`；没有用 Problem 1 分数冒充其他问题。内部 CLI 通过 `--engine rank|event` 选择路线，必须显式给 graph、plan、config 和输出路径，且写的是内部响应对象，不是官方结果形状。因此官方默认路径、`-o`、结果/Trace/日志字段兼容和公共 `team_eval` 入口均未实现。

## 2. 排序模型

对每个候选方案，原型统计每核各 Pipe 的操作 cycles 之和，并令每个 Task 的静态时长为其 Pipe 负载最大值。它在收缩后的 Task 依赖和同核相邻 Task 之间加入固定等待，计算一条粗粒度依赖下界。另按 Task 边界 COPY_IN/COPY_OUT 语义累计搬运字节。最终分数为

\[
s(P)=\max\{B_{\mathrm{pipe}}(P),B_{\mathrm{dep}}(P)\}
      +\frac{D_{\mathrm{boundary}}(P)}{\mathrm{bandwidth}}.
\]

这里的 `s(P)` 只用于同图、同 Problem、同核数和同配置候选之间升序排序。它没有校准为 cycles，不能与 E0 Makespan 作数值误差计算。

### 2.1 已做的结构检查

- 调用冻结官方 `validate_graph` 检查原图；
- 方案必须恰含 `node_to_subgraph` 与 `core_schedules`；
- 非 COPY 操作必须精确覆盖一次，整数/布尔、重复整数 ID 和额外 ID 会被拒绝；
- 每个子图必须在核心顺序中精确出现一次；
- 收缩后的子图依赖必须无环，同核依赖顺序必须一致；
- 调用官方 `validate_task_order` 做已能构造的 Task 顺序检查；
- batch 请求先检查非空且唯一的 `request_id`，单个方案失败返回对应的 `invalid`、`unsupported` 或 `error`，设计上不应终止后续请求。

这些检查不等于完整执行可行性。成功响应仍明确标记 `execution: unchecked`。

## 3. 第二路线：粗粒度 Task 事件模型

`proxy-task-event-v0` 不再把每核 Pipe 负载压成一个总上界。它先在每个 Task 内按依赖拓扑顺序，对各官方 Pipe 做单槽确定性 list schedule，其中每个原始操作按 `max(1, cycles)` 计时；再把每个边界 COPY 按 `max(1, ceil(size / bandwidth))` 独立取整，并将输入 COPY、Task 内计算、输出 COPY 顺序合成为 Task 时长。这样合法的零周期操作和零字节边界 COPY 都与官方 Step3 一样至少占 1 cycle。最后沿 Task 依赖和同核 Task 顺序传播完成事件，同核/跨核边分别使用冻结 config 的固定等待。

这与第一路线的“聚合 Pipe 上界 + 全局搬运罚项”是算法上的不同方向，不是同一内核的语言翻译。它能在 FORM PR #17 的排序反例上区分相同搬运统计的两个方案，并与官方开发观测同样得到 1052 与 152 cycles；但这只证明该微型等待语义被表达，不能证明一般精度。

该路线仍省略 Step2 spill、完整 Step3 execution graph、memory reuse 边、COPY/计算重叠和共享 DDR 争用。FORM 最终交接还明确指出 Pipe 队首等待时能否越过尚无探针，本路线也不声称模拟该行为。其 Makespan 是数值估计，不是官方 cycles。固定风险标签包括 `spill_unmodeled`、`step3_approximated_by_local_list_schedule`、`pipe_head_blocking_unmodeled`、`copy_compute_overlap_unmodeled`、`ddr_contention_unmodeled` 和 `uncalibrated_makespan_estimate`。

## 4. 近似点与失效机制

| 近似/省略 | 为什么更快 | 可能偏差或失败 | 当前检测与处置 |
| --- | --- | --- | --- |
| 用每核 Pipe 累计负载取最大值 | 不执行逐周期/逐事件调度 | 忽略 Pipe FIFO、就绪时间、Task 内关键路径和并行重叠 | 固定 `step3_order_ignored`、`execution_unchecked`；发布前交 E1/E0 |
| Task 时长取 Task 内最大 Pipe 负载 | 避免 Step1--3 展开 | 排序、spill 和内存依赖可能改变时长与合法性 | 固定 `spill_unmodeled`；容量风险时不应强剪枝 |
| 粗粒度 Task 依赖加同/跨核固定等待 | 只在 Task DAG 上做一次拓扑动态规划 | 多前驱、同刻事件及真实 ready/issue/retire 次序被压缩 | 分数不命名为 Makespan；完整结果交 E0 |
| 边界搬运量除以标称带宽 | 避免共享 DDR 事件模拟 | 忽略传输重叠、争用、取整和最短 1 cycle | 固定 `ddr_contention_aggregated` |
| 按 Task 边界累计 COPY_IN/COPY_OUT | 不构造完整局部 Task 图 | 能反映搬运量，但不反映 COPY 的实际发射/完成时序 | 有跨 Task tensor 时加 `task_boundary_copy_timing_aggregated` |
| 不运行 Step2 spill | 避免扩展图和反复 reload | 容量临界方案可能被系统性乐观估计 | 静态工作集超 capacity 时加 `capacity_pressure` |
| 不生成 Step3 memory reuse 边 | 避免虚拟字节额度和 WAR/WAW 构图 | 可能漏执行环、队首阻塞与内存峰值 | `execution_unchecked`；不得据 `status: ok` 声称官方可行 |
| 不模拟 Problem 3 Cache | 保持首版范围很小 | 无法估计 hit/miss、共享池争用或题三 Makespan | Problem 3 明确 `unsupported` |
| 未做分数校准 | 不训练/拟合数值模型 | 无法满足中位数 1%、P95 3% 的 Makespan 误差门槛 | 固定 `uncalibrated_rank_score`，`numeric_kind: none` |

附加风险标签包括：空核 `empty_core`、非零核负载最大值相对均值超过 1.5 的 `high_core_imbalance`，以及上述容量和边界搬运风险。标签只提示风险，不是校准概率，也不能单独证明无风险方案正确。

## 5. 单图 64 候选开发池

证据目录为 `results/a/proxy/r20260923-e2-dev64-gzip/`。输入是 `case_001.json`、Problem 1、4 核、同一官方 config；图 SHA-256 为 `a634cd1151c0e918dd3a143eba421b88907f7f0334bfe6a5ca0412342307f09f`。候选由官方 stub 在四组子图尺度 25、50、100、200 上按固定 seed 生成。64 次尝试均得到唯一成功候选，且 64 个成员全部保存 E0 真值。

每份 E0 full JSON 使用 `compresslevel=9`、空文件名和 `mtime=0` 的确定性 gzip 保存。`candidates.csv` 同时记录压缩文件 SHA-256 与未压缩官方 JSON 字节 SHA-256；64 份压缩结果共 2,694,701 bytes。生成后逐份解压，并核对未压缩 hash 与记录的 Makespan。旧的未压缩开发目录不作为提交证据。

短名单大小按 `min(n, max(8, ceil(0.1*n)))` 取 8。

| 指标 | 开发池观察值 | 解释 |
| --- | ---: | --- |
| 候选数 / 有 E0 真值 | 64 / 64 | 没有只标注入选者 |
| 全池最佳 E0 Makespan | 228471 cycles | 官方函数层真值 |
| 短名单最佳 E0 Makespan | 228471 cycles | 此池保留了全池最佳 |
| 短名单遗憾 | 0 | 仅此开发池 |
| 保留距最佳 1% 内候选 | 是 | 仅此开发池 |
| 同池 Spearman | 0.8567765568 | 排序诊断，不是数值精度 |
| E2 评分累计时间 | 0.3559557 s | 常驻图上下文、内存内直调 |
| E0 full 累计时间 | 28.7685327 s | 内存内官方函数直调 |
| 观察到的 E0/E2 比 | 80.8205x | 不是 E2/E1，也不是完整 CLI/端到端速度 |
| `quality_gate_passed` | `false` | 单图开发池，不是校准或封存验收 |

80.82 倍只比较“已准备同一图后的内部 E2 分数”和“E0 full 函数结果”。它排除了图准备、方案生成、gzip/文件 I/O、完整官方输出、E1 短名单、E0 最终确认和调度开销；也没有按补充规范与已通过一致性范围的 E1 做同池配对。因此不能声称已达到 `>=10x E1` 联合门槛，更不能用本数字推算 E2/E1。

`proxy-rank-v0` 没有输出 E2 Makespan，所以它的校准误差中位数、P95、最大误差和超过 3% 比例均 **不可计算**。短名单结果来自开发时检查过的同一个池，不能代替至少 12 个独立池或图级封存集。

### 5.1 两路线同池复跑

`results/a/proxy/r20260923-e2-route-compare/summary.json` 在读取 64 个计划和确定性 gzip E0 真值后，逐一复核计划、压缩文件和解压 JSON 的 SHA-256，再对两条路线各预热 1 次、完整池重复 3 次。该复跑没有重新执行 E0；下表中的 E0/路线比使用开发池已记录的 E0 总时间，只是辅助观察，仍不是 E2/E1。

| 路线 | 池时间中位数 / s | Spearman | 短名单遗憾 | 数值误差中位数 | 数值误差 P95 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `proxy-rank-v0` | 0.3385 | 0.8568 | 0 | 不可计算 | 不可计算 | 排序基线；无 Makespan |
| `proxy-task-event-v0` | 0.3438 | 0.8127 | 0 | **25.7591%** | **28.8954%** | 64/64 均超过 3%，数值门槛失败 |

事件路线最大相对误差为 30.6974%，`numeric_gate_passed=false`。两条路线都在这个已看过的单图开发池中保留了距最佳 1% 内候选；这不能抵消事件路线的数值失败，也不能代替独立多图封存验证。

## 6. FORM 回归与原生小内核

`tests/eval_proxy/test_form_regressions.py` 固定吸收 FORM PR #17 最终交接 `dab91d612bd26183e12d30848b13d5fb14e071c7` 提供的开发候选证据，而不合并或自签该 PR：合法空 core；字符串键 `"02"` / `"2"` 归一化后的重复 ID；`1 -> 2 -> 3` 且 1/3 合组产生的 quotient cycle；以及上述 1052/152 排序反例。排序夹具 Git blob 在此前采用版本与最终固定版本间相同。连同 pool 身份、零周期下限及 FORM 量词勘误回归，本机 `tests/eval_proxy` 为 16/16 通过。

`src/eval_proxy/native/` 另把一个固定点 feature/ranking 小内核以 Python、C++17、Rust 三份源码表达。保存的 512 候选实验中，MSVC 19.35 编译运行成功，C++ 与 Python 的完整 31,387-byte stdout 相同，SHA-256 均为 `30b2a06e4fde37cb43f5feb59e7e0735049e2c610e35eb09fd5238a5e25f3186`；11 次进程级中位数分别为 39.4891 ms 与 256.8738 ms。独立复跑再次得到同一输出 hash。Rust 源码已交付，但本机 `rustc`、`cargo` 均不在 PATH，所以没有编译或运行，不能写成 C++/Rust 双路线实测完成。

这个原生实验只比较合成小内核的解析、排序和序列化，不读官方 graph/plan，不证明 E2/E0 精度，也不代表完整 E2 加速。

## 7. 复现

输出目录必须预先不存在：

```powershell
uv run python -m src.eval_proxy.dev_pool `
  --graph data/raw/a/official/data/case_001.json `
  --config data/raw/a/official/data/config.txt `
  --output-dir results/a/proxy/<new-run-id> `
  --count 64 --cores 4 --scales 25 50 100 200 `
  --max-attempts 1280
```

对单个方案运行内部排序接口：

```powershell
uv run python -m src.eval_proxy.cli `
  data/raw/a/official/data/case_001.json `
  results/a/proxy/r20260923-e2-dev64-gzip/plans/candidate-000.plan.json `
  --problem 1 `
  --config data/raw/a/official/data/config.txt `
  --output results/a/proxy/<cli-run-id>/candidate-000.proxy.json
```

第二路线在相同命令中增加 `--engine event`。同池复跑命令为：

```powershell
uv run python -m src.eval_proxy.compare_routes `
  --graph data/raw/a/official/data/case_001.json `
  --config data/raw/a/official/data/config.txt `
  --pool-dir results/a/proxy/r20260923-e2-dev64-gzip `
  --output results/a/proxy/<new-route-run>/summary.json `
  --warmup 1 --repeats 3
```

原生小内核需先加载 Visual Studio developer 环境；完整命令见 `src/eval_proxy/native/README.md`。

## 8. 回退原则与未验收项

E2 v0 自身不执行隐式回退。搜索器应保留当前 E0 最优、代理优选、结构多样候选和随机审计样本；遇到容量压力、执行合法性未知或当前不支持的 Problem 2/3，应交 E1/E0，而不是把候选判为 invalid 或静默删除。任何回退时间都必须计入混合流程成本。

仍缺少：

- 校准 Makespan 模式及中位数 `<=1%`、P95 `<=3%` 的数值误差证据；
- 与 E1 在同提交、同池、同配置和同资源下的 `>=10x` 配对吞吐测试；
- 图级开发/校准/封存分离、多图、多核、Problem 2/3 和最差池报告；
- 批量 1/16/64/256 的 P50/P95、冷启动、完整 CLI、内存峰值和混合流程总成本；
- FORM 四个开发回归已加入，但完整公开对抗集、执行环、Step2/3、spill、共享 DDR/Cache 与同刻事件压力矩阵仍缺；
- C++ 小内核已实跑且 byte-equal；Rust 因工具链不可用未运行，且原生实验尚未接官方 I/O；
- 第二算法路线已经实现和实跑，但 25.76%/28.90% 的误差明显未过 1%/3% 门槛；
- 官方形状的完整结果、Trace/日志兼容与独立队长验收。

在这些缺口关闭前，E2 v0 只能作为排序研究基线，不能作为官方成绩、执行可行性证明或“高速低误差”最终交付。
