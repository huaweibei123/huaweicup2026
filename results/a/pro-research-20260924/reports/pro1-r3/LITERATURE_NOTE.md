# 本轮文献使用范围

本轮以实现和反例为主，不重复R2长综述。

1. Tao Yang, Apostolos Gerasoulis. **DSC: Scheduling Parallel Tasks on an Unbounded Number of Processors**. IEEE Transactions on Parallel and Distributed Systems, 5(9), 951–967, 1994. DOI: 10.1109/71.308533. UCSB作者机构报告1994-12： https://cs.ucsb.edu/research/tech-reports/1994-12 。本轮再次读取机构页面的题名、作者、日期、摘要；没有把摘要列出的特例或近似保证当已阅读全文复证。背景是无界、完全连通处理器，不能把结论移植为本题2–5核保证。引用用于承认已有DAG聚类思想，不用于证明本轮原型质量。

2. François Baccelli, Guy Cohen, Geert Jan Olsder, Jean-Pierre Quadrat. **Synchronization and Linearity: An Algebra for Discrete Event Systems**. Wiley, 1992, ISBN 0-471-93609-X. R2中已有实际阅读与固定时延闭包推导，本轮复用该理论背景。新原型的3×3矩阵推导与随机子模型核对在RESEARCH_MEMO和test_math.py；本轮没有再宣称全文重读，也没有把它升级为公平共享DDR/FIFO Cache的线性模型。

3. R2中的有向超图划分、参数最大流、内存剖面/窄边界DP文献仍是研究背景。本轮只把其中理想集最小割代理做了正式图构造试验，并得到不优先推进的证据。没有复用其近似因子为本题定理，没有新增未经核实文献。
