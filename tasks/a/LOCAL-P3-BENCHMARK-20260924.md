# 本机 P3 在线构造 benchmark

执行会话：`nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc`，来源[Issue #26登记](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5814790103)。

1. **任务目标**：固定P3结构选择构造，运行100图×1–5核的500个真实求解格，每格构造并内置调用一次冻结官方P3 E0，保留与队友重复格供交叉复核。
2. **输入文件**：`a4e7ee13310d693ec4fb5cc236669ceb3b172d1f`的`src/q3/solve.py`及其依赖，冻结100图/config/官方源码。官方源码聚合哈希见批次清单；官方单核分母复用PR #89，不重跑。
3. **输出要求**：`results/a/local-p3-20260924/20260924T1331Z-s59ee/`中逐格plan、完整官方P3 result.json.gz、Q3原收据、外层run、批次账和`board-submission-v1` feed。无P2同计划无Cache配对时CacheGain为NA；P3 Makespan及字节Cache命中率仍可验。
4. **限制条件**：先001/002×1–2核2 worker，再同两图3–5核4 worker，之后其余98图×1–5核8 worker。每进程≤180秒，整批自T0起≤30分钟；不额外再调用E0，不重试，不换方法，低于8GiB可用内存不启动新格。
5. **验收标准**：500格状态明确；成功格的冻结身份、P3 scene B/problem=3/read_only、核心数、原result和plan/run SHA一致；严格协议预检`eligible=500`。这不等于独立复跑或证明Q3算法最优。
6. **截止时间**：T0=`2026-09-24T13:31:54.680Z`，最后一格=`13:35:07.951Z`；500/500成功，后续P1另批。
