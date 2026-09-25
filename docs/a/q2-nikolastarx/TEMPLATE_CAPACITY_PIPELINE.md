# 容量约束的 job-major 模板流水

`template_capacity_pipeline.build(graph, cores, config)` 保留 `shared_input_wave._recognize` 的严格同构独立 job 条件，按模板拓扑序切成连续段。同一模板 op 在所有 job 固定同核；核内按 job 外层、段内模板位置内层执行。它与原 stage-major 构造是两个显式 API，不自动选成绩或回退。

对区段 `[a,b)` 和池 `p`，`S_p` 是本区段被消费的全部共享 external 物理输入字节和；`P_p` 是一个 job 的 private tensor 在区段内各 op 首末 touch 闭区间的峰值（DDR 在 P2 映为 UB）。`S_p+P_p≤capacity_p` 是 job-major 原 priority 的零 spill 充分条件：共享输入在整段所有 job 间至多驻留一次；不同 job 的 private 物理 tensor 互不相同，而核内 job 块不交叠。共享 input 每 job 恰一个 anchor，因而若 job 数至少 3，中间任一 job 执行时，所有本段共享输入已被首 job touch、仍须供末 job 使用，整段都驻留；这时峰值恰为 `S_p+P_p`。两 job 时该式可能保守。证明只在 recognizer、singleton、无 logical_tid/隐藏 COPY 路径等证书守卫均成立时适用。

固定左端 `a`，右端逐 op 扩张。private tensor 第一次 touch 于 `b`，在线段树加 `[b,b]×size`；已有末 touch `l` 再 touch 于 `b`，加 `[l+1,b]×size`。共享输入首次出现时加入 `S_p`。由此预计算所有区段上界，时间 `O(S·I·log S)`，空间 `O(S²+I)`，`I` 为单模板 tensor touch 次数。随后 DP 仅允许两池上界都合格的段，优先使用最多 `min(K,S)` 个非空段，并在可行切分中最小化各段归一 per-Pipe 工作最大值；时间 `O(KS²P)`、空间 `O(KS+S²)`。无可行切分明确报 `UnsupportedStructure`。生成方案后再用独立 `zero_spill_intervals.certify` 核对，不一致则拒绝。

`python3 -m unittest tests.q2_nikolastarx.test_template_capacity_pipeline -v`：2 项合成测试通过，逐区段用独立闭区间枚举核对上界，三 job 与证书峰值相等，容量不可行时拒绝。只读静态构造 K5，容量取官方 `config.txt` 的 L1=524288B、UB=131072B（秒数不含文件读取）：

| 图 | 切点 | 构造秒 | 逐核 L1 上界/证书峰值 B | 证书 |
| --- | --- | ---: | --- | --- |
| 044 | 0,22,53,71,105,124 | 0.145 | 12768,291072,516480,119040,9856 | 零 spill |
| 046 | 0,20,53,71,108,124 | 0.129 | 30048,301440,517632,129408,27136 | 零 spill |
| 078 | 0,49,56,63,72,128 | 0.118 | 367992,499968,499968,499968,373512 | 零 spill |

三图 UB 均为 0。容量可行仅说明原 priority 的 Step2 零 spill，未建模跨核 COPY、500-cycle release、共享 DDR 或 Step3 排队；尤其 078 的中间窄段说明工作平衡受到容量强约束。没有运行 E0/E2，不能声称 Makespan 或吞吐改善。
