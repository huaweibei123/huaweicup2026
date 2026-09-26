# 本机 P2 真实一核 benchmark

执行会话：`nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc`；分工登记 [Issue #26](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5814790103)。本任务不写成绩台的代码或中央成绩库。

1. **任务目标**：对固定 P2 连续分块构造算法运行 001–100 全部图、模拟核数 `k=1` 的真实求解；每图一次构造、一次冻结官方 P2 E0 评价。它补的是求解器成绩，不能将官方 A 单核分母当作求解结果。
2. **输入文件**：求解器固定提交 `0b58c123cccf02fc993b741d79dcd8511e4dd38f` 的 `src/q2/construct.py`，`data/raw/a/official/data/case_001.json`–`case_100.json`、固定 `config.txt`、`docs/a/source-manifest.json`；官方代码聚合哈希 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。已有官方 A 单核分母来自合入主线的 PR #89，仅作配对复用。
3. **输出要求**：每图独立 plan、完整官方 result/Trace 的无损 gzip、官方日志、run 收据；批次清单和 `board-submission-v1` feed 位于 `results/a/local-p2-k1-20260924/20260924T131640Z-s59ee/`。不覆盖他人尝试；导出器机械生成字段和哈希。
4. **限制条件**：先 001/002/044 两单元并发，链路正常后 4、最多 8 单元；每图构造上限 120 秒、官方复评 180 秒；全批自 T0 起最多 120 分钟。0 E1/E2、0 搜索、0 自动重试；采样观察内存，系统可用内存低于 8 GiB 不启动新阶段。不同工作单元独立目录。
5. **验收标准**：100 个位置各有明确成功/失败/超时，成功条目 plan/result/run 哈希与冻结图/配置/官方源码一致，官方 P2 场景 B、`num_cores=1`；严格协议检查 `eligible=100`。该检查仅证原件与格式，不替代独立复跑或算法科学验收。
6. **截止时间**：本批实际开始 `2026-09-24T13:16:49.687Z`，到期 `15:16:49.687Z`；实际全批 100 格于 `13:18:12.024Z` 前完成。之后等待网站维护者的下一具体范围，不自动扩 P1/P3。

实际命令、平台、逐条收据及汇总见[批次 README](../../results/a/local-p2-k1-20260924/20260924T131640Z-s59ee/README.md)。
