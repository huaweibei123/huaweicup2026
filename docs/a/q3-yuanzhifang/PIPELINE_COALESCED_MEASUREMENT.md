# 第十批：流水阶段合并，保持原操作分核

1. **目标 / 机制**：固定算法 `6e620b5e005a281003d516ce070228934e8a03af` 的 `pipeline_coalesced.py`。只执行一次既有同构共享链连续分段流水分割，将每个非空阶段合并为一个子图，保持每个原计算操作的核心归属，让未修改官方 Step1 决定桶内顺序。分割复杂度为 O(k L²)，严格守卫及 L≤512 沿用原方法。解除 singleton 优先级桶可能提前独立输入，也可能延长生命周期、增加 spill 或 Makespan；本批证伪该机制，不扫描参数，不继承旧计划的 M/V FIFO、无 spill 观察或固定序下界。
2. **输入**：仅官方044，请求4核。只读预检核该图、全部10个官方代码文件和配置，共12个冻结文件；核候选、pipeline/active/construct/baseline及机制文档字节，同时单独核 `pipeline_stages.py` 与原 `6bae8dfa317bc71226068344b59dd65d2612c32b` 完全相同。核冻结公共辅助函数、标准 feed 模板、044真实官方单核分母。控制为 `e6b5500dcbf3818034804168ee79d0f65c16706b` 的完整 pipeline 原件，P2=P3=40927；逐项核 plan/result/trace/log/run/manifest 哈希及相同 graph/config/official 身份，不重跑控制，不从 ratio 反推分母。
3. **输出**：独立 `pipeline_coalesced_benchmark.py`、`pipeline_coalesced_export.py` 与 `results/a/q3-yuanzhifang/pipeline-coalesced-20260924/`；新目录只在实际 START 后创建。记录唯一两字段 plan、完整 P2/P3 result/trace/log、容量/cache_events/operations、stdout/stderr、实际环境与共享资源、派发前内存、调用账、run/manifest、无损 gzip 原字节及压缩哈希、CSV、`board-submission-v1`。method_id 为 `q3-pipeline-coalesced`，采用独立 run/attempt ID。成功冷构造内的官方 `derive_multicore_plan` 验证含子图商图无环；冷构造之后，runner 仅读取新旧 plan，逐操作比较核心归属、操作集合与每核计数，记录归属摘要哈希及 plan 字节/完整 JSON 是否不同，不再次 build/derive。
4. **限制 / 时间**：独立额度≤1 cold + 2外部 E0，同一 plan 分别 P2/P3 一次。1 worker，单调用30秒，含预检和封存的批次120秒、90秒后停止派发，首失败/守卫拒绝/身份或核心归属不符/超时/清理异常即停，0重试/E1/E2/GPU/云。每次派发前 Windows `GlobalMemoryStatusEx` 核可用 RAM≥1 GiB，低于或未知则不派该子进程并停止。保存原始失败产物；清理未确认时保留 raw 并标 sealed=false。若完整 JSON 意外与控制相同，保留实际 cold 墙钟并停止，不重复 E0。
5. **验收**：先提交 runner/spec，再执行 `--check-only` 并报告 ready；预检只读源码、输入及现有原件，0 solver/E0，不调用真实图 build/derive/Step1/2/3。实际执行仍等待主会话明确 START，并填写当时 `--concurrent-work P2`，不声称整机独占。新计划必须逐操作保持控制的核心归属且完整 JSON 不同；官方未修改 E0 成功后才报告质量、搬运、命中率与容量。冷 solver 启动至读图、构造、静态合法性检查、写盘退出计实际墙钟；runner 的独立控制核验计批次开销，外部 E0 墙钟另列。保留负收益与失败，不把本地 feed 预检当作中央接收或独立验收。
6. **交接 / 截止**：无另设硬截止。START 前只准备；自然结束或停止后先给实际 T0/T1、调用数、状态和派发前内存最小值，再归档/导出/提交，并对固定数据 SHA 执行协议预检。运行期间不读 live ledger；仅在结束后读取完整账本。只精确提交本批自有文件，不推送，不修改前九批或官方/算法源码。5～10分钟是官方效率建议，本批120秒是团队资源保护。

只读准备命令（不创建正式结果目录）：

```sh
python -B src/q3_yuanzhifang/pipeline_coalesced_benchmark.py --check-only --graph-dir ../huaweicup2026/data/raw/a/official-cases/data
```

收到 START 后才可去掉 `--check-only` 并提供真实 `--concurrent-work`；实际并发情况如与预登记不同，应如实记录并向协调方报告。阶段合并效果只能依据本批官方原件判定，既有三个合成检查不代表真实图成绩。
