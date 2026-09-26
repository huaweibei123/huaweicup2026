# 固定计划计算—门控下界：两轮反馈

1. **目标**：从32份已有P1计划解释质量退化，区分划分/核序限制与仍可能优化的执行开销。不是新算法成绩或全局最优性证书。
2. **输入**：Stage A @9b07b791cbbb950410d56d2c8c02407fde013982 的24份、Stage B @0441891f60b07a456a0f21ed74a024987edd8cd9 的8份feed及完整原件；冻结图/config/十份官方源码。
3. **输出**：`stage-a-bounds.json`、`stage-b-bounds.json`保留逐行计划/结果哈希、身份、原始观测指标、最长下界路径和计算/门控拆分。实现与实际分析HEAD/源码哈希在各JSON中。
4. **限制**：0 solver/E0/E1/E2，未重新评估、训练、改计划或选择新候选。无内存/DDR成本，不宣称该下界可达。
5. **验收**：固定Git feed字节与本机一致；计划/完整result/config/图/官方源码哈希一致；32行下界均≤对应E0；相关反例单测通过。下界≤E0是有限一致性检查，不是一般正确性的替代证明。
6. **交付**：随Issue98研究PR交付；不生成board attempt，避免静态数字被当作方案成绩。Windows无dot_clean，仅扫描本目录元数据。

对固定合法计划，每个Task的计算时长下界取以下两项的最大值：该Task内单Pipe总工作量；保留的内部计算依赖最长路。普通操作使用max(1, cycles)，冻结配置每核每Pipe一个slot。原COPY会被删除，因此内部边仅保留原直接计算边或原tensor连接的计算边，不穿越被排除COPY收缩。Task间依赖与核序来自官方derive/validator，跨核真实依赖边权1000；核内相邻Task边权100；同核非相邻数据依赖0。同一对节点多个限制取max。以上边/节点加权DAG最长路即固定计划下界。Task完成门控保证其前驱的所有工作已结束，故不把同时发生的多个等待相加。此结论适用于冻结P1语义，没有扩展到P2/P3。

| 已有计划 | E0 cycles | 固定计划下界 | 其中路径门控cycles | 对研发的含义 |
| --- | ---: | ---: | ---: | --- |
| 001 component/chain | 58984 | 58200 | 0 | 当前计算下界已很近，低优先级继续微调 |
| 002 chain | 88110 | 69008 | 7100 | 仍有差距，但队长已回报更好的树前沿构造 |
| 044 chain | 135220 | 71525 | 48000 | Task过碎与搬运同时存在，不能只看spill |
| 051 chain | 324823 | 271472 | 119000 | 重点研究释放前沿，不能把119000视作可全消除 |
| 048 switch→chain | 362034 | 335812 | 246300 | LB已大于fixed64的226990，需改变划分/核序 |
| 071 switch→chain | 43499 | 31321 | 25400 | LB已大于fixed64的21586，搬运改进不足以反超 |

该Task下界不约束其他划分的最优值。JSON另列所有方案通用的纯计算Pipe工作量/k弱下界，它不包含必要COPY；不能和固定计划下界混称全局界，也不能替代官方单核分母。048/071的不可胜结论仅针对保留当前Task图和核序的执行改进。修改计划后旧下界不再适用。

更正来源：队长 `170132b127d632237a93101bea80456053f38e50` 的Q1_LOWER_BOUNDS.md所述COPY桥反例；父会话诊断64d8b66在未发布静态结果前修复为1e3b6bd，并重新生成两份输出。两批E0结果与构造器均未改变。

成员本机接收另存 `member-board-readback.json`：父会话对既有52341服务进行GET只读逐ID复核，32/32记录均eligible且artifacts_checked，提交指标及冻结身份与两份feed逐字段一致。成绩台另派生baseline_speedup，不要求整个metrics对象与提交前完全相同。本回执既不生成新attempt，也不代签中央接收、重新E0或科学验收。

008补充时间线反馈见 `008-pipe-overlap.json`（0新评分）：各核component方案M62532/V59292，M/V重叠0；chain方案重叠8952，却新增12026880 B搬运，E0从123060升至248154。求交公式直接作用于完整官方 `per_core_timeline.ops` 的start/end，不用局部预测时刻。增加重叠仍可能被DDR/门控代价抵消；该统计不能独自证明Step1某个特定选择是唯一原因。

复算只读取已有证据；输出使用不存在的新文件，不能覆盖本交付：

```text
uv run python -X utf8 -B src/q1_yuanzhifang/analyze_feed.py results/a/q1-yuanzhifang/stage-a-20260924/board-feed-20260924T141300Z-stage-a.json --artifact-commit 9b07b791cbbb950410d56d2c8c02407fde013982 --output output/q1-analysis-a-NEW.json
uv run python -X utf8 -B src/q1_yuanzhifang/analyze_feed.py results/a/q1-yuanzhifang/stage-b-20260924/board-feed-20260924T143000Z-stage-b.json --artifact-commit 0441891f60b07a456a0f21ed74a024987edd8cd9 --output output/q1-analysis-b-NEW.json
```
