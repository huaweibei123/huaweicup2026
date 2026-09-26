# P3 输入共享构造首批实测

本批没有降低 P3 Makespan 的候选。008/037/044 与本机 baseline 持平；080 的 shared_order、shared_place 分别退化 183、273 cycles。保留全部改善、无变化和退化证据，不用 P2、搬运或命中率替代 P3 主目标。

- 算法：`8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6`；实际 runner：`39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0`。
- 本批 UTC：`2026-09-24T14:09:46.620762Z` 至 `2026-09-24T14:10:56.184972Z`；驱动批 wall 69.56425709999985 秒，含本批哈希预检、环境采集、构造、外部复评、证据压缩和收尾，不含后续 feed/报告发布。
- 实际 12 次全新 Python 进程构造、8 个不同 plan、16 次未修改官方 E0（P2/P3 各 8），均成功。E1/E2/GPU/云、重试为 0。未耗剩余额度，未追加实验。
- 预算：1 worker、每调用 30 秒、批 600 秒、550 秒后停派、最多 12 构造/24 E0、首失败即停。600 秒是本批保护预算，不是题面淘汰线。
- Windows 11，AMD Ryzen 5 5600H，物理内存 17024741376 B，Python 3.12.14。完整硬件、锁文件及线程约束在 `manifest.json`；未测 peak RSS。主机非独占，不声称跨机器速度收益。

| 图（4核） | variant | P2 cycles | P3 cycles | P3 额外搬运 B | P3 spill B | P3 字节命中率 |
|---|---|---:|---:|---:|---:|---:|
|008|baseline|63768|63768|0|0|0|
|008|shared_order / shared_place|同 baseline plan|同 baseline plan|0|0|0|
|037|baseline|53852|53852|614400|0|0|
|037|shared_order|同 baseline plan|同 baseline plan|614400|0|0|
|037|shared_place|53852|53852|1024000|0|0.5671052631578948|
|044|baseline|91922|70261|4179744|1388544|0.32948412200326344|
|044|shared_order|同 baseline plan|同 baseline plan|4179744|1388544|0.32948412200326344|
|044|shared_place|91922|70261|4179744|1388544|0.32948412200326344|
|080|baseline|112445|83124|4419584|229376|0.5910290237467019|
|080|shared_order|108757|83307|4190208|0|0.6411290322580645|
|080|shared_place|87353|83397|2805760|1155072|0.3538156590683845|

037 增加命中率而 Makespan 不变，并增加额外搬运；080 shared_order 提高命中率且消除 spill，P3 仍退化；080 shared_place 降低静态入口并集和总额外搬运，P3 仍退化。这些现象支持继续审查真实 COPY 完成时刻、Cache FIFO 与计算关键路径的耦合；静态输入聚集不能单独证明主指标改善。因果机制留待逐事件分析，本表本身不证明具体瓶颈。

## 计时与去重

每个 variant 各冷构造一次，外包进程 wall 从启动前到写出计划并退出，包含 import、读图、结构分析、构造和结构检查。范围为 0.7100400999997873–3.3141882999998415 秒，12 次总和 17.760307599999578 秒。这里“冷”只指全新 Python 进程，没有清空操作系统文件缓存；每种只观测一次，不估计稳定 P50/P95。

外部 E0 的配置/图/plan读取、模拟、完整 result/trace/log 落盘和退出单独计时，范围 1.033907399999407–4.454379099999642 秒，16 次总和 30.020737400000144 秒。其余批时间为预检/硬件采集/压缩/调用账等成本；不是隐藏在线评分。算法没有实现在线择优，事后最好成绩不能配成单候选的求解墙钟。

同图 plan 原字节去重：008 三构造相同，037 与 044 各自 baseline=shared_order，080 三者不同。4 个别名的实际构造时间仍在 `summary.csv`、`manifest.json` 和 `call-ledger.json`；别名不另造 E0 调用或正式 feed 记录。037/044 shared_place 虽同分，计划字节不同，所以确实各评价一次。P2/P3 两条 feed 记录共享一次构造，不能重复累加其中的 solver calls；总调用以独立 ledger 为准。

## 证据与复现

`board-feed-20260924T141108Z-unique-plans.json` 含 16 条实际 E0 记录。每条引用本提交内 plan、完整官方 result、运行收据、Trace、日志、manifest；P3 `cache_pair` 指向本批相同 plan 的 P2 结果。单核分母复用已核冻结身份的 `results/benchmark-board/official-singlecore-20260924` 原件，没有重跑单核。

所有官方结果保持 `scene="B"`；P3 另保留 `problem=3`、`cache_mode="read_only"`。result 包含全部 operations、cache_events、诊断与搬运字段。result/trace/log/stdout/stderr 的 gzip 解压后逐字节等于实际输出，压缩和原始 SHA、大小均在收据。plan 保留未经重写的官方两字段 JSON。

输入只读引用相邻主工作区；冻结 `source-manifest.json` 的 114 个文件（含 100 图）逐项核 SHA 与大小，通过后开始调用。复现命令如下；本批产物目录已存在时 runner 拒绝覆盖，复跑必须获得新批预算并使用新目录。

```powershell
.venv/Scripts/python.exe -B src/q3_yuanzhifang/benchmark.py --graph-dir ../huaweicup2026/data/raw/a/official-cases/data --output results/a/q3-yuanzhifang/pilot-20260924
.venv/Scripts/python.exe -X utf8 -B src/q3_yuanzhifang/export_feed.py
.venv/Scripts/python.exe -X utf8 -B src/benchmark_board/protocol.py results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json --submission
```

工作树协议预检 `valid=true, eligible=16/16`；固定提交预检另存收据。格式/字节校验不是中央已接收、网页已上台、独立复跑或算法终验。本子代理继承研发上下文，不是盲审。覆盖仅 4 个公开开发图、4 核，不是官方全部 100 图、1–5 核最终成绩。

首次数据提交 `bbc59188bbcfa04dc295434b644d0ee7e99d7552` 的固定预检发现 Git 把原始 Windows CRLF 规范化为 LF，计划哈希不匹配，`eligible=0/16`。原始工作树字节始终保留；本目录随后使用 `.gitattributes` 的 `* -text` 并重新收录原字节，未更改算法/计划语义、未重跑，也未按提交后的 LF 反改实测哈希。失败收据 `protocol-precheck-bbc59188.json` 保留，最终通过收据另列。

父代理报告之前做过两次静态 build_variant 结构/去重预检及两组合成结构单测，属于研发开销，不计为本批 12 次冷 CLI，但不能据此宣称此前没有构造工作。依赖准备 `uv sync --locked` 在本批前完成，耗时未记录；无离线训练或编译。

Windows 无 `dot_clean`；仅对本次输出目录只读扫描 `._*`、`.DS_Store`、`__MACOSX`，没有发现残留。没有删除仓库外内容。
