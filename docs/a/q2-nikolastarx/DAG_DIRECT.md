# P2：按 tensor 通信和就绪路径直接分核

本构造的目的，是打破“整个弱连通组件只能放在一个核上”的限制，同时保持一次构造、零在线评价。它是独立的确定性启发式候选，尚不证明优于 Fang，也不证明接近全局最优。正式方案质量必须由冻结 E0 另行测量。

## 接口和来源

实现 `src/q2_nikolastarx/dag_direct.py`：

```python
from src.q2_nikolastarx.dag_direct import build
plan, detail = build(graph, cores, {
    "bandwidth": 60,
    "cross_core_copy_delay_cycles": 500,
    "capacity": {"L1": 524288, "UB": 131072},
})
```

这里的常数展示冻结配置内容；调用方应使用官方 `read_evaluation_config` 和 `read_scene_b_config` 读取实际配置，不以这些数值覆盖配置。接口要求两个实际使用的键存在，无静默默认。`capacity` 目前不进入预测模型，所以不能把接口接收它说成容量约束已验证。

独立直接 CLI（仅构造和官方结构检查，不调用 E0）：

```sh
.venv/bin/python -B -m src.q2_nikolastarx.dag_direct \
  data/raw/a/official/data/case_071.json --cores 4 \
  --config data/raw/a/official/data/config.txt --output /tmp/dag071.json
```

生成文件严格只有 `node_to_subgraph`、`core_schedules`。标准输出包含路由、预测量和从读取输入/配置到方案写入的计时；这个内部计时不含解释器启动和 import，方案成绩台必须使用 runner 的进程外端到端墙钟。输出文件已存在时拒绝覆盖。

复用 `direct.Index` 的冻结结构读取及拓扑接口（本分支来源 `affd4e67`）；组件/pipe 实现的历史归属继续见 `direct.py` 和 `FEEDBACK_METHOD.md`。新分核策略没有复制 Fang 的 packet 分核代码，也没有把 Pro 的理想模型结论作为一般 DAG 证明。语义依据为未修改的 `multicore_cut_evaluate_problem_2.py::_build_scene_b_tasks`、`_prioritize_task_seq`、`schedule_step3.py::_op_duration` 和结构入口 `derive_multicore_plan`。

## 一次构造的规则

1. 由真实 tensor 边和直接 op-op 边得到 eligible op DAG；排除原始 COPY 节点时仍保留原先结构函数收缩出的前后依赖。逆拓扑计算每个 op 的剩余最长计算路径。这里只累计原始 cycles（至少 1），不夹入任意通信权重。
2. ready heap 每次选择 `(-剩余计算路径, op ID)` 最小者。每个 op 只分派一次，不做参数网格、随机重启、候选枚举或局部回滚。
3. 对每个核预测该 op 完成时刻：考虑其已分派前驱、四条 pipe 的尾时刻，以及输入 tensor 的必要 COPY。孤立 COPY 耗时为 `max(1, ceil(bytes / bandwidth))`，跨核两端 COPY 之间插入配置延迟。多个输入按 tensor ID 稳定处理。
4. 同一个 `(tensor, source core, destination core)` 的传入预测只建立一次，后续同核消费者复用。图输入每消费核读一次；图输出每生产核写一次。直接 op-op 边按各边的 `data_size` 单独处理，包括零字节边的两条至少 1 cycle COPY。
5. 选择 `(预计完成时刻，包括本次最终输出写回, 新增 DDR 字节, 核上已分配计算工作, core ID)` 最小的核。这个词典序没有调参权重。副作用仅在选定核后提交，未选分核不会留下时钟或传输记录。
6. 每个 eligible op 一个 singleton 子图，子图 ID 固定来自原始 ID 优先拓扑序；每核执行顺序是上述**同一条全局拓扑分派序**在该核上的投影。返回前调用官方 `derive_multicore_plan`。

这是一个 tensor 感知的 earliest-finish 列表启发式。不同于之前的常数 `500 × 被切前驱数`：一个大 tensor、一个零字节同步边、同 tensor 的十个同核消费者不再被视为同一代价。它也不同于 Fang 在研的 bounded-active-job/residency 路线：本算法没有活跃 job 上限，也没有内存峰值控制。

## 已证明的不变量，以及未证明的部分

**覆盖和全局原始顺序。** ready 只在所有 contracted 前驱完成分派后入堆，所以分派序是原始 eligible DAG 的拓扑序。singleton 映射是 eligible 节点到子图的一一映射；每个 op 只添加到一个核。所有每核次序边都朝这条全局序的前方，因此把这些次序边和原始依赖合并仍无环。这比只验证各核直接依赖顺序更强，但仍不是执行图合法性证明。

**编译子图优先级的拓扑性（每个 tensor 至多一个 eligible producer）。** 本次另行静态扫描确认，冻结 100 图全部满足这个条件。P2 的图输入 COPY_IN 附于该核第一个消费者；最终/跨核 COPY_OUT 附于最后一个本核生产者；跨核 COPY_IN 附于目标核第一个消费者。全局拓扑投影使每个本核 tensor 生产者先于本核消费者，且每个生产者不晚于 COPY_OUT 所属桶、COPY_IN 所属桶不晚于其消费者桶。直接依赖同理。桶内保持官方 Step1 的拓扑次序，故这些由 builder 引入的边不会因本构造的子图桶排序而逆序。一般多生产者 tensor 不享有这个结论：local tensor 可能同时依赖本地 producer 和较晚桶里的远端 COPY_IN，进而使较早 producer 桶中的 COPY_OUT 依赖后桶。代码仍可生成其基础结构方案，但不能承诺通过 P2 编译；多生产核测试仅验证输出计数，不把它扩写为编译验收。

**静态 COPY 计数。** 就 `_build_scene_b_tasks` 引入的 COPY 而言，原始 tensor 的生产核集合和消费核集合确定了图输入、图输出及跨核核对的字节计数。代码的 `predicted_ddr_bytes_without_spill` 对这一部分可通过最终 ownership 的组合计数直接核对。跨核字段计算的是读加写 `2 × size`，不是官方 `cross_task_traffic_bytes` 的单侧口径。它不包含 Step2 spill，因此不是完整官方 DDR 指标。

**没有声称：** 上述证明不涵盖 Step2 换出/回载、Step3 的内存复用补边、各 pipe 最终 FIFO 顺序与跨核 COPY 合并后的无环性。只有 E0 能决定本次方案的完整执行可行性及成绩。预测时钟使用每条 COPY 独占带宽的耗时，同时忽略全局共享带宽竞争、容量门控、spill、实际 Step3 乱序与最终 COPY 桶时序；预测时刻既不是下界，也不是上界，不能据此安全淘汰任何 E0 候选或宣称加速比。

一个具体风险是：按关键路径优先会同时打开许多分支，预测计算负载很均衡，真实 Step2 却可能产生较多 spill；另一个风险是，将较早生产者的 COPY 延后记在消费分派阶段，与官方 COPY 所属桶不同。这些都必须保留为 E0 可证伪点。

## 复杂度边界

设 V 为 eligible op 数，D 为 contracted 原始依赖边数，I 为 tensor incidence 和直接边数。就绪堆和计算 tail 为 `O((V + D) log V)` 的保守界。令 H 累计每个消费 incidence 的已知生产核数（至少按 1 计），外加每个最终输出的生产核数。候选分核工作为 `O(k (V + I + H log k))`；若每个 tensor 只有一个生产者，这接近 `O(k (V + I))`。

一般多生产者输入不能笼统写成 `O(k (V + I))`：每个候选核仍会访问全部来源核，H 可达 `k I`，所以存在 `O(k² I log k)` 项。代码同时保留 k 个候选的局部时钟更新；一轮的临时状态也可能达 `O(k²)`。本题 k 不超过 5，但这个事实不能抹掉渐近项。原始 adjacency 构造中的 producer × consumer 展开、原始 COPY contraction、验证器内部排序另计；调用了这些官方函数，不宣称整个 CLI 已严格实现线性对数复杂度。

## 在看本构造成绩之前固定的 8 个开发图

只读取全部 100 个原始输入作静态扫描。使用数值极值和 case ID 稳定破同值，选出下表；008 额外作为已知 M–V*–M 窄域控制图。002/008/016 以前在别的构造下已公开，不能称 holdout。原始图字段全读；没有根据这个构造的成绩换图。父会话已确认 8 图 × k=2/4/5 的首轮外部 E0 范围，此文档自身没有执行 E0 或扩大预算。

| case | 选择规则 | eligible ops | 组件 | forks | joins | 最大 tensor 消费者 | 最大内部 tensor 字节 |
|---|---|---:|---:|---:|---:|---:|---:|
| 002 | 无 fork 的单组件图中 op 数最小 | 1798 | 1 | 0 | 198 | 1 | 1536 |
| 008 | 已知齐次 M–V*–M 控制图，不要求一般 DAG 路由替代专用构造 | 864 | 108 | 216 | 216 | 2 | 18432 |
| 014 | op 数最大；也是 joins 数最大 | 35705 | 1340 | 144 | 14725 | 2 | 6144 |
| 016 | 内部 tensor 字节最大，同值选 case ID 最小 | 17995 | 1 | 304 | 3355 | 12 | 32768 |
| 025 | 弱连通组件数最大 | 18662 | 2666 | 2666 | 5332 | 2 | 3072 |
| 035 | tensor 消费者数最大，同值选 case ID 最小 | 3857 | 16 | 750 | 1434 | 14 | 8192 |
| 062 | 原始图输入唯一 tensor 总字节最大 | 19636 | 1 | 0 | 2180 | 1 | 1536 |
| 071 | 有 fork 的单组件图中 op 数最小 | 741 | 1 | 216 | 370 | 6 | 4608 |

表中 fork/join 是 contracted DAG 的出/入度大于 1 的 op 数；图输入字节只计没有 eligible producer 且有 eligible consumer 的原始 tensor，每 tensor 一次。全部 100 图中没有 eligible direct op-op 边，因此此分支通过合成手工例覆盖，不声称官方输入覆盖了它。

## 实际静态验证

2026-09-24，当前已授权本机 Python 3.12 环境：

- `python -B -m unittest tests.q2_nikolastarx.test_dag_direct -v`：9/9 通过，零 E0。覆盖单组件分支能分核、真实 tensor/direct 字节改变分核选择、图输入复用、最终输出、多生产核输出计数、原始 COPY 排除、输入列表置换确定性、不修改原始图、配置与边界检查。
- 固定 8 图 × 2/4/5 核共 24 份方案：全部通过 `derive_multicore_plan`；进一步将每核原始 op 相邻顺序边加入原始 contracted DAG，官方 `check_acyclic` 全部通过。没有调用 Step1/2/3 或 E0。
- 8 图的 4 核版本：按最终 owner 独立重算图输入/图输出/每 tensor source→target 核对的字节量，全部与构造记录一致。此检查只证明静态 COPY 数量口径，不证明真实运行时长。
- 子 agent 完成独立只读代码审查，未发现具体的覆盖、确定性或 COPY 计数错误；指出多生产核复杂度限制，已反映在上节。它继承了本任务上下文，不是隔离盲审；没有运行测试或 E0。

24 份静态脚本单图计时约 0.014–1.275 秒，含建索引/构造/结构验证及附加全局原始 DAG 检查，不含进程启动、方案落盘，也没有独占机器。故这些计时只能用于安排下一轮资源，不能替代方案成绩台上的求解端到端耗时。特别是最大的 014 已超过 1 秒，不能用“零在线 E0”推断它必然比 Fang 更快。
