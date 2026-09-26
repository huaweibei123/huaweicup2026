# P2 gap_packet 全 500 格补齐计划

根会已选定统一候选 `384b6c2a7ff937ca44180dee09a9d4bcaea0c50d` 的 `python -m src.q2.feedback.construct --strategy gap_packet`。`chain_dag` guard 自动进入 join-gap 或 capacity fallback，方法描述沿用冻结 spec。runner 为 `fa6522a3266fe040379dd064092beb27c0b20a5e`，官方 E0 为 `45f647b395b84e9569f418fd33d62c2b8eb4d190`。既有29个gap格全部完成并审计，相对固定tensor_packet有28项官方Makespan改善、1项相等，同时保留DDR增加和050二核新增spill。这是优先补齐本候选的依据，不能据此宣称全量改善。根会批准按固定提交补齐471格；实际启动由各Luna流水线按资源门控执行。

矩阵为 5 核 × 100 图。round11a/k4、round11b/k1、round11c/k5、round13a/k2、round13b/k3 的29格已核对相同source、统一入口、配置和参数，保存run/plan/result哈希及原solver墙钟；其固定算法测量原样纳入矩阵，不重复评分，不复用capacity-only或tensor_packet成绩。其余471格按核数和case顺序分15批，每批不超过33格；优先完成k2/k3。计划详表及两条流水线的分片分工见 [`gap-full500-plan.json`](../../../../results/a/q2-yuanzhifang/feedback-20260924/gap-full500-plan.json)。

每批 1 worker，最多 2 个 P2 worker 并行；派发前 free memory 须 ≥1.5 GiB，不足则只在批次边界等待。每批 900 秒、solver 30 秒、E0 90 秒、收尾 15 秒、零重试、首个意外失败即停，maxcalls 等于图数。总上限 471 solver / 471 E0。

成本背景：e647全500为501 solver/500 E0；早期R1/R2/R3为28/26；33格机制批为33/33；后续24格机制批已完成24/24，另有两次批次slug预检拒绝、0 solver/0 E0。新增471格各生成一次方案并独立官方复评，原29格已经是同一程序版本的测量。固定spec提交由运行收据或根会START记录，不在同一提交内自引用。本文冻结时，新增471格尚未启动。

依据用户模型预算要求，两条执行流水线均用GPT-6 Luna、medium，短上下文及约6000 tokens/流水线的软预算；工具没有硬token限额或逐代理精确用量，不能声称硬控。遇明确脚本/语义错误停批交根，执行代理不临时改算法。根会实际已读模型预算规范 `0a97785fae0df0354424c5d760914c7c9ae2d3ac` 对应新增节。通用保存原件审计入口为 `src.q2.feedback.audit_batch`，已用既有round11b的3例/6份gzip/23291操作时间线做只读验证，0新增评分。
