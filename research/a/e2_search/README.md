> P2/P3 适配已在本分支开放；接口、固定检查点与真实冷搜索性能见 [P23_HANDOFF.md](P23_HANDOFF.md)。
> 下文保留 PR42 的 P1 说明与成绩，不能外推到 P2/P3。

# E2：供批量搜索使用的原生评分器

这是可运行的 **Problem 1 开发版本**。官方局部编译保留 Step1、spill/backing、Step3 内存依赖；C++17 内核逐事件重放全局 FIFO、共享 DDR 和等待。Python 负责官方方案入口、划分缓存、回退和受控进程。没有为了 E2 名称强行引入近似，也没有拟合校准系数。

它解决的是大量候选的评分成本：只返回实际计算的 Makespan、搬运量和跨 Task 流量，不构造每个候选的完整时间线/审计 JSON。需要完整诊断时，整份结果透明走 E1。官方冻结源码未改动；正式成绩仍由 E0 最终确认。

## 当前结果及成本边界

本机 macOS arm64 / Apple Clang 21 / Python 3.12.13。三个正式图、四个 64 候选开发池，256 次评分（248 个不同的图–方案组合），所有候选都有完整 E0 原输出。Makespan、搬运量、跨 Task 流量的值与类型无差异，四个池 top-8 都保留 E0 最好值。**这些池都是开发证据，不是独立封存验收。**

| 64 候选池 | E1 搜索 API | E2 搜索 API | 比值 |
| --- | ---: | ---: | ---: |
| 004，固定划分 | 1.789 s | 0.068 s | 26.33× |
| 005，固定划分 | 9.202 s | 0.303 s | 30.34× |
| 011，固定划分 | 1.554 s | 0.060 s | 25.72× |
| 004，8 种划分，各 8 调度 | 2.214 s | 0.443 s | 5.00× |

计时从已解析输入开始，包含实例初始化、首个划分编译及全部候选调用。双方调用同样的内部搜索接口、返回三个相同指标；**被测 E1 固定为 `5bfe53a`，内部仍构造完整诊断。这个比较体现现有候选流程成本，不是相同原生准备接口的语言/内核对照，也不是新原生 E1 的比较，更不能冒充正式 E2 ≥10× 联合门槛通过。** 不含生成方案、文件读写及解释器启动。逐池顺序、CPU、P50/P95、每次调用、图及源码哈希见原始结果。

另外实际执行了两个完整的选优调用流程：E1 基线评分 64 个并由 E0 确认最优；E2 评分 64 个、取前 8 个用 E1 完整复核，再由 E0 确认最优。005 固定划分 **9.135→1.946 s（4.69×）**；004 混合划分 **2.280→0.883 s（2.58×）**。两条路线选出的最终 Makespan 一致。这些是实际循环计时，仍不包含候选生成和文件 I/O，不能叫完整求解器加速。

## 资源与并行

- 默认 `workers=1`，内核不再开线程；外层已经并行跑实验时，每个实验保持一个 worker。只有实际测得收益时才增加内层并行。
- 每个 worker 最多一个在途请求，父进程最多读取一个 worker 大小的批次，按输入顺序流式返回；不会预取所有候选。超时/崩溃独立标记，取消迭代器或退出上下文会清理在途 worker。
- 默认缓存 16 MiB；缓存计费覆盖键、保留的 Python 元数据和数字数组，**不是 RSS 上限**。原始图、运行时、临时编译、原生暂存和分配器不在此限额内。缓存有条目数上限；缓存失败或过大时不保留，不伪造结果。
- 每 256 请求回收 worker；可用 `recycle_peak_rss_bytes` 在请求完成后按观测高水位回收。它不是请求执行过程中的硬内存限制。单个请求的内存尖峰尚无跨平台强制上限。
- 005 的 64 请求，在单独子进程中计入解释器导入、文件读取、spawn、IPC 和退出：1 worker 的 E1 **8.385 s**，E2 **0.471 s**；2 workers 分别 **4.639 s / 0.504 s**。该规模 E2 两 worker 反而较慢。
- 相同 005 资源试验，父进程＋worker 的采样 RSS 总和：1 worker **147.81→127.69 MiB**，2 workers **235.97→196.73 MiB**；单 worker 自报峰值 **87.98→73.11 MiB**。50 ms `ps` 采样可能漏尖峰，共享页重复计数，排除 multiprocessing resource tracker；不等于独占物理内存或硬保证。固定划分缓存从 E1 的序列化 1.802 MiB 到 E2 计费 0.379 MiB，两种计费口径不同。
- 2 workers、每 256 请求回收的 1024 请求连续试验通过，实际循环使用 64 个方案，四个 worker 生命周期均正确且最终关闭；自报峰值约 73.22–73.36 MiB。它不是 1024 个独立新候选，也不是长时间泄漏证明。

## 使用

从仓库根目录执行，Python 与 NumPy 沿用锁文件，不安装新依赖：

```sh
uv sync --locked
uv run python scripts/a_materials.py --extract
uv run python -m research.a.e2_search.build_native
uv run python -m unittest discover -s research/a/e2_search/tests -p 'test_*.py' -v
```

构建必须关闭 fast-math 和 FMA contraction。当前只实测 Apple Clang；工具链不可用或二进制缺失时 API 透明回退 E1，记录 `route` 和 `fallback_reason`，不能继续宣称原生速度。Rust 的 `rustc/cargo` 当前不在 PATH，尚无真实 Rust 对照成绩。

```python
from research.a.e2_search import E2Evaluator, E2BatchEvaluator
from src.eval_exact import read_config

config = read_config("data/raw/a/official/data/config.txt")
engine = E2Evaluator(graph, cache_bytes=16 << 20)
record = engine.evaluate_record(plan, **config)
# status: ok / invalid / error。查看 route: native / e1_fallback / e1_full。
full = engine.evaluate_record(plan, full=True, **config)["result"]

# 使用正常的 if __name__ == "__main__" 保护启动 spawn。
with E2BatchEvaluator(graph, workers=1, timeout_seconds=60,
                      max_tasks_per_worker=256) as pool:
    for record in pool.evaluate_batch(plans, **config):
        consume(record)
```

`graph`、`plan` 都直接使用官方 JSON 对象；`plans` 可为惰性迭代器。内部 search record 有显式元数据，不是官方结果 JSON。只有 `status=ok` 才有可用指标。pool 另外可能返回 `timeout`；worker 失败仍为 `error`。若提前结束迭代，关闭迭代器或 pool。

搜索 CLI 接收每行一份官方方案的 JSONL，输出为内部记录，已有输出文件拒绝覆盖：

```sh
uv run python -m research.a.e2_search.cli graph.json plans.jsonl --config config.txt --output results/new-run/records.jsonl --workers 1
```

官方完整格式 CLI 则透明委托 E1；stderr 明示路线，结果/Trace/日志不拼接原生分数，也没有原生加速承诺：

```sh
uv run python -m research.a.e2_search.multicore_cut_evaluate_problem_1 graph.json plan.json --config config.txt -o results/new-full/result.json --trace-output results/new-full/trace.json --log-output results/new-full/log.txt
```

## 缓存、正确性与失效域

图在实例创建时复制并固定。整个原始映射的有序键值、带宽与容量共同决定缓存身份，保留数值类型；改变任一内容会重编译，绝不按局部 Task 成员集合复用不同划分的 COPY ID。新调度始终检查类型、恰好覆盖、重复和 Task 依赖＋核序的联合环；等待参数每次验证。全局重放成功才准入缓存；返回字典没有与缓存共享的可写别名。

原生域：1–128 核、正整数操作时长、整数非负等待，保守累计时间界限低于 `2^50`，最多 2,000,000 编译后操作。超界、非整数等待、缺库、全局死锁、max_iter 或适配器异常统一尝试 E1，保留官方错误类别；不会把原生不支持判成方案非法。`max_native_ops` 只限制原生准入，回退本身仍可能消耗更多资源。

8 项开发测试包含 80 个新随机微图的冷/热/换核评分、已发布 FORM 样例、L1 spill/backing 重复 incarnation、参数与图快照、无缓存/逐出、非法/超时/崩溃、完整诊断回退和进程清理。正式 CLI 也实际跑过成功结果/Trace 值相等、日志字节相等，以及非法方案不中断后续搜索记录。此前原生内核的逐操作时刻和 DDR 事件审计证据见父交付 `03f02e7`；本次新正式池比较的是本接口三个指标，没有声称本接口新生成了完整时间线。

旧 E2 `d83d5f3` 的 rank/event 在完全相同的新池另作只读对照：event 的中位相对误差 **30.42–37.47%**，P95 **30.55–38.60%**；rank 不输出 cycles。新路线零观测误差且固定划分更快；变化划分时旧近似仍更便宜，却未通过误差目标。保留旧实现和对照证据，不作为新核心的数值依据。

主要未完成项：生产写权交接、LYX 独立测试、图级封存池、多平台、同一原生准备接口对照、Rust 实跑、Problem 2/3、不同规模/带宽/核数的联合发布矩阵及硬 RSS 约束。混合划分仍只有约 5×，不宜以三个高复用池外推所有算法邻域。新原生 E1 完成后须重新冻结对照版本并测量。

## 证据与复现

- [四个池、全 E0 原输出、计时、资源和旧路线对照](../../../results/a/proxy/e2-native-search-20260924/)
- [实际短名单流程和 1024 请求](../../../results/a/proxy/e2-native-workflow-20260924/)
- [两种 CLI 的实际输入输出](../../../results/a/proxy/e2-native-cli-20260924/)
- [来源清单](PROVENANCE.json)、[给独立测试者的交接](HANDOFF.md)

所有输出使用新目录，命令不可覆盖上述证据：

```sh
uv run python -m research.a.e2_search.benchmark --output results/a/proxy/e2-independent-NEW
uv run python -m research.a.e2_search.workflow_probe --inputs results/a/proxy/e2-independent-NEW --output results/a/proxy/e2-workflow-NEW
uv run python -m research.a.e2_search.cli_probe --output results/a/proxy/e2-cli-NEW
```

旧路线对照使用独立、干净的 `d83d5f3` checkout，`compare_legacy.py --legacy-root <checkout> --inputs <new-run> --output <new-file>`。主实验的 `run.json` 保存实际代码哈希，`as-run-source.zip` 对应这些字节；后来增加的流程、CLI、旧路线复核脚本各自独立留记录。基底 HEAD 不是新增代码已提交的虚假标记，以文件哈希和最终 PR 提交共同定位。
