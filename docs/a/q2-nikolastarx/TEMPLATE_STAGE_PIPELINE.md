# 同构 job 的连续模板阶段流水

`template_stage_pipeline.build(graph, cores, config)` 调用 `shared_input_wave._recognize` 的严格同构独立组件识别。该守卫要求至少两个共享 external 输入、每个共享输入在每个 job 恰有一个消费 op、组件模板签名一致、无 direct op 边或隐藏 contracted 依赖、每 eligible op 恰有一个输出 tensor 且无多生产者。模板取第一个组件的拓扑序；每个 job 按签名映射同一模板位置，并再次检查其局部拓扑。

令模板位置 `0..S−1` 的每 Pipe 工作量为该 op 的 `max(1,cycles)`。在 `k=min(cores,S)` 个非空连续段中，DP 精确最小化

`max_{stage,pipe with W_pipe>0} W(stage,pipe)/W_pipe`，

其中 `W_pipe` 是单个模板全部该 Pipe 工作量。相等时取更小前切点，故构造确定性；不按 case ID 或历史成绩选参数。前缀和及区间分数建立 `O(P S²)`，DP `O(k S²)` 时间、`O(S²+kS)` 空间（`P` 为不同 Pipe 数）。该目标只平衡模板计算工作，未计跨核 COPY、共享 DDR、500-cycle release 或官方 Step3 排队。

同一模板位置的全部 job op 归属同一核；每核按 `template position` 外层、`job` 内层输出 priority。连续切分保持每个 job 的阶段拓扑；每个共享输入的唯一消费模板位置只在一核，故该物理输入仅被该核使用。其他 private tensor 可能跨阶段搬运，其驻留峰不由工作平衡目标控制。多余核保持空 row。返回计划仅含 `node_to_subgraph` 与 `core_schedules`，并经官方只读结构校验。诊断中嵌入 `zero_spill_intervals.certify`；即使不支持或峰超容量也返回计划，不把它包装为容量安全或 Makespan 收益。无 E0/E2 调用。

`python3 -m unittest tests.q2_nikolastarx.test_template_stage_pipeline -v`：4 个合成测试通过，包括同签名同核、共享输入单核、局部拓扑、极小连续切分穷举核对、超容量仅诊断、非同构拒绝。

只读静态试跑 `case_044/046/078`、K5、官方 `config.txt` 容量 L1=524288B、UB=131072B：

| 图 | jobs×模板 op | 切点 | 构造墙钟秒 | 逐核 L1 峰值 B | UB 峰值 | 证书 |
| --- | ---: | --- | ---: | --- | ---: | --- |
| 044 | 11×124 | 0,20,49,76,108,124 | 0.057 | 47392,39808,76672,24704,47392 | 全 0 | supported/零 spill |
| 046 | 8×124 | 0,17,46,76,111,124 | 0.045 | 139552,70784,90624,70784,139552 | 全 0 | supported/零 spill |
| 078 | 8×128 | 0,17,49,79,114,128 | 0.047 | 209544,107040,178944,156192,307848 | 全 0 | supported/零 spill |

这些时间包含 Python 读入后的构造和证书，不含文件读取或官方评价；单次本机观测不能代表批量耗时。零 spill 证书仅针对受守卫的原 priority/Step2；跨阶段切分可能带来大量跨核 COPY 和较差真实 Makespan，是否有收益仍需独立官方测量。
