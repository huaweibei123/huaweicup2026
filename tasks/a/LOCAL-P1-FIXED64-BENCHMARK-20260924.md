# 本机 P1 fixed64 构造与官方复评

负责人：@NikolaStarx，执行会话 `nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc`

分支：`codex/local-benchmark-20260924`

沟通 Issue：[登记与交付](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5814790103)

1. **任务目标**：对冻结的 P1 100 图 × 1–5 核，各运行一次固定 `fixed64` 构造和独立的官方 E0 最终复评，给方案成绩台补真实成绩；不调用 E1/E2 或搜索循环。
2. **输入文件**：`data/raw/a/official/data/case_001.json` 至 `case_100.json`、固定 `data/config.txt`；身份由 `docs/a/source-manifest.json` 的大小与 SHA-256 校验。
3. **输出要求**：逐格 plan、官方 result、trace、run 收据与原日志；统一协议 feed 在 `results/a/local-p1-fixed64-20260924/20260924T1337Z-s59ee/`。
4. **限制条件**：求解源码固定提交 `4dff90ef699fd51845cf482951e8477066f5f566`；runner 固定提交 `556077b23ae903ddea246f9f9965b50e59c37dca`；每格 solver 最多 120 秒、E0 最多 180 秒，批次总截止 120 分钟。先以 2、4 workers 小样验证，再 8 workers 跑剩余 490 格；零自动重试，输出目录隔离。
5. **验收标准**：500 格均有一次成功的 plan 和官方 E0 原件，严格协议校验保留原件上限的准入结果；官方单核分母使用已有固定原件，不将优化方案 k=1 冒充单核基准。
6. **截止时间**：2026-09-24 15:37 UTC；实际批次于 13:43 UTC 完成。

## 交付记录

实际命令：`python -B src/local_benchmarks/s59ee_p1_fixed64.py --source ../local-p1-fixed-4dff --batch results/a/local-p1-fixed64-20260924/20260924T1337Z-s59ee --cases <分片> --cores 1,2,3,4,5 --workers <2|4|8>`；详见 `batch.json` 和各格 `run.json`。导出只读现有收据：`python -B src/local_benchmarks/s59ee_export_p1.py --batch <上述目录> --cases 001:1,...,100:5 --output <上述目录>/board-feed-full500.json`。

代码提交与输入版本：求解器和 runner 固定提交如上；官方聚合 SHA-256 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，config SHA-256 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。

结果与图表：500/500 次真实构造、500/500 次官方 P1 E0 复评成功；`board-feed-full500.json` 共 500 条。官方 result 为 `.json.gz`，保留原字节哈希与解压往返校验；所有完整原件仍在批次目录。

结论及限制：方案成绩台当前每原件及解压内容上限为 64 MiB。014/k2–5、076/k2–5、091/k3–5 共 11 格官方原始 result 解压后超过上限，因此严格校验当前为 489 条正式、11 条仅报告。原官方 result 不为适配格式而改写；由网站维护者决定可审计的分片或接收方案。批量运行、原件匹配不等于算法独立复跑或科研终验。

未验证项：跨机器复现、11 个超限格正式准入、真机收益。

PR：[本机批量 benchmark](https://github.com/huaweibei123/huaweicup2026/pull/93)。
