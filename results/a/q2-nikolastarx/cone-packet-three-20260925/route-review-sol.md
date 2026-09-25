# Cone packet 三图保存证据复盘

只读对照本目录与 `output/shifted-packet-three-20260925-v1/results.zip` 的 ledger、proposal、candidate、E0 原件；未构造或评分。两批各 26 次 native E2、3 次独立 E0，均无 fallback。

| 图/K5 | 旧 E0 M | shifted 胜者 | cone 胜者 | 对照 |
|---|---:|---:|---:|---|
|005|33515|33436|33436|胜者 plan SHA 与 E0 result SHA 逐字相同|
|069|11962|11849|11801|再降 48 cycles；added DDR 均 321938 bytes|
|071|9465|9394|9394|胜者 plan SHA 与 E0 result SHA 逐字相同|

005 的八个 cone packet 均只在一个旧核上，packet 数与 shifted 相同；071 虽有跨旧核 packet（如 5、8、6 节点），胜者仍是 ordinal 7 的同一双节点方案。**事实是候选空间扩大却未改两图的最优已试候选；为何没有更好解不能由这八个样本证明。**

069 胜者 ordinal 2 的 cone packet 为 24 个旧关键原操作，来源核 3 有 21 个、接收核 4 有 3 个，故实际迁核仅 **3 个**（151–153）。与 shifted ordinal 2 的三个迁核操作相比，五核操作集合/分核完全相同，只有核 3 优先序不同（279 个操作中 74 个绝对位置改变）；scheduled COPY 字节与 added DDR 不变。E0 中 151–153 时刻仍为 5560–5596；核 3 后续 154 等操作提前，而核 2→1 tensor 0494 的 release/start 从 10695 提前至 10647，核 1 最终 M 同步提前 48。**推断：**收益来自同一分核上的优先序/竞争传播，并非多迁了 21 个节点或减少总 COPY；保存结果不足以唯一归因到某一条 DDR 竞争或 FIFO 边。

`critical_packet_exchange.py:149–160` 的 cone 仅沿原始 `DAGIndex.succ` 且属于旧 critical original IDs 的后继扩展；prepared Step3 内存复用边、M/V FIFO 边和跨核 COPY→release 门槛没有参加闭包。因此它不能保证包含所有实际紧约束后继，也可能把已在源核的原 DAG 后继纳入 packet，只改变插入顺序。现有三图结果不能推出该闭包足够或不足够；它只是一个受限构造域。

**无需新评分的证伪检查：**用已保存的旧 E0 `per_core_timeline`、native `critical_original_ids.op_ids` 与原图边，逐个列出这些关键计算操作在同 Pipe 时间序列中的相邻对；统计其中源在 cone、目标在 cone 外且原图无直接边的对。这能找出被原 DAG 闭包遗漏的 **可能** FIFO 见证；归档没有完整 prepared 关键链及 Step3 内存边，不能仅凭邻接确认紧性，更不能补造内存边。三图仅一个胜者变化，当前证据支持停止扩大同类 cone 评分，而非自动全量 500。
