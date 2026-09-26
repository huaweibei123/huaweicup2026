# 067/k5 首波容量阶梯：独立有界测量准备

候选 `wave_stair` 固定源码 `68fbe66e97f78161bfb6f4f9e83cd2f0977ce7a9`。本批仅 067、5 核、一个固定构造：最多一次 fresh cold solver，随后同一计划的官方外部 P2/P3 各一次；没有在线 E0 选优、E1/E2 或自动重试。新 run ID 为 `yuanzhifang-q3-wave-stair-20260925`，结果目录 `results/a/q3-yuanzhifang/wave-stair-20260925`。该目录和旧 `wave-tail`、`wave-capacity` 测量完全独立。

以下是**待 runner/export/本文提交冻结之后**供队长安排的命令形式；本次准备未运行 `--check-only` 或实际测量：

```powershell
uv run --no-sync python -B src/q3_yuanzhifang/stair_benchmark.py --check-only
uv run --no-sync python -B src/q3_yuanzhifang/stair_benchmark.py --concurrent-work P1+P2
uv run --no-sync python -B src/q3_yuanzhifang/stair_export.py
```

`--concurrent-work` 必须改填执行时的真实状态。最新公共协议 `2da54f2bcfb85e033df900b03b4d181a698fd012` 的跨批次资源调度由总调度负责，网站被动接收报告；本文件与代码准备不构成 START。执行前由根核对本地 P1/P2 窗口及实际资源状态，按已授权的一次固定预算派发。冻结后的 `--check-only` 只核候选及全部依赖提交原字节、官方 manifest 中 10 个 code 文件加 graph/config 共 12 份原字节、feed 模板、runner/export/本文 HEAD 字节，执行 0 build/derive/Step/E0。

实际批次限定 1 worker；每次派发在全局锁内确认至少 2 GiB 可用物理 RAM 和 2 GiB 输出磁盘空间，不足或未知立即停。每次调用最多 60 秒，整批 180 秒，120 秒之后不派发；首失败停，0 重试。Windows 子进程以 `BELOW_NORMAL_PRIORITY_CLASS` 启动，超时安全清理并保留已完成原件。完整冷墙钟包含解释器启动、图/配置读取、索引、严格结构守卫、两遍切点 DP、逐位置 `beta→U→h+c` 首波阶梯、tail-first 次序、余下最少均衡波、零 COPY FIFO 必要界、canonical singleton 静态 derive 和计划落盘。此前静态审计不复用为本次 solver 结果；外部 P2/P3 另计调用与墙钟。

runner 读回计划和元数据后核 `guard=true`、`selected=wave_stair`、singleton 恰覆盖所有 eligible op、70 个完整作业各核 14 个且完整归核、最后一作业按五段连续切点归核；再按原图逐 op 周期重算各核 M/V 工作量和 DP 峰值，核 `n_c=h+c`、逐位置代理宽度、首波尾操作优先及后续 wave 次序。读回校验不重新调用 `analyze/build`。P2 不要求 `problem` 字段；P3 要求 `problem=3`、`read_only`。P3 后置审计保留异常 cache 事件检查，以原图 tensor ID/size 核 shared 读量分账与 hit+miss 总账，并验 Makespan 不小于实际 M/V 工作量必要界。跨核传输全部保留原件，只报告数量，逻辑 tensor/direct tail 边归属待另行只读验收；不把旧完整作业共享读取界或 `cross_core_transfers=[]` 当作本候选承诺。

命令、退出码、资源、平台、冷墙钟、计划、官方完整 result/trace/log 和 stdout/stderr 以压缩与原始字节哈希封存。若官方成功后发生读回/后置审计失败，原件仍保存且另出 failed receipt/feed 行。exporter 不启动求解或评估，先封存 manifest 和 ledger，再写标准 feed、run receipt 与汇总；每条 P2/P3 行引用同一 construction ID，feed artifacts 不添加非标准 `call_ledger` 键。历史 pipeline `15686331`、完整作业界 `12446880`、队长同身份参考 `12237901` 只是事后背景，不进入在线选择或本批新调用账。

这是结构家族开发验证，尚无正式 E0 成绩，更不是统一 full500 算法成绩。容量足迹和零 COPY FIFO 路径是代理/必要界，不证明零 spill、实际 DDR、Cache 或 Makespan 改善。
