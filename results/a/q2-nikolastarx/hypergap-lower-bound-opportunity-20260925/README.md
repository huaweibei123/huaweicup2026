# 已完成子集的必要下界核对

2026-09-24T23:44:13Z 的运行中快照包含 125 项，其中 K5 为 25 项。核对既有数学下界证书、官方源码、逐图身份与固定单核分母；未构造候选、未调用评价器、未重算证书。125 项均满足 M≥LB。

`summary.json` 是只读核对结果，保留输入 SHA；本地目录前缀已替换为 `<local-home>`。下界原理及实现见 `docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md` 和 `src/q2_nikolastarx/global_bounds.py`。这不是全100图成绩或独立可达性证明。

M/LB 大可提示优先诊断的结构，但当前下界放松了传输和容量限制，B/LB−B/M 不是预测提升。M/V 两类流水线的负载不能直接相加作为单一容量。后续 trace 诊断另存 `hypergap-timeline-diagnostic-20260925`；应据因果证据设计候选，再由 E0 验证。
