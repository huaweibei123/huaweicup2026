# Q2：强核分配上的次序构造小实验

负责人：NikolaStarx，session `nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894`

分支：`codex/q2-structure-nikolastarx`

沟通：[Issue33](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5805084900)

1. **任务目标**：问题2/B。检验 Fang 的 M1 胜者与已有 critical32/singleton 次序组合是否改善，再用全 ready critical 与计算管线最早开始构造作有限对照。目标是官方 Makespan 与完整求解 wall；不把低代理分数当最优或执行合法性证明。
2. **输入文件**：冻结官方 cases ZIP、config 和 P2 源码；Fang 固定 `0b58c123cccf02fc993b741d79dcd8511e4dd38f` 的 002-M1、044-M1、044-M2 原计划。公开开发例002/044，四核，不是保留测试集。既有最佳002=72415、044=69113是作者报告，先复核。
3. **输出要求**：自己的 src/tests/docs/results `q2_nikolastarx` 目录；原始输入哈希、计划、完整 E0 result/trace、账本与报告。固定 op-core 和有序 mapping 键；singleton 候选间也固定子图编号。复现入口 `python -m src.q2_nikolastarx.pilot OUTPUT`。
4. **限制条件**：新独立预算，不使用 Fang 或旧共同机制余额。首批最多13次 P2 E0：两 M1 父计划与044 M2标杆共3次，2图×4次序=8次，2图赢家各1次确认。单worker、每次30秒、整批计算与机器报告180秒，末60秒不启动评价；首失败/基线不符即停，无重试。完整人工分析和Git发布另记，不假称180秒内。无 E1/E2/P1/P3；固定原件，不改 Fang 代码。候选生成采用确定性规则，seed不适用。
5. **验收标准**：关键结构守卫与复制/顺序测试通过；官方输出成功，基线数值复核，赢家完整结果复跑一致；如无改善也保存反例及成本。不以两图验证泛化或最优性。整个实验是强种子局部改进，不是从图直接生成完整优质解的端到端算法。
6. **截止时间**：本轮接手会话完成一个可复核检查点（Asia/Taipei）；运行T0由程序记录。

## 交付记录

首批已完成：`results/a/q2-nikolastarx/joint-20260924/REPORT.md`。as-run `73e40f6`（完整SHA见protocol），13/13次P2官方CLI、4项结构测试通过；002从72415到72056，044保留69113。两赢家完整JSON复跑相同。源、输入、输出与预算证据见同目录；所有额度已封存，无在途实验。

命令：`.venv/bin/python -m src.q2_nikolastarx.pilot results/a/q2-nikolastarx/joint-20260924`。测后报告由 `python -m src.q2_nikolastarx.report <目录>` 重建，无评价。结果属于两图强种子的局部开发检查点，不能称完整求解器或普遍优于Fang；PR链接由任务Issue发布。
