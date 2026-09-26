# r02 发送后的使用方勘误与接口收紧

原上传两文件固定`ceaed932e1951af00969c481e5ebc0f7d2bd1e82`；本文件追加更正，
不回写网页原提问、不称Pro在生成中已读到。本专项收到P1/P2对PR63的实质审阅后重新核源码，
当前设计已修正；完整Pro答复到达时必须据此复核，有影响再在原会话追加追问及快照。

## P1入口不能合并成一种失败语义

P1负责人s-6607指出之前自己的摘要和本brief过度概括；本专项在固定
`4dff90ef699fd51845cf482951e8477066f5f566`实际读取三段源码确认：

| 入口 | 实际行为 | 适配要求 |
| --- | --- | --- |
| search.py:183–197 | 返回非ok只记记录后继续；E1更优就先写best plan；最后另做selected和baseline E0 | 不把提前文件当已确认checkpoint；兼容时保留continue策略，复核两条路径分别留额度 |
| profile_refine.py:179–203 | 首非ok停循环；仍final E0复核此前provisional，匹配可提升confirmed，状态partial_failure | 失败不等于禁止所有final；明确provisional和confirmed及final-on-partial-failure |
| prospective_priority.py:92–118 | 非ok抛错退出，不进入final提升；正式checkpoint保留parent | 保留该错误分支与父状态 |

“默认strict=1在途”是新服务的保守提案，不自动复现上述三种行为。统一首失败停止或失败轮回滚
必须标为显式算法策略变更，不能伪装纯工程加速。原brief那句“status非ok即停止、E0确认才
发布checkpoint”对全部P1入口不成立。

## 身份必须区分候选与评价，父状态与原序号须冻结

P1/P2都指出submit例漏parent与序号绑定；P2进一步指出score→full不能被当candidate ID冲突。
修订规则：候选C绑定完整问题/输入/有序plan及parent/epoch/proposal_seq等谱系；评价操作S/F
分别绑定C、引擎/输出/purpose/成本。S与F各自幂等、独立计费；final必须新操作。
epoch有不可变父计划与父结果引用、有序清单hash、revision和封闭状态；开放轮只追加不重排。
from-graph显式parent=null。完成交付、成本证明、原序前缀确认是不同状态。
strict模式不会因为主机有空槽就突破1在途；可借用槽位必须同时符合声明cap、投机窗口和预算。

Q3在[5e8726e审阅](https://github.com/huaweibei123/huaweicup2026/blob/5e8726e646a711691a4f60f9a0ecc826f17ab536/docs/a/q3/CONCURRENT_DESIGN_REVIEW.md)
进一步指出结果字典也需按operation_id，P2/P3配对不能覆盖；当前设计已改。
同生成提议可关联两个problem候选，原序窗口按proposal计、执行并发按evaluation计，
K−1个越过提议可能有更多E0，必须按操作费用求和；Q3单候选直接official_full可用，
不强制native预评分。epoch同时冻结objective/tie-break/决策模式。

## 数学和官方目标表述

- 原brief“成本约束部分理想”更正为**价格加权部分理想（代理最小割）**。
  `release_ideals.py:155–221`精确最小化
  `denominator * cutbytes - numerator * positive_additive_work`，另有upper/forced closure。
  没有求硬cutbytes预算下工作最大化；有限价格不覆盖所有Pareto或所有预算最优。
- “5～10分钟为佳”的脚注直接修饰官方Q1。Q2/P3也要求稳定高效，本队沿用完整耗时设计口径；
  不能写成官方对三问分别给了相同范围。无论哪题都不把它当600秒硬门槛或必须跑满的目标。

本更正为0评价的源码/契约复核。原Pro材料的证据和本更正各有版本，后续归档README需显式链接，
避免读者只看原brief继承过度概括；Pro建议、当前草案与实际接口仍分开验收。

## 路由审计与父阶段停止域（本轮后续补充，尚未发给Pro）

LYX固定09eef20静态审计及本专项有限复核支持603b074单请求条件上界：P1完整E1≤1，
P23本问题完整E0≤1。两者分账；E1不能被E0=0掩盖，冷失败两轮prep也不等于两个完整E0。
外层STARTED/route不证明完整函数进入；中断actual未知仍保留上界预留，调用方truth/final/
重试另计。仍无公开fallback前拒绝协议，审计不是实际服务或驱动总量证明。

Fang Stage B父stage只有一个active case×method unit；unit即experiment，epoch是unit内
候选轮，final操作仍属该unit。父控制器核验原stop_after_unit语义、完整回执及清理后，
才持久放行下一unit；特定baseline拒绝只挡同case，其他意外失败停止stage。
每experiment一个在途不足以保证旧父stage停止；祖先许可必须进入派发事务。新条文未实现，
也未被既有10项单层模型检查覆盖。详见当前设计与ROUTE_COST_REVIEW.md。
