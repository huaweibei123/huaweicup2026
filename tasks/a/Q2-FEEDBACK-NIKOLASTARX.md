# A-Q2：Pro 与成绩台反馈驱动的结构构造和评分剪枝

负责人：@NikolaStarx，session=`nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894`。
分支：`codex/q2-feedback-s8ee`。原任务通道：[Issue33](https://github.com/huaweibei123/huaweicup2026/issues/33)。
本任务与 Fang 的 `src/q2/feedback` 协作；本会话只写 `src/q2_nikolastarx/` 及对应测试/证据。

1. **任务目标**：依据用户 2026-09-24 授权，在 P2/情况 B 上将 Pro 的有条件构造转为可提交算法，以官方 Makespan 和从输入到方案落盘的求解墙钟共同迭代。保留退化例和历史最佳；不把固定次数参数扫描本身当作结构算法，不接管 P1/P3 或共享 evaluator。
2. **输入文件**：未修改的 `data/raw/a/official/` 100 图、配置与源码，哈希见 source-manifest；`AI chats/` 的 Pro2/4 原文及 `docs/a/q2-nikolastarx/THEORY_REVIEW.md` 的实际阅读范围；首轮前冻结的成绩台快照 `results/a/q2-nikolastarx/feedback-20260924/board-before.json`。6 图 002/008/044/064/051/016、4 核是公开开发样本，不是 holdout。
3. **输出要求**：固定四种 from-graph 构造、成功 E0 incumbent 保护、可证分核 Pipe 工作量剪枝；独立 run 的全部候选/日志/计划/完整结果/trace、每图求解墙钟与最终 E0 墙钟、实际调用数、状态、字节数、资源和哈希；标准 board feed；方法/证明/限制文档与本任务交付记录。原件压缩映射保持可逆。
4. **限制条件**：每批单独预冻结协议，不重用旧批预算；本两批各上限30 E0、1 worker、每 E0 60秒/solver240秒/批1200秒、RSS观察停止4GiB、0重试、E1/E2=0。用户允许本机及 Colab 等可调用资源，前提不与其他 session 冲突；这两批只用本机单CPU worker，Colab未分配。官方文件只读，GitHub Actions不运行。
5. **验收标准**：首批完整公布6例及所有退化，最终计划由独立 E0 复评且完整结果字节一致；第二批验证与首批6个最终计划/结果逐字相同、保存每个跳过候选的有效下界证书，减少实际评分调用。成绩台原件接收、开发者自测、跨会话独立复核和全部100图算法终验分别记录；不以6例自测代替通用验收。
6. **截止时间**：无用户新增硬期限。本轮检查点为完成这两批有界交付及与 Fang 互通；不自动扩大到全矩阵、无限云计算或常驻运行。

## 交付记录

- 第一批 source `f17fcc2d84d20497482a1269de7bac95ab7a3138`；runner `4d9b32a19f060f408bea1b2768c16f0cd4e14a0d`；数据 `5e5d688ca473a80b7d72b26b397ce568ac70f534`。真实24在线+6最终E0，6/6完整结果字节一致；中央成绩台已确认接收6条，5格改善、002历史最佳保留。
- 第二批 source `405024df0532b72e916306399278d5ad6c2413c7`；runner `1c663e275b632cbdae73829a2b3310633362ab91`；数据 `ad94c6d945886df0e1417f367cb61af586e84e0e`，真实18在线+6最终E0，24个提案计划及六图最终计划/完整结果均与首批逐字一致；producer预检6/6 eligible。
- 实际命令、表格、资源、阴性结果和机器并发限制均在各批 `run/REPORT.md`；本地八个选择/边界测试使用手算或mock、0 E0。
- [PR102](https://github.com/huaweibei123/huaweicup2026/pull/102) 为待审算法交付。尚未完成全100图/1–5核泛化验收、跨平台复测及P2快速 evaluator 接入。
