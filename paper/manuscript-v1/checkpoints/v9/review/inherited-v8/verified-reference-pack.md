# v8参考文献核验与作者使用范围

核验时间：2026-09-26。现稿12项中有1项中文赛题、11项英文材料，尚无中文学术论文。有限Pro可见归档中的中文学术线索未检出；这不是对隐藏推理或未归档内容的穷尽结论。中文两篇是本轮直接从期刊核实的补充，不能写作来自Pro。只使用可见回答、附件和公开来源，不提取隐藏推理。

以下编号为Markdown稳定引用键；PDF按首次引用自动编号。条目是否入稿由论述需要决定，不能为了数量堆砌，不声称复现或采用这些论文的全部算法。

## [13] AutoConfig（中文，新增核查）

张洪滨, 周旭林, 邢明杰, 等. AutoConfig: 面向深度学习编译优化的自动配置机制[J]. 软件学报, 2024, 35(6): 2668–2686. DOI:10.13328/j.cnki.jos.007102.

期刊原页：https://ebook.xml-journal.net/rjxb/2024/06/files/basic-html/page92.html 。实际核到书目与首篇摘要。可支持静态信息与动态开销结合、减少自动调优搜索开销的背景；本文提交自由度只有分组/分核/次序，没有实现AutoConfig的代码生成。适合03章相关方法定位，1–2句足够。

## [14] TVM算子生成加速（中文，新增核查）

高伟, 李帅龙, 茆琳, 等. 一种基于TVM的算子生成加速策略[J]. 计算机工程, 2024, 50(8): 353–362. DOI:10.19678/j.issn.1000-3428.0068182.

期刊原页：https://www.ecice06.com/CN/10.19678/j.issn.1000-3428.0068182 。实际核到书目、摘要及正文入口。基于代价模型和预定义规则裁剪Ansor调度空间，可用于说明候选选择既关注输出性能也关注搜索成本。本文未训练其梯度提升模型，也不改变算子内核，不移植其性能数字。

## [15] HEFT（新增核查）

TOPCUOGLU H, HARIRI S, WU M Y. Performance-effective and low-complexity task scheduling for heterogeneous computing[J]. IEEE Transactions on Parallel and Distributed Systems, 2002, 13(3): 260–274. DOI:10.1109/71.993206.

原论文全文：https://disco.ethz.ch/courses/fs14/seminar/paper/Jochen/4.pdf 。可支持异构DAG任务调度中优先级与最早完成时间的经典方法定位。本文并未声称直接实现HEFT；静态任务成本不等同于本题动态DDR仲裁、有限容量与FIFO事件模拟，不能援引它保证本文算法最优。

## [16] 两机重入车间（Pro可见材料线索，已核期刊）

DROBOUCHEVITCH I G, STRUSEVICH V A. A heuristic algorithm for two-machine re-entrant shop scheduling[J]. Annals of Operations Research, 1999, 86: 417–439. DOI:10.1023/A:1018927407164.

期刊页：https://link.springer.com/article/10.1023/A:1018927407164 。仅摘要可见，不声称阅读全文。原文处理M1→M2→M1两机重入模型，报告O(n log n)、4/3近似界。可在03章方法适用范围中解释理想机器次序模型与本题多Pipe/共享DDR/有限存储的不同；4/3界不得转移到本队算法。线索原文：AI chats/20260924-P2-异构流水与最优性界/完整问答-20260925T211215Z.md:187。

## [17] LATTICE（Pro旧名线索，锁定新版）

LIU R, PEI M, DING F, et al. LATTICE: Constraint-Directed Scheduling, Memory Planning, and Pipeline Refinement for NPUs[EB/OL]. arXiv:2607.17422v3, 2026-08-04[2026-09-26]. https://arxiv.org/abs/2607.17422v3 . DOI:10.48550/arXiv.2607.17422.

作者原预印本及HTML：https://arxiv.org/html/2607.17422v3 。可支持执行次序与存储规划相互影响、存储可行性不能对任意重排保持的背景。旧Pro附件写DAN-Scheduler，核为同号v1旧题名；本次锁v3的题名与结论，不混合版本。原线索：AI chats/20260924-Pro4-算法方案设计/附件/r03-HuaweiCup_Route4_Report.md:209–213。本文自由度不同，不能暗示实现LATTICE或使用其数据。

## 暂不入稿线索

- Optimal Software Pipelining using SMT（arXiv:2601.21842）：VLIW循环模调度与当前提交自由度较远；未实现SMT，不为数量硬加。
- WeCAN（arXiv:2603.23249）：学习式DAG生成；本文未实现或比较其学习器，不硬加。
- 中文《深度学习编译优化技术综述》2026优先出版：查到书目信息但未可靠取得完整原页，本轮不引用其具体结论。

建议作者在03章用一个短小方法背景段/小节串起调度、存储与求解成本三项关系；正文现有超图割与树内存引用继续保留。五篇各自承担不同的确切论述，禁止凑成无关长综述。
