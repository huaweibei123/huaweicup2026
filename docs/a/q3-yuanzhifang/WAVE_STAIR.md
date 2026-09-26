# 首波容量阶梯：研究构造入口

`src/q3_yuanzhifang/wave_stair.py` 把 `tail_stair_model` 的纯计算次序变成官方两字段计划。它只生成一个候选，不按 E0 选优、不扫切点或波次参数、不使用预制的 067 数值。任何同构、形状、容量阶梯或拓扑守卫失败都会显式报错，**不**返回可评分的 fallback。

一次冷 CLI 调用从 Python 启动、读取原图与配置开始，依次完成 `SharingIndex`、严格 `structure/model`、两遍尾段切点 DP、逐位置 `β`、`U_c`、`h+c` 阶梯、尾操作优先的首波及余作业均衡波次、零额外跨核 lag 的 compute/FIFO 必要界、canonical singleton 映射、`derive_multicore_plan` 静态校验，最后才落盘计划并在 stdout 输出元数据。输出 JSON 仅含 `node_to_subgraph` 与 `core_schedules`。元数据含 `guard=true`、`selected=wave_stair`、作业与核数、切点、每核 M/V 周期、模型下界和完整 `stair_model` 细节。P2/P3 的外部官方 E0、资源成本和完整端到端墙钟须由后续冻结 runner 单独计量；本入口内部 Step/E0 调用为零。

CLI 形式：

```powershell
uv run --no-sync python -B -m src.q3_yuanzhifang.wave_stair <graph.json> --cores <k> --config <config.txt> -o <plan.json>
```

这仍是结构家族开发候选。逐位置 `W/A/F` 容量和零 lag compute/FIFO 最长路只是代理与必要界，不是 Step2 零 spill、官方 Makespan、DDR 或 Cache 结果的证书。R2 文档中的数字也不是本入口本机测量。当前只在小合成图上验证实际 derive、两字段 singleton 覆盖、尾操作首波优先，以及不适用结构明确拒绝；**尚未执行真实 067 冷构造或 E0**。旧 `tail_phase_model` 的前缀相位构造与本首波阶梯不同，不能混用其测量或身份。
