## 附录C 核心算法实现与实验复现说明

### C.1 程序源码与正文算法对应关系

各问题的算法主实现、评测上限如表 \ref{tab:appendix-1} 所示，正文伪代码与源码的详细映射关系如表 C.2 所示。

表题 {#tab:appendix-1}：问题一至问题三的固定实现版本与复现入口

| 问题 | 固定源码提交 | 模块入口 | 在线评价次数上限 |
|---|---|---|---|
| P1 | `834d8c957538ee069c66aadac9509552a4cc69d7` | `src.q1.branch_refine` | 10次E1 |
| P2 | `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f` | `src.q2_nikolastarx.adaptive_hypergap_guarded` | 3次E2 |
| P3 | `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1` | `src.q3.forest_solve` | 3次E0 |

| 算法 | 算法名称 | 源码对应位置 | 来源提交 |
|---|---|---|---|
| 算法 \ref{alg:p1-unified} | P1 统一细化流程 | `src/q1/branch_refine.py::solve` | P1，见上一表 |
| 算法 \ref{alg:p1-branch-aid} | 局部支路重分配候选构造 | `src/q1/branch_aid.py::construct` (359–438 行) | P1，见上一表 |
| 算法 \ref{alg:p2-load-guarded-cut} | 二核心负载约束超图割 | `src/q2_nikolastarx/binary_hypercut.py::load_guarded_cut` | P2，见上一表 |
| 算法 \ref{alg:p2-adaptive-hypergap} | 自适应保护超图分核 | `src/q2_nikolastarx/adaptive_hypergap_guarded.py::build` | P2，见上一表 |
| 算法 \ref{alg:p3-forest-memory-order} | 森林拓扑指标递推与遍历序列构造 | `src/q3/forest_memory_order.py::construct` (153–192 行) | P3，见上一表 |
| 算法 \ref{alg:p3-forest-solve} | 森林候选池受限在线评估 | `src/q3/forest_solve.py::evaluate_candidates` | P3，见上一表 |

表 C.2：正文各算法伪代码与程序源码对应映射关系。

正文各伪代码块系为阐释核心控制流与数学决策而提取的高层抽象，完整程序实现、模块接口与依赖环境均归档于程序附件包 `attachments/v10/source-code-v10.zip`（详见附录 E），其与表 C.1、表 C.2 标定的固定历史提交严格对应。官方代码哈希为 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，官方硬件配置哈希为 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。已有实验结果可运行 `python3 paper/manuscript-v1/scripts/export_tables.py` 从冻结数据直接导出，不调用求解器或评价器。

### C.2 问题二理论下界证书来源与校验

第 7 章中与 P2 全量方案 $U$ 比较所采用的全局下界证书 $L(G, K)$，源自固定提交 `00d311ed0eea0fd86f9840df406956041a7c192a` 中的文档 `docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md` 与生成脚本 `src/q2_nikolastarx/global_bounds.py`。该证书文件的 SHA-256 校验和为 `fe25f7b7737dbd3d841284bc5939242982613f64e0cffa9bd3d25df1f4a0c96b`，归档于数据资产 `results/a/q2-nikolastarx/goal-20260924/global-bounds.json`。

在固定复核脚本 `results/a/q2-nikolastarx/hypergap-full500-audit-20260925/audit.py` 中，该证书直接关联至新方案 $U$ 的逐用例评估数据。该下界覆盖 100 张计算图在 1～5 核下的完整 500 个评测点，是针对任意合法无死锁多核划分可行域 $\mathcal{F}_2(G, K)$ 建立的全局理论下界；其与第 6 章针对固定完整多核候选方案 $P$ 所建立的 FIFO 与依赖必要不等式下界 $L(P)$ 具有不同内涵，而附录 B.3 则属于未产生本次统计的新离线理论补充推导（不构成单核方案证书），三者概念严格分离，第 7 章的数值界限比较仅采用上述全局证书 $L(G, K)$。

## 附录E 核心算法程序附件说明

本文核心算法程序完整代码已归档至独立附件包 `attachments/v10/source-code-v10.zip`。包内收录三题固定历史提交下的源算法模块、附录 C 标定的 7 个核心算法原始及带规范声明展示副本、官方评价器与依赖源码，以及完整的 SHA-256 哈希校验清单。详细文件目录与运行环境限制参见包内 `README.md`。

本附件定位为源码审阅附件。其中问题二入口执行所需的原 Git 对象、经过认证的原生二进制文件及最终生产运行环境验证，须按 `README.md` 说明由各程序责任人独立补齐。

附录 C 标定的 7 个核心算法模块在编程实现中使用了 OpenAI 的 GPT-6 Astra（`gpt-6-astra`，2026-09-03）提供辅助支持，展示副本头部已附规范声明；此事实严格限定于上述 7 个模块，不外推至其他队友编写的源码。

