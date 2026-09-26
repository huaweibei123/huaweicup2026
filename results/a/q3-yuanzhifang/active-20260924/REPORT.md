# 044 请求4核、解析选择2个活跃核

本批未修改官方配置和核数：请求 `cores=4`，最终方案含4个 `core_schedules` 条目，两个有工作、最后两个为空；官方P2/P3原件均返回 `num_cores=4`。算法按资源公式选参与核心数，**不是改为请求2核再混入4核成绩**。

官方 **P3 Makespan=44185 cycles**，相对上一阶段全4活跃核同层交错66992降低22807（34.04436350609028%），相对首批baseline70261降低26076（37.11304991389249%）。同计划P2=44234。

|指标|初始 baseline|4活跃核 shared_stages|本次2活跃核 active_stages|
|---|---:|---:|---:|
|请求核数|4|4|4|
|P2 cycles|91922|67339|44234|
|P3 cycles|70261|66992|44185|
|总额外搬运 B|4179744|2791200|930400|
|spill B|1388544|0|0|
|Cache 字节命中率|0.32948412200326344|0.007025400840996889|0.0015122166717640262|

本次官方 `scheduled_copy_bytes=1905856`、`partition_added_copy_bytes=930400`，P3 hit/miss bytes=`2848/1880480`，COPY_IN hit/miss count=`9/102`；字节命中率继续下降，不能宣称所有指标同时严格改善。各核官方L1峰值为 `98560/94464/0/0 B`，UB均0。空核减少输入复制份数，计算工作集中，实际效果由这一次完整E0证据体现；未证明所有图上都有同样收益。

## 选择机制与适用范围

算法 `bb7a7e8702b636a0a9dda33d070daad5f4d7c212`，`src/q3_yuanzhifang/active_stages.py`。guard要求同构独立串行链、共同输入及一致的按位置访问签名。对最多请求核数个直接算术模型计算 `max(compute_pipe_load, all_miss_zero_spill_copy_service)`，只构造其中选中的一个计划；没有试运行时间线，没有E0找参与核数。

本次r=1/2/3/4的模型cycles为 `74404/40584/47360/62890`，选择r=2（compute=40584、all-miss COPY service=31830）。**这些是选择候选的启发模型，不是P3全局下界或最优性证明**；未实测其他r，也没有授权外的扫描。

## 实际成本与预算

- runner固定 `bf2ecc35bc8acc935b5db6bec00158f6c1ae1474`，复用冻结 `39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0` 的进程/压缩辅助函数。
- T0=`2026-09-24T15:17:20.874119Z`，T1=`2026-09-24T15:17:27.615491Z`；批wall `6.741844199999832 s`，包含114文件核验、证据收尾等，不包括后续报告/feed发布。
- **实际1次冷构造+2次E0，全成功**；0重试/E1/E2/GPU/云。独立预算1worker，单次30s/整批120s/90s后停派，首失败即停，不借前两阶段余额。
- 冷构造外包进程wall `0.4380230999995547 s`：启动、import、读图/配置、索引/guard、最多4个公式、构造/结构检查、计划写入、退出。公式计算在该计时内。
- 外部P2 E0 `0.8179044999997132 s`，P3 E0 `1.5596452999998291 s`：完整官方CLI启动、输入/配置、模拟、全部result/trace/log写出与退出。它们未包含在solver wall里，没有在线选优。

运行前发现P2工作区有用途未知的Python stdin进程，先未启动；随后只读CIM复查确认其与父代理静态分析进程均退出，再运行本批。仅说明当时未观察到其他项目评分进程，不声称整机独占。Windows5600H机器静态inventory引用本会话已采集原件及时间，Python3.12.14，1worker；峰值RSS未测，没有清空OS缓存，单次观测不足以声称稳定效率提升。

## 可审计产物与比较限制

`board-feed-20260924T151739Z-active.json` 含2条真实E0记录，`cores=4`，另在parameters及run写 `active_cores=2`；P2/P3共享唯一构造，调用总数以ledger为准。P3配对本批同计划P2；单核分母复用已核身份的044原件154407，得到本次单核相对加速比 `3.4945569763494397`。

若只把15:11读取的中央签名快照中044/k4的66992替换为44185，保持另外99格不变，4核历史最优100图均值会从 `3.22233971527293` 变为 `3.2342367120724886`。这是离线条件计算，**不是本次结果已经中央接收，也不是单一算法全量跑出的均值**；仍未达到图1作者报告4.09。其他图/核数、同计划P2全覆盖及严格最优界限仍待研究。

完整官方result/cache_events/逐操作timeline、Trace、日志、stdout/stderr、原始plan、逐调用账、run/manifest与哈希均保存；gzip解压原字节可核，目录 `.gitattributes` 禁止Git改换行。工作树协议预检 `valid=true, eligible=2/2`，固定提交预检另存收据。源码、图和config按清单再次逐项核验114文件；本子代理不是盲审，格式/字节通过不等于算法终验。

```powershell
.venv/Scripts/python.exe -B src/q3_yuanzhifang/active_benchmark.py --graph-dir ../huaweicup2026/data/raw/a/official-cases/data --output results/a/q3-yuanzhifang/active-20260924
.venv/Scripts/python.exe -X utf8 -B src/q3_yuanzhifang/active_export.py
.venv/Scripts/python.exe -X utf8 -B src/benchmark_board/protocol.py results/a/q3-yuanzhifang/active-20260924/board-feed-20260924T151739Z-active.json --submission
```

已有目录拒绝覆盖。Windows无`dot_clean`，仅对本批输出只读扫描AppleDouble/`.DS_Store`/`__MACOSX`，无残留。未操作其他人的结果目录。
