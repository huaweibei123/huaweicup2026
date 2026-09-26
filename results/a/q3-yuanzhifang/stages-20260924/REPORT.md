# 044 共享权重同构链同层交错：独立小阶段

本阶段在 044、4 核的固定官方配置下得到 **P3 Makespan 66992 cycles**，比首批本机 baseline 70261 降低 3269 cycles（4.652652253739628%）；P2 从 91922 降为 67339（26.74332586323187%）。这是一个公开开发图的一次观测，不是全 100 图或独立最终验收。

| 指标 | 首批 affine_eighth baseline | 本次 shared_stages |
|---|---:|---:|
|P2 Makespan cycles|91922|67339|
|P3 Makespan cycles|70261|66992|
|P3 调度搬运 B|5155200|3766656|
|P3 总额外搬运 B|4179744|2791200|
|P3 spill 额外搬运 B|1388544|0|
|P3 Cache 字节命中率|0.32948412200326344|0.007025400840996889|
|本次计划 P3 hit / miss bytes|见首批原件|26304 / 3717824|

新计划官方各核 L1 memory_peak 为 `86272/86272/86272/82176 B`，UB 为 0；不是预登记中的静态区间估计。计划保留原作业分核，严格同构链守卫通过后按原操作位置同层交错。spill 消失与更短 Makespan 同时出现；Cache 命中率下降，不能据此说算法退化。P2/P3 同计划都改善，但本批只证明这一固定候选的结果，不能据此推出任意输入上局部峰值与 Makespan 单调关系。

## 固定来源与调用

- 算法：`b4f7f67673bce89d3032042795c08a149bb68410`，`src/q3_yuanzhifang/stages.py`。
- 实际 runner：`bae8b09b615a6afddc440f3701755914eca94918`，`src/q3_yuanzhifang/stage_benchmark.py`；复用冻结 `39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0` 的进程与原字节压缩辅助函数。
- UTC T0=`2026-09-24T14:24:07.342626Z`，T1=`2026-09-24T14:24:21.238255Z`，批次 13.896062300000267 秒。
- 独立预算最多 1 次冷构造、2 次 E0，实际全部成功；1 worker、每次 30 秒、批 120 秒、90 秒后停派、首失败停止、无重试。E1/E2/GPU/云为 0。不借首批余额，不追加候选。
- 运行前等到本机 P2 释放评分窗口，结束即通知主代理释放窗口给 P1。没有因此声称整台机器独占。

冷构造外层 wall 为 `0.9638694000004762 s`，覆盖全新 Python 进程、import、图读取、guard/索引/构造、结构检查、计划落盘和退出；没有清空 OS 文件缓存。独立外部 P2 E0 为 `1.1634545000006256 s`、P3 E0 为 `2.7686234000002514 s`，均覆盖官方 CLI 启动到完整 result/trace/log 落盘退出。E0 未包括在 solver wall 内，本实现不在线择优。只各一次非独占观测，不声称稳定延迟或相对首批求解加速。

Windows/Ryzen 5600H/内存/Python 等静态机器信息复用同一 worker 在首批实际采集的 inventory，并在 manifest 写明原采集时段、原件 SHA；本次所有进程时间与结果新测，peak RSS 仍未测。预检再次逐项核对冻结清单全部 114 文件及算法/辅助源码。依赖已先前 `uv sync --locked`，准备耗时未记录；父代理此前静态链/guard/驻留分析与合成测试属于研发工作，没有计成这 1 次冷 CLI。

## 证据

`board-feed-20260924T142449Z-stages.json` 是标准 `board-submission-v1` 的 2 条实际 E0 记录。P2/P3 共享一次构造，调用总数以 `call-ledger.json` 为准；P3 配对使用这同一计划的 P2 结果。官方单核分母复用同身份的既有原件，没有新增单核调用。

原始 plan JSON、完整 result（含全部操作与 cache_events）、Trace、日志、stdout/stderr、逐调用收据、run/manifest 和 SHA 均保全。gzip 不改解压后的原字节；目录 `.gitattributes` 禁用 Git 文本规范化，保留 Windows 原始 CRLF。工作树协议预检为 `valid=true, eligible=2/2`；固定提交预检另存收据。格式/原字节通过不等于中央已接收、网页已上台或科学终验。

```powershell
.venv/Scripts/python.exe -B src/q3_yuanzhifang/stage_benchmark.py --graph-dir ../huaweicup2026/data/raw/a/official-cases/data --output results/a/q3-yuanzhifang/stages-20260924
.venv/Scripts/python.exe -X utf8 -B src/q3_yuanzhifang/stage_export.py
.venv/Scripts/python.exe -X utf8 -B src/benchmark_board/protocol.py results/a/q3-yuanzhifang/stages-20260924/board-feed-20260924T142449Z-stages.json --submission
```

已有输出目录拒绝覆盖；再次执行需要新授权预算和新目录。Windows 没有 `dot_clean`，仅对本次输出目录只读查 `._*`、`.DS_Store`、`__MACOSX`，未见残留。
