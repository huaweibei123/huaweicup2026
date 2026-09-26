# 021 / 3 核：同计划 CacheGain 小于 1 的固定证据

本页只审阅 `c2d628ba0fe8dce4630e5f9c0a5c8fb810fcd41a` 统一算法的 **021/k3**。方案计划固定 SHA-256 为 `13362774572585a30167aed18b9929d52f1962390d05fafb3dc4dbd318a098c4`，图为 `d1b1b8a543eab9b359421f0d67baaee43f2890b2562bf2bfa1dfeb5fa5f87b37`，配置为 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`，官方 code 聚合身份为 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。P3 原始 feed 与 plan/result/receipt 位于固定提交 [`130dfe4c6a10d394a6d04257f660d5a66c51c624`](https://github.com/huaweibei123/huaweicup2026/tree/130dfe4c6a10d394a6d04257f660d5a66c51c624/results/a/q3-nikolastarx/witness-full500-20260925-s59/20260924T2032Z-s59ee)。本次只从该 feed 选取 021/k3，并核对该单格 plan/result/receipt 原字节 SHA；没有抽取其他499格、重新求解或运行 E0。

| 对照 | 无 L2 的 P2 | 只读 Cache 的 P3 |
|---|---:|---:|
| Makespan，模拟周期 | 2,140,720 | 2,140,863 |
| 同计划 CacheGain = P2/P3 | \- | **0.9999332045** |
| 比 P2 增加，模拟周期 | \- | **143** |

P2 数值及同计划绑定来自固定提交 [`27409658d869671d30e940f536bbab30d50d3ef9` 的审计摘要](https://github.com/huaweibei123/huaweicup2026/blob/27409658d869671d30e940f536bbab30d50d3ef9/results/a/q3-nikolastarx/cachepair500-feedback-20260925/summary.json)：021/k3 行明确记录上述 plan SHA、P2 压缩结果 SHA `e7b6d54df96bca81730c7dadc8b59a65d988da75476be81ea0b550e4f4dad3c6`、P3 压缩结果 SHA `f6e460a78209a37b3edb003692efd590378687e4efa7575b286dfa0245c2edb5` 及两个 Makespan。该目录 README 说明 P2 是 s59 对同一批 P3 计划另做的500次官方评估，审计核了逐格绑定。**本次也取得 P2 原件**：固定提交 [`19bebf35205d23fdd832781540f8879da52eeb62`](https://github.com/huaweibei123/huaweicup2026/blob/19bebf35205d23fdd832781540f8879da52eeb62/results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/cache_pair/021-k3/result.json.gz) 中的后续复用拷贝，其 gzip **原字节 SHA 与旧 c2 配对摘要完全相同**，Makespan 也为2,140,720；这不是把新 forest 算法的计划或结果替换进旧配对。P3 feed 的 021/k3 行为 `scene=B`、`problem=3`、`read_only`、3 核、2,140,863 周期；计划及 P3 压缩结果实字节 SHA 与摘要吻合。同计划身份由旧配对摘要的 plan SHA 与旧 P3 实物 plan SHA 绑定，P2 复制件由完整压缩结果 SHA 回接旧摘要。

逐操作按 `(core_id,task_id,op_id)` 对齐后，**两端 8,881 条操作的身份、op 类型、subgraph、pipe 和各核每 pipe 的列表顺序均相同**；三核 `COPY_IN` 各为1284、1285、1245条，`COPY_OUT` 各为387、388、372条，总计3814次读入、1147次写出。官方 `data_movement_bytes` 五项也逐字段相等：`scheduled_copy_bytes=39,993,344`、`added_copy_bytes=36,655,104`、`spill_added_copy_bytes=31,944,704`（其余见小审计 JSON）。所以这个反例**不是增加 COPY 数量或官方计划搬运字节**；两端每核合并 timeline 列表顺序并非完全相同，不能误说跨 pipe 的实际交错不变。P3 Cache `COPY_IN` 命中681次、未命中3133次，命中字节3,692,544、未命中字节22,206,464，命中率0.1425747272；`cross_core_transfers=[]`。

在这个单格的两份原始 timeline 中，按最早的任一端时间戳寻找变化：最早**完成时间差异**是核2/task2/op `1000004905` 的 `COPY_IN`，两端均从4956开始，P2于5163结束（207周期），P3命中 Cache、于4973结束（17周期）；这是先加快的读取。最早**开始时间差异**是同核/task2/op `1000006255` 的 `COPY_IN`，P2从5163开始、5472结束，P3从4973开始、5281结束。每核合并 timeline 首个可见列表换位按较早开始时刻定位在核2、列表索引29：P2 的 op551 从6708到9804，P3 同位置为 op `1000005175` 从6329到6536；这是跨 pipe 合并列表的观察，不是 Pipe FIFO 次序改变的证明。两端 7485 条操作起点不同、7808 条终点不同、2392 条自身历时不同。

固定审计 [README](https://github.com/huaweibei123/huaweicup2026/blob/27409658d869671d30e940f536bbab30d50d3ef9/results/a/q3-nikolastarx/cachepair500-feedback-20260925/README.md) 报告的最早**同起点但服务变慢的 COPY_IN**，本次已独立定位为核0/task0/op `1000006089`：两端均从443077开始，P2于443146结束（69周期），P3走 DDR、于443215结束（138周期）。这一事实与 Cache 改变事件交错/共享 DDR 服务时间的机制**相容**，但该事件发生在大量更早的时序差异之后；不能把它单独解释成末端143周期退化的完整因果链。需要原始依赖、资源争用和最终关键路径的逐边分析才可做更强归因。

复现脚本与小摘要：[audit_021.py](../../../results/a/q3-yuanzhifang/cache-counterexample-021-20260925/audit_021.py)、[audit.json](../../../results/a/q3-yuanzhifang/cache-counterexample-021-20260925/audit.json)。从仓库根目录执行 `python results/a/q3-yuanzhifang/cache-counterexample-021-20260925/audit_021.py`；脚本从自身位置推导根目录，只读固定 Git 对象，不复制大结果、不调用 solver/E0。路径差异本身不改变源身份：P2 是后续交付里的**同字节复用拷贝**，P3 是旧 c2 原件。此页可作为同计划 CacheGain<1 的实证反例和“搬运字节不变而时序变”的观察；它不证明完整的143周期因果链、全部500格或真机性能。
