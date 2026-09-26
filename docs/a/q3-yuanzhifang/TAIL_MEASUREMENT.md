# 067/k5 单尾部作业切分波次测量

本批只准备 `wave_tail` 一个固定候选：067、5 核，最多一次冷 solver 构造、同一计划的外部官方 P2 和 P3 各一次。代码候选固定在 `1b0da8c9f92d868209d0cada77a170eb558c997c`；其 `wave_capacity` 守卫和容量模型依赖固定在 `2cf325fb717077cd902830e7f01c920d27cbf8ec`。runner、exporter 和本文需另行提交冻结后才能 `--check-only` 或实际派发；`--check-only` 只核源码、官方图/config/code、模板和依赖原字节，不构造计划、不调用 Step/E0。结果目录 `results/a/q3-yuanzhifang/wave-tail-20260925`，run ID `yuanzhifang-q3-wave-tail-20260925`，不复用旧批原件。

入口在仓库根目录，图目录按默认相邻官方只读数据目录：

```powershell
uv run --no-sync python -B src/q3_yuanzhifang/tail_benchmark.py --check-only
uv run --no-sync python -B src/q3_yuanzhifang/tail_benchmark.py --concurrent-work P1+P2
uv run --no-sync python -B src/q3_yuanzhifang/tail_export.py
```

实际 `--concurrent-work` 必须按当时真实并发工作填报，可选 `P2`、`P1`、`P1+P2`、`none-reported`、`unknown`；上述 P1+P2 只是格式示例。只有根审查冻结并安排独立窗口后才运行。1 worker，每次派发在全局锁内检查可用物理 RAM 和输出磁盘均至少 2 GiB；未知或不足即停。每调用最多 60 秒，批次 180 秒，120 秒后不再派发；首次失败停止、零重试、零 E1/E2。子进程 Windows 优先级为 `BELOW_NORMAL_PRIORITY_CLASS`。冷墙钟包含新 Python 进程启动、图读取、索引、守卫、两遍 DP、构造、静态 derive 与落盘；外部 E0 墙钟分列。

solver 后必须验证 `guard=true`、`selected=wave_tail`、singleton 恰覆盖全部 eligible op、70 个完整作业在 5 核均分且各完整归核、最后 1 个作业按 5 段非空连续位置只跨对应核；直接从原图/计划重算每核 M/V 周期工作量并与 metadata、DP 峰值对照。失败不会派发 E0。P2 不要求 `problem` 字段；P3 要求 `problem=3`、`cache_mode=read_only`。P3 后置审计对 cache hit/miss 原始事件作总账和原图 shared tensor ID 字节分账，并要求 Makespan 不低于实际每核 M/V 工作量最大值。跨核传输保留完整官方原件与计数，由根作只读逻辑 tensor/direct tail edge 归属复核；此 runner 不用猜测谓词拒绝结果。尾部分裂不宣称完整作业版 `W×wave_count` 共享读取界，也不要求跨核传输为空。

每次调用保存命令、退出码、优先级和环境、资源检查、墙钟、stdout/stderr；计划与官方完整 result/trace/log 保存 gzip 及压缩/原始哈希。失败、超时、守卫拒绝或后置审计失败均留 manifest、ledger 和已成功原件；验证失败另出独立 failed feed 行。exporter 不派发求解或 E0，先封存 manifest/ledger 后生成标准 feed、run receipt 和汇总，不引用 live ledger。每评价引用同一个 construction ID，feed artifacts 只用标准键。

历史 pipeline 067 P2/P3 `15686331`、完整作业计算必要界 `12446880`、同身份队长参考 `12237901` 仅供事后比较，不是本批调用、在线选优或统一 full500 算法成绩。当前只做结构候选的有界开发验证；官方 Makespan、额外 DDR、P3 cache 命中和完整冷墙钟应待真实外评报告。
