# Stage G 051/k5 结果

## 冻结身份和实际调用

作者 `e29685da0268420f2d881246603763d6bf8baf5b`，实际runner/exporter提交 `902000f6504f5c23e566f02d434a176ec9e83ceb`。相对66f4559只更正任务卡中的数学措辞，未改任何作者算法或runner。启动时核对五个算法依赖、十官方源、051图、固定config与旧C原件；完整SHA-256见 `run/protocol.json`。

唯一冷solver返回 `selected=intact-prefetch-frontier`、144 Tasks、R208152；唯一未修改官方E0成功，输出合法官方两字段方案及完整结果。调用为1solver/1E0/0E1/0E2、0retry，无失败被删或补跑。计划、诊断、result/trace/log、全部stdout/stderr、run/events均保存；result/trace经无损gzip并校验压缩/原始字节hash。静态分析和成绩台预检另为0评分，不改原件。

既有对照仅使用 `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a` 中 C 的051/k5；未重跑。官方单核607628周期也只读取已核原件。不是盲测或全图试验。

## 实测表

| 指标 | Stage C（既有） | Stage G（本次） |
|---|---:|---:|
| E0 Makespan / cycles | 253856 | 234536 |
| 官方单核比 | 2.393593 | 2.590766 |
| R 计算+Task门控 / cycles | 180644 | 208152 |
| E0减R / cycles | 73212 | 26384 |
| Task数 | 144 | 144 |
| 调度搬运 / B | 9438614 | 9438614 |
| 总额外搬运 / B | 9045396 | 9045396 |
| spill增加 / B | 0 | 0 |
| 冷solver wall / s | 1.0622996 | 0.5056320 |
| 本次外部E0 wall / s | 未重跑 | 1.4357794 |

本次Makespan降低19320周期（7.6106139%）。共享资源条件没有控制为同一实验，因此两次solverwall只并列，不据此宣称程序效率翻倍或已形成严格墙钟Pareto优势。本单格仍不能证明达到全100图2/3/4/5核均值目标2.19150/2.83820/3.42710/3.90660。

## 时间与资源

父授权token `parent-s-bdf7e1f4-20260924T1755Z-shared-stage-g-1plus1`；P1 E4/F均已结束，P2可最多2worker共享，本P1始终1worker，无独占保证。父最近报告free RAM2262240KiB；不是本子进程峰值采样。CPU、总RAM、Python、uv.lock、线程配置在protocol；peak RSS未监测。依赖复用既有 `uv sync --locked` 环境，没有新增训练或预计算。

冷runner启动前shell记录 `2026-09-24T17:55:39.3307212Z`，之后是源码/输入/旧证据预检和硬件清单。正式批次T0 `17:55:51.560790Z`，T1 `17:55:53.758253Z`，2.1977067秒。solver起止 `17:55:51.562790Z` / `17:55:52.071310Z`，perf_counter完整进程wall0.5056320秒；包括导入、读图/config、守卫、构造、结构校验、R诊断、plan/diagnostics落盘及退出。外部E0结束 `17:55:53.537714Z`，1.4357794秒，未混入solverwall。OS文件缓存未清空。

本轮30/90/180秒是冻结实验预算，不是原题硬淘汰线；官方5–10分钟为算法效率建议。

## 同工作量，不同执行时间

对C/G两个固定计划使用 `trace_c.boundary_metadata` 静态重建Task边界COPY，不调用Task编译器或任何评价。按 `(tensor,direction,bytes)` 统计多重集，二者完全一致，各1003个COPY；静态边界字节与各自官方搬运字段相符。12个原始32KiB外部输入仍各进入24个Task，重复外部输入均为9043968B。

字节容量必要下界均 `ceil(9438614/60)=157311`。冻结官方先以 `_op_duration=max(1,ceil(bytes/60))` 初始化COPY的剩余服务量，再使活跃COPY共享总服务容量1，所以逐COPY独占服务量的总和158251也是必要Makespan下界。它不是精确E0持续时间，不指定独占执行顺序，不能与gate路径直接相加。任务卡此前“只允许字节界”的过强措辞已在启动前修正。

G保留大tensor内部链并改变根核负载与尾核位置，R多27508周期，E0却少19320周期。总DDR工作量相同并不意味着发射时刻、公平共享、依赖和计算重叠相同；静态compute/gate+总DDR代理可能错排这两个计划。本次实测支持将该结构候选纳入后续研发比较，但没有唯一归因于提前预取，也没有证明其他图都获益。完整trace已保全，未在这份单格交付中额外展开因果分析。

## 复现和验收边界

以下入口用于固定源码下复核；已有输出目录拒绝覆盖，新的真实评分需新预算和窗口：

```text
python -X utf8 -B src/q1_yuanzhifang/benchmark_g.py --graphs GRAPH_DIR --execute --window-token parent-s-bdf7e1f4-20260924T1755Z-shared-stage-g-1plus1
python -X utf8 -B src/q1_yuanzhifang/export_g.py --graphs GRAPH_DIR --output results/a/q1-yuanzhifang/stage-g-20260925/board-feed-20260924T175725Z-stage-g.json
python -X utf8 -B src/benchmark_board/protocol.py results/a/q1-yuanzhifang/stage-g-20260925/board-feed-20260924T175725Z-stage-g.json --submission
```

实际argv/cwd、源码哈希和运行范围在原run/protocol。静态COPY多重集与服务量对照见 `run/copy-signature-comparison.json`，方法是对已有两计划的 `boundary_metadata(graph,plan,60)[0]` 聚合 `(tensor,direction,bytes)` Counter，并对 `solo_service_cycles` 求和；这不是另一次模拟。

Windows dot_clean不可用，仅在本结果目录扫描 `._*`、`.DS_Store`、`__MACOSX`。成绩台格式/证据预检不等于维护者接收、页面上台、独立复跑或科学验收。本子会话不直接写中央服务，也不扩大后续评分预算。
