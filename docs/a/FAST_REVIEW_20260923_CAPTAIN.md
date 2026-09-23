# A-R1 FAST 首批独立复核（队长，2026-09-23）

## 结论与范围

对 PR #20 固定提交 `3357d7ef9c1ad443dd0799f6ecb5b813df6753b3` 的有限复核：已提交的 64 个候选 E0 完整 JSON 在本机重新计算后全部一致；E1 在这 64 个候选、3 个官方开发例和新增 169 个微型输入对照中未发现差分。E1 的三例配对几何平均加速为 **1.1494× / 1.1359× / 1.1753×**，未达到 3×。E2 事件代理的 Makespan 相对误差中位数 **25.7591%**、P95 **28.8954%**，未达到 1% / 3%。

这是可继续开发的首批实现与可复现证据，**不是任务验收通过**。本次不合并、不标记 done，不外推至 Problem 2/3、封存集或全部输入域。成员原交付已明确承认这些性能与范围限制；本次复核没有发现与其声明相反的实验结果。

复核使用独立 worktree、锁定环境 Python 3.12.13、macOS 27.0 arm64（18 个逻辑 CPU）。冻结材料经过 `scripts/a_materials.py --extract` 的清单校验：114 个文件、100 个 case。未修改官方源码、原始数据、公共真值或门槛。

## 本机证据

证据根目录：`results/a/review/20260923-fast-3357d7e/`。

| 检查 | 结果 | 边界 |
| --- | --- | --- |
| 成员已有测试 | E1 7/7、E2 16/16、native Python 5/5 | 有限单元与接口测试 |
| 64 候选重新运行冻结 E0 | 保存的完整 JSON 全部一致 | 同一个开发图、同一候选池 |
| 64 候选 E1/E0 | 完整函数返回对象零差分 | 不使用容差或字段白名单 |
| 独立生成 169 个微型输入 | E1/E0 完整结果或异常类型、消息零差分 | 77 个返回结果、92 个拒绝；不是正式题面域的完备证明 |
| 三个官方 case 配对计时 | 完整结果一致，约 1.14–1.18× | 内存内函数调用，排除 CLI 启动和 JSON/Trace 序列化 |
| E2 两条路线 | 排序 Spearman 0.8568；事件 0.8127；二者该池 regret 都为 0 | 一个开发池，不能证明多池保留率或封存集泛化 |
| C++17 与 Python 小内核 | 31,387 字节输出一致；SHA-256 `30b2a06e4fde37cb43f5feb59e7e0735049e2c610e35eb09fd5238a5e25f3186` | 512 行合成特征的排序内核，不是完整 E2 |
| Rust | 本机无 rustc/cargo，未编译 | 没有安装新工具链 |

三例 `case_001/019/080` 的 Makespan 为 189027 / 141133 / 294124。每例预热 1 次、正式重复 5 次、交替 E0/E1；本次全部 15 对速度比均 ≥0.8×，但均未达到主要 3× 门槛。计时原始 CSV、方案、输入/实现/config 哈希见 `e1-matrix/`。

`e2-routes/summary.json` 是成员比较脚本的原样本机输出，其中 `recorded_e0_seconds_over_route_median` 使用成员 Windows 上保存的 E0 时长除以本机 Mac 的代理时长。**这些约 442 / 419 的数值是跨机器比值，不能用作加速证据，也不是 E2/E1 比值。** 本报告只采用该文件的完整性校验、误差与排序结果；没有把存储的 E0 时间用于验收。

C++ 本机为 Apple clang 21.0.0，预热 1 次、运行 5 次，进程端到端中位数 6.163 ms；Python 为 21.902 ms。这个小内核结果不替代真实图解析、特征提取、合法性与回退等成本。

## 独立输入与比较方法

复现脚本 `scripts/a_fast_review_3357d7e.py` 从冻结源码目录直接导入 E0，不通过候选的官方加载器取得 oracle。它固定成员提交和两份 E1 文件 SHA-256。64 个保存的 E0 JSON 在官方结果经过标准 JSON 序列化/解析后逐字段、逐类型比较；E0/E1 函数结果直接做类型严格比较。

这里的 JSON 往返只处理 JSON 本身规定的表示转换，例如 `memory_peak_by_core` 的 Python 整数键在 JSON 中成为字符串键。最初复核脚本直接比较 Python 字典与已解析 JSON，因这个表示差异停止；确认全部 JSON 值一致后修正了比较层，未修改候选实现或任何数值。

新增微型图采用种子 900000–900059：2–9 个算子、乱序 ID、多消费者、零字节/零周期、无用 tensor、1–5 核与附加空核。每图检查基本方案、缺失映射和可用时的非连续合并方案，共 169 次对照。其中 60 个基本方案返回结果；60 个缺映射被拒绝；49 个合并方案中 17 个返回结果、32 个因依赖或任务环等被拒绝。拒绝路径比较异常类型与消息，不能算成 169 个成功合法方案。

本次审阅了索引 Task 构图、官方模块隔离加载、两条 E2 路线和比较脚本的核心逻辑。没有把代码阅读或有限差分当作全域等价证明。

## 复现入口

从本复核分支的项目根目录运行，所有新结果使用新的输出目录：

```sh
uv sync --locked
uv run python scripts/a_materials.py --extract
uv run python -m unittest discover -s tests/eval_exact -p 'test_*.py' -v
uv run python -m unittest discover -s tests/eval_proxy -p 'test_*.py' -v
uv run python -m unittest discover -s tests/eval_proxy_native -p 'test_*.py' -v
uv run python scripts/a_fast_review_3357d7e.py --output output/fast-review-replay/independent-results.json
uv run python -m src.eval_exact.benchmark --cases case_001.json case_019.json case_080.json --output-dir output/fast-review-replay/e1-matrix --seed 2026 --cores 4 --warmup 1 --repeats 5 --min-subgraph-size 4 --max-subgraph-size 12
uv run python -m src.eval_proxy.compare_routes --graph data/raw/a/official/data/case_001.json --config data/raw/a/official/data/config.txt --pool-dir results/a/proxy/r20260923-e2-dev64-gzip --output output/fast-review-replay/e2-routes.json --warmup 1 --repeats 3
uv run python -m src.eval_proxy.native.run_experiment --candidates 512 --seed 20260923 --iterations 5 --report output/fast-review-replay/native-report.json
```

## 下一阶段建议与未验收项

1. E1 先补改写后的分阶段 profiler，与同机 E0 对照，判断剩余耗时；保留原始 profile 或可复现的机器可读摘要。再决定继续消除扫描、索引复用或引入原生内核，不以语言名称作为速度证据。
2. E2 先分解误差来源。排序代理可作为候选筛选开发路线，不能冒充低误差 Makespan 估计器；事件代理需要独立的误差修复。基准脚本跨机重跑时应把旧 E0 比值标记为不可比较或重新计时。
3. E2/E1 必须在同机、同配置、同候选池端到端比较。后续按任务卡补独立多池、图级开发/校准/封存拆分、shortlist 保留率、尾部误差和回退成本。
4. 当前主要是 Problem 1。Problem 2/3、全面非法输入、官方默认 CLI 路径、冷启动/批量/完整输出计时仍未完成；不要将后续 Q3 FIFO 假设直接用于 E1。
5. PR #20 的三个系统 demo CI 均通过，但现有工作流运行 demo 与 mailbox 测试，没有执行本次 evaluator 矩阵，因此不构成 evaluator 验收。

本报告属于队长的有限独立复核；成员后续实验和最终验收须分别记录，保持固定提交与证据关联。
