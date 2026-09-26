# Stage F 结果与复现

## 固定来源与调用

仅真实 051/k5 一次；作者算法 `916a19e57c041ca5dc4aa1f3748e23726464b762`，runner/exporter `2b79198675838415baee96ccca64e81067ff6781`。数据、config、十个官方源、四个作者依赖均在启动前严格核对原字节 SHA-256。C 的 051/k5 原件固定于 `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a`。未修改作者源码、官方源、原始数据或既有成绩；未训练、搜索候选或复跑旧单核/旧 C。

唯一新 solver 与外部 E0 均正常退出；诊断确认 star 构造、263 Tasks、R=166540。官方两字段计划通过冻结 E0 的依赖/核序/容量处理。官方结果、完整 trace、text log、stdout/stderr、diagnostics 和原始运行收据全部保全；result/trace 无损 gzip，压缩与解压 hash 在原 run 中。空 stderr 表示进程未输出错误，不替代独立复跑。

本批 1 solver、1 E0、0 E1/E2、0 retry；没有失败被删除或补跑。预检与静态结果分析不调用求解器、Task 编译器或官方评价。独立复跑和全100其他核验不在这份单例预算内。

## 质量与墙钟分开

| 项目 | Stage C 051/k5（既有） | Stage F 051/k5（本次） |
|---|---:|---:|
| E0 Makespan / cycles | 253856 | 325520 |
| R 构造计算+gate值 / cycles | 180644 | 166540 |
| E0 减 R / cycles | 73212 | 158980 |
| Task 数 | 144 | 263 |
| 调度搬运 / B | 9438614 | 15599090 |
| 总额外搬运 / B | 9045396 | 15205872 |
| spill增加搬运 / B | 0 | 0 |
| 冷 solver wall / s | 1.0622996 | 1.2007275 |
| 本次独立 E0 wall / s | 未重跑 | 2.0575621 |

单核基准607628周期仅引用已核官方原件；本次单格单核加速比约1.866638，旧 C 约2.393593。单例不是100图平均，不能用于声称已达到用户新的2/3/4/5核均值目标2.19150/2.83820/3.42710/3.90660。

共享窗口 token 记录 P1 E4 实际结束 `2026-09-24T17:14:10.325759Z`，P2 5C 结束 `17:08:34.117251Z`；P2 后续可最多2 worker共享运行。本 P1 始终1 worker。父 START 时报告 FreePhysicalMemory=2467896 KiB，这不是本进程峰值采样。CPU/总RAM/解释器/锁文件/线程配置在 protocol；peak RSS 未监测。两批墙钟直接列出，不声称程序加速或独占测量。

shell 在启动 runner 前记录 UTC `17:16:08.2171036Z`；随后 runner 做源码/输入/原件预检及环境记录，这些准备未作为算法求解时间。正式批次 T0 `17:16:28.123478Z`，T1 `17:16:31.674371Z`，批次3.5507643秒。solver 启动 `17:16:28.126209Z`、退出 `17:16:29.330723Z`，perf_counter计完整冷进程1.2007275秒；包括读图、守卫、构造、官方结构检查、R诊断、两字段方案与诊断写出、进程退出。外部 E0 结束 `17:16:31.425756Z`，耗时2.0575621秒，另列且未进入 solver。OS文件缓存未清空。

## 负结果的结构反馈

对两个固定计划调用已冻结 `trace_c.boundary_metadata`，只重建官方 Task 边界 COPY 的静态条件；不调用 Step1/2/3。逐 tensor/direction/size 聚合其出现次数并作 F−C 差分，得到：

- 32768B COPY_IN 增加94个、3080192B；COPY_OUT 同样增加94个、3080192B。
- 2B COPY_IN 增加46个、92B。
- 合计增加234个边界 COPY、6160476B，与官方新增搬运差完全一致，spill=0。

共有94个32KiB重链中间 tensor 新跨Task边界；它们的双向写出/读入新增6160384B。其余23个2B tensor 各多两个输入加载，共92B。12个原始32KiB输入在两种计划中均各进入24个 Task，重复外部输入仍9043968B。新增切链没有改善旧方案的主要外部输入重载。

F 固定分区的必要 DDR 工作字节为15599090，冻结带宽60 B/cycle，因此 `ceil(15599090/60)=259985>253856`。逐 COPY `max(1,ceil(size/60))` 服务和为261133周期。仅前一个更保守的字节容量界已经足以排除该固定分区击败 C 的可能。它是固定方案的必要资源界，不是所有分区的通用下界，也不能将观测退化71664周期逐周期归因于 DDR。

理论R里减少14104周期是有效的模型改进；E0却增加71664周期，说明忽略新增大tensor切口会选错当前候选。下轮构造可优先约束大tensor跨Task切口、减少重复外部输入，或把边界搬运纳入结构候选的必要成本。此反馈不授权新增实验，也不证明未切链是一般无损限制。

## 复现入口

以下是已执行逻辑的可重现入口；不得在已有本批目录覆盖重跑，新的真实评分需新的明确预算与窗口。

```text
python -X utf8 -B src/q1_yuanzhifang/benchmark_f.py --graphs GRAPH_DIR --execute --window-token PARENT_START_REFERENCE
python -X utf8 -B src/q1_yuanzhifang/export_f.py --graphs GRAPH_DIR --output results/a/q1-yuanzhifang/stage-f-20260925/board-feed-20260924T171730Z-stage-f.json
python -X utf8 -B src/benchmark_board/protocol.py results/a/q1-yuanzhifang/stage-f-20260925/board-feed-20260924T171730Z-stage-f.json --submission
```

实际 solver/E0 argv、cwd、UTC、参数、timeouts 在原 run 中；window-token 原文在 protocol。导出器只分析已有原件。COPY差分的完整117个 changed tensor 明细在 `run/copy-delta-analysis.json`；复算方法为对 C/F 的 `boundary_metadata(graph,plan,60)[0]` 分别统计 `(tensor,direction,bytes)` 的 Counter，对所有键计算 F−C，再按 `(bytes,direction)` 求次数差与字节差。该静态差分没有改动官方结果。

官方5–10分钟是效率建议，不是600秒淘汰线；本轮30/90/180秒为冻结预算。所有成功与负结果都会保留，格式 eligible 不意味着维护者已上台或完成科学验收。
