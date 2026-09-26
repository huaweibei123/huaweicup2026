# P2 固定方案的理想模型下界 R5

本会话 `yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24` 新增独立模块 `src/q2/feedback/ideal_bounds.py`，不改已冻结待试的R4源码或构造入口。实现用于解释固定方案及研究廉价候选准入，尚未成为新的求解算法成绩。

## 已实现量与范围

对固定singleton方案B，在唯一原producer、无logical alias及R4已有整数数值域下，计算基础DDR服务和W、逐核逐Pipe eligible工作量P、真实tensor/direct依赖最长路径D，以及增加同核同Pipe相邻eligible FIFO弧后的最长路径D_FIFO。各跨核真实边权为两次COPY独占服务加固定等待，同核边权为0；多个输入和并行弧取max。最终取 `L_B=max(W,P,D_FIFO)`，同时保留物理路径D供诊断。

这是**固定方案、理想精确服务模型、成功执行条件下**的必要界。分核、FIFO、跨核COPY都依赖B，换成其他方案后这些工作和等待可以减少，故本量**不是全局最优Makespan的下界**，不能把`M/L_B`写成全局最优性gap。浮点退役、事件投影和成功返回仍需另外核验；未凭测试宣布机器严格证书。

根会话已阅读两份Sol审阅及对应冻结源码：[物理关键路径](CRITICAL_PATH_BOUND_R5_REVIEW.md)、[FIFO顺序与环边界](FIFO_LOWER_BOUND_R5_REVIEW.md)。原COPY链收缩的可达边不能直接当实际物理等待；同核不同Pipe的优先顺序不能整体串行化。同Pipe相邻eligible的0 lag弧来自Step2保持原op子序列、Step3固定逐Pipe投影及全局cursor在完成后推进。加入FIFO后重新拓扑检查，必要依赖有环则拒绝给有限下界；无环仍不证明完整E0成功。

数值诊断元数据`contracted_pairs_without_physical_arc`统计端点对的差集，不是被排除COPY路径数。Sol窄审指出旧命名可能混淆两者，已更正并注释。同核direct不再计算无用的COPY服务。复用service_profile已经完成的官方计划校验，避免同一函数再重复derive；这项减少调用不等于已实测求解器提速。

已有索引与计划验证后，物理弧构建、Pipe投影及两次拓扑最长路径扫描为O(V+E+I)，FIFO新增弧至多V，辅助空间同阶。服务统计的按核tensor对及官方计划验证、TensorIndex的构建/排序成本另计；不能把扫描复杂度称为整个求解器端到端复杂度。

## 与队长已有方法的关系

本轮随后实际补读固定c665下的 [fifo_bound.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/fifo_bound.py)、[FIFO_BOUND.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/FIFO_BOUND.md) 与 [global_bounds.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/global_bounds.py)。队长已有同一D_exec/FIFO计算先后的必要下界及COPY收缩反例；该部分是已有团队成果，不把本次独立推导/实现当作首次发现。已有global_bounds还包含不依赖分核的不可分工作量与head/tail窗口界，不能用R5的固定分核量替换它。

R5在本会话适用域内另计基础DDR工作W，并对真实跨核边加入COPY独占服务与500-cycle等待，形成带通信权的候选路径诊断。这个增强引入DDR浮点语义缺口，所以比现有纯计算FIFO证书的结论更有条件，尚未证实在真实图上比它紧多少或能省掉多少评分。未来集成应先核对此增量是否有用，避免同时维护两套相同的计算FIFO原理；本轮未修改队长模块或其证书。

## 检查与后续诊断

新增8项手算/反例检查，联同R4/F1为19项通过：509周期tensor路径及并行direct取max、504周期多输入汇合、不同Pipe不串行、原COPY链不产生假lag、同核传输无lag、FIFO把509加强到511、四节点跨核/FIFO等待环拒绝，以及别名/多producer/数值域拒绝。均0真实图构造、0 Step2/Step3/E0。Sol medium先做FIFO窄审（软预算4500 tokens），再做实现窄审（软预算3000）；未使用Astra、未递归；软预算不是工具级已核算token账单。

`results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/probe.py` 准备对100个已保存五核tensor/F1方案对做静态核验，核对图、配置、计划与结果哈希、基础COPY字节；记录理想界是否高于已有E0、旧/新判据能触发哪些保存方案对及容量证书。它不构造新方案、不调用Step2/3/E0，也不将事后选择保存方案的分数拼成新的算法均值。输入已用于研发，不能称留出或盲测。

P2核查03:15:54.4062372Z本人0评分进程且R4未START，并给P1暂让资源。P1随后回报03:16:57.6324379Z其RAM门未通过、0solver/0E0且释放窗口；P203:19:05.3946213Z实查空闲1163673600 B。静态诊断仍需派发时复核资源，实际结果另补，未运行前不预报增益；R4真实评分仍按原Issue33排程，不复活已封存预算。

实际派发结果：Luna在03:21:28.5870923Z的一次入口读取仅有366104576 B，低于本次静态扫描768 MiB门（805306368 B），故probe启动0次、T0/T1为空、无report.json、无重试。源固定为`1acc50a7f8290fd98fa94a12113281728705d7ca`，程序SHA为`48cc32c52b10059510e23ad5495226c4764e221960d3738c63a1ac955a98a8bd`；[去个人路径的入口收据](../../../../results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/preflight-stop.json)记录原始收据SHA。本次没有100对静态结果，更没有新增官方成绩。不能把几分钟前可用内存较高当作实际入口已通过。

已实际读队长协调 [Issue33 #5826046123](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5826046123)：当前没有释放的共享主机窗口或R4评分T0，继续保持007/020/045固定三格包，准入与唯一派单齐备前不启动。该消息不影响上述零评分方法/材料工作，也不新增实验预算。

## 第二个静态窗口的完成结果

以上“没有100对结果”是第一次入口停止时的历史状态，不覆盖或撤销该收据。第二窗口在 2026-09-25 03:31:13.9200251Z 实际检查到可用内存 2930335744 B、本人匹配评分进程为空，源/程序哈希一致，随后运行一次静态 probe。T0 为 03:31:13.9620654Z，T1 为 03:32:57.0028234Z，退出码 0；程序内诊断耗时 102.5018218999976 s，不是求解器端到端耗时。

完整 [report.json](../../../../results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/report.json) 的 SHA-256 为 `53d102dbe6ce461cae05f110cee01cb6949c45370b283e91dcd4492fded4db0a`，配套 [完成收据](../../../../results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/completed-receipt.json) 记录原始外部收据/日志哈希；仅去除个人日志路径并将重复嵌入的全量 report 字符串缩为 summary，原 report 字节未改。

100 对保存五核方案共计算 200 个条件界，没有发现条件下界高于保存 E0 的数值矛盾；这不是通用机器证明。R4、R5 的触发集合均为 020/022/029/044/045/057，新增 R5 触发为零，触发保存方案对无退化。因此本次不能主张加入路径项已提高筛选收益，也不据此把 R5 接入主线。所有输入已参与研发，不称留出或盲测；0 新 solver/Step2/Step3/E0/E1/E2，没有新统一算法均值，R4 真实试验仍未启动。

用户随后将本会话调整为跟进算法与写 P2 论文。本结果只用于章节研究边界，当前不新增算法实验；[P2 初稿](../../../../paper/sections/a-q2.md) 和 [证据索引](../../../../paper/sections/a-q2-evidence.md) 随固定方法与验证证据继续修订。
