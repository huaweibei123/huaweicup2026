# v8 文献线索：AI chats 可见理论材料

本表只记录归档中的**候选线索**，未联网核验原论文。对照 v7 `09-references.md` 的 12 条后去重；Pro 的表述不是书目事实或论文定理。按与现稿的相关性排序，均不建议直接将所述界或性能移植为本题结论。

| # | 候选书目（待核） | 归档原文短引文与定位 | 可支撑的现稿位置与命题 | 语言、缺项和误用风险 |
| --- | --- | --- | --- | --- |
| 1 | Drobouchevitch–Strusevich；**标题缺失**；1999；[Springer 摘要链接](https://link.springer.com/article/10.1023/A%3A1018927407164)；DOI **10.1023/A:1018927407164**（仅由链接解码，未核出版页） | [P2 异构流水快照，第187行](/Users/nikolastar/Projects/huaweicup2026/AI%20chats/20260924-P2-异构流水与最优性界/完整问答-20260925T211215Z.md:187)：“针对相同的 $M_1\to M_2\to M_1$ 路径给出 $O(n\log n)$、$4/3$ 算法”；原答也声明只读摘要。 | `05-p2.md`「利用执行资源空闲区间安排计算」：理想重入流水可有结构化排序及界，作为相关工作/模型对比。 | 英文；作者名仅姓氏、标题缺失。不能写成官方双 Pipe、容量、FIFO、共享 DDR 的 4/3 保证，也不能说团队实现了该论文算法。 |
| 2 | **DAN-Scheduler: Deterministic Three-Stage Co-Optimization of Scheduling, Memory Layout, and Pipeline Overlap for General-Purpose NPUs**；作者**缺失**；2026；[arXiv:2607.17422v1](https://arxiv.org/html/2607.17422v1)；DOI **缺失**。 | [Pro4 明确理论附件，第209–213行](/Users/nikolastar/Projects/huaweicup2026/AI%20chats/20260924-Pro4-算法方案设计/附件/r03-HuaweiCup_Route4_Report.md:209)： “内存压力、布局与关键路径流水优化值得对照”。 | `01-problem.md`「核心挑战」、`05-p2.md`「同一核心内的数据复用与存储权衡」：计算并行度、存储压力和流水重叠需要联合权衡。 | 英文；与本题执行器和核内调度语义不同，不能引用其收益数值证明本题候选有效。 |
| 3 | Roorda；**Optimal Software Pipelining using an SMT-Solver**；2026；[arXiv:2601.21842v1](https://arxiv.org/html/2601.21842v1)；DOI **缺失**。 | [Pro4 明确理论附件，第221–225行](/Users/nikolastar/Projects/huaweicup2026/AI%20chats/20260924-Pro4-算法方案设计/附件/r03-HuaweiCup_Route4_Report.md:221)： “按需加入寄存器压力约束和利用 UNSAT core 解释阻塞”。 | `04-p1.md`「结构化候选方案生成与多级细化策略」或 `03-framework.md`「候选剪枝准则」：资源压力约束可作为小窗口研究对照。**现稿若不讨论 SMT，只宜放相关工作。** | 英文；作者仅姓氏。寄存器压力不是官方 L1/UB、COPY、spill 规则；不能声称现稿采用 SMT 或具备其最优性证书。 |
| 4 | **A Learning Method with Gap-Aware Generation for Heterogeneous DAG Scheduling**（WeCAN）；作者**缺失**；2026；[arXiv:2603.23249v2](https://arxiv.org/html/2603.23249v2)；DOI **缺失**。 | [Pro4 明确理论附件，第201–207行](/Users/nikolastar/Projects/huaweicup2026/AI%20chats/20260924-Pro4-算法方案设计/附件/r03-HuaweiCup_Route4_Report.md:201)： “先检查解码器能生成什么，再讨论网络更强”。 | `03-framework.md`「通用求解策略与递进关系」：可提交编码限制候选空间，作为异构 DAG 调度相关工作。**现稿不使用神经网络，不应描述为本队方法依据。** | 英文；作者缺失。其资源池、开始时间和 skip 动作不能映射为本题两字段提交或官方 FIFO/DDR 的可达性结论。 |

**中文学术文献：本次限定范围内未找到可列入书目的中文论文。** Pro4 附件有“北大/中科院/华为 2012 实验室”的中文机构说明，但 WeCAN 为英文题名、英文 arXiv 文献；中文解释、中文机构和赛题原件均不等于中文学术文献。

**筛选与缺口。** 已读项目索引、六个指定 chat 的 README 与最新完整可见快照，另检 P1、P2、P3、Pro4 已取得的明确理论附件中可检索文本。P1/P3 快照未见新外部学术书目；P2 C01 的因果性能分析 arXiv 线索对应 v7 已收录的 Coz，Pro4/P2 的 *New Tools for Peak Memory Scheduling* 也已收录。Pro4 的 REGAL、TpuGraphs/GST、AlphaEvolve 和通用框架主要关乎尚未进入现稿核心机制的学习或数据组织，暂未列入候选。若需要中文文献，须由主会话另做原始文献检索及核验；本次没有联网，也没有穷尽未选分支、折叠/删除消息和未取得原字节的附件。所有候选在入正文/书目前应核作者、标题、年份、DOI、全文适用条件及现稿是否实际陈述对应命题。
