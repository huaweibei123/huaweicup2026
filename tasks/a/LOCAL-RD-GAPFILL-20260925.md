# P1 overload-list k5 缺口补测

负责人：@NikolaStarx，执行会话 `nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc`

分支：`codex/rd-gapfill-s59ee-20260925`

沟通 Issue：[会话登记与数据交付](https://github.com/huaweibei123/huaweicup2026/issues/26)

1. **任务目标**：接续 P1 研发已完成的 18 个 `q1-component-overload-list` 五核坐标，补齐其余 82 图的同版五核 benchmark。保留改进、退步和失败，不把历史最优组合混成单一算法均值。
2. **输入文件**：冻结 `data/raw/a/official/data/case_001.json` 至 `case_100.json`，固定 `data/config.txt` 和 `docs/a/source-manifest.json`；82 个剩余图号由 `src/local_benchmarks/s59ee_p1_overload_manifest.json` 精确列出。
3. **输出要求**：独立目录 `results/a/local-q1-overload-gapfill-20260925/<run_id>/`；逐格 plan、官方 E0 result/trace/log、诊断、run 收据与标准 feed，固定提交后交方案成绩台接收，历史 18 格只引用、不重算。
4. **限制条件**：求解器固定 SHA `3c6e41b938c764d207de45584fb526c64f4eb845`，入口 `src/q1/component_overload.py`，`max_rounds=64,max_sinks=64`。至多 82 次 solver + 82 次冻结官方 P1 E0，0 E1/E2，0 自动重试。每格 solver 30 秒、E0 60 秒；整批 1200 秒。先 4 格 2 workers，再剩余 78 格最多 8 workers；启动前可用内存至少 6 GiB，首次异常阻止新排队启动，已在途收尾，保留全部收据。
5. **验收标准**：只读预检固定 runner/manifest/solver 和 114 份原件哈希；82 个坐标均有终态与真实调用账，成功须通过官方 P1 E0、协议与固定 Git 原件校验；服务实际入库回读不等于算法终验。
6. **截止时间**：无用户设定日历截止；P1/P3 已预告的微型评分窗口释放后才启动本批 T0。

## 交付记录

实际命令：`.venv/bin/python -B src/local_benchmarks/s59ee_p1_overload_gapfill.py --source <固定3c6e检出目录> --batch results/a/local-q1-overload-gapfill-20260925/20260924T1712Z-s59ee`；只读预检加 `--preflight`。产物详见该目录的 `batch.json` 和逐格 `run.json`。

代码提交与输入版本：runner 与 manifest 启动前固定提交 `8fecaaaf786a9977d30b5d9cd9722e053748bef5`；官方聚合哈希 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，config 哈希 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。

结果与图表：2026-09-24 17:12:26–17:14:08 UTC 运行，82 格中 76 成功、014/041/079 的 k5 官方 E0 各 60 秒超时、098/099/100 的 k5 因首异常停派未启动；79 solver + 79 官方 E0，0 E1/E2、0 重试。82 条 `board-feed-82.json` 经本地严格协议校验为 76 可正式接收、6 非成功；本任务不要求新图件。

结论及限制：既有 18 格含退步，本批仅补同算法覆盖，不承诺质量提升。分核/放置的代理时间不是官方 Makespan。

未验证项：剩余 6 格的另行限额补测、全100图同算法平均值、跨机器复现与算法终验。原批失败/未跑原件永久保留，不原地改写或自动续跑。

PR：待发布。
