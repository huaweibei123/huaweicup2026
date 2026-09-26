# 044 同配置 P2 结果互审：收尾顺序

2026-09-24，本会话对现存完整 result.json.gz 做零新增评价读取。两份原件为本线 `5f137e14f5bc73d123c53401737e2b5dc62e66d2:results/a/q3-yuanzhifang/stages-20260924/044/shared_stages/P2/result.json.gz`，以及P2会话 `044deba0e8d4f26514a266d9e68a9477822ba318:results/a/q2-yuanzhifang/feedback-20260924/round2/044-pipe_window_fill/result.json.gz`。后者作者为session s-eb28fa11a5664fdfbdd29b3d6e38ca24，其算法与结果不归本线。

| 指标（P2、4核） | 本线 shared_stages | P2会话 pipe_window_fill |
|---|---:|---:|
|Makespan cycles|67339|66901|
|核心0/1/2的MTE2工作及完成 cycles|62505|62505|
|核心0/1/2的M工作 cycles|20292|20292|
|核心0/1/2的M最后完成 cycles|66980|66752|
|核心0/1/2的V最后完成 cycles|67068|66796|
|核心0/1/2的MTE3工作 cycles|315|315|
|scheduled COPY bytes|3766656|3766656|
|总额外COPY bytes|2791200|2791200|
|spill额外COPY bytes|0|0|

P2方案低438 cycles（约0.65%）。此差异不是总搬运字节减少；当前轨迹中的MTE2也没有更少工作或更早结束。计算及最终COPY_OUT的释放顺序值得研究。相同总工作和结束时刻不证明每个COPY的顺序、开始时刻都相同，不能把这份审计直接升级为单因素因果实验。

P2会话另外报告已对有序mapping、分核集合及输入/config/官方源码身份做同一固定原件核对；本页亲自复核的是上述结果字段和完整timeline的汇总，未代签其所有核验。零新增solver/E0，不混入原两阶段13cold/18E0账单。

必须与P3区别：本线P3同计划为66992、核心0/1/2 MTE2为62066；这不能和对方P2的66901直接计算Cache收益。对方fill暂无本次提供的同计划P3结果，因此目前不知道它在P3是否改善。后续在明确结构守卫下研究计算收尾与首次COPY_IN并发miss，两问题分别验证，不因P2较好就替换P3现有候选。
