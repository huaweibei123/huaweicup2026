# Q3 对共享并发设计 v1 的接口核对

被审版本：`9f8fa68b031d14579d77f105ae5052078d3be9e2`，Draft PR63。
实际读取完整 `CONCURRENT_EVALUATION_DESIGN.md`、`PRO_R02_RESEARCH_BRIEF.md`，
以及 `NEEDS_AND_EVIDENCE.md` 中相关需求、同提交 `OFFICIAL_OBJECTIVES.md` 出处。
对照本方 `EVALUATION_PROFILE.md`、`EXPLORATION_FEEDBACK.md`。
仅文档/接口核对，0新增评价、0模型测试，不是共享服务或算法验收。

## 接口定型前需要消除的身份歧义

设计第4节L82–96的示例只显式传candidate_id并用`results[record.candidate_id]`收结果，
同时把problem/engine/输出表示纳入完整身份，规定candidate_id重用但内容不同即冲突。
L118又允许同计划P2/P3配对；L90/104允许之后取official_full。

Q3具体场景：同一提议x先P2 score，再P3 score，再对该计划P3 official_full。
若三项共用candidate_id=x，现示例会覆盖结果，身份冲突规则也可能拒绝后两项；
若每项都改candidate_id，则候选谱系、去重后的提议序号和“候选数”含义需要另给字段。
这不是指实现已经有bug，而是当前文字不足以唯一决定合法客户端行为。

建议明确两层：proposal/candidate身份描述生成出的计划；evaluation/operation身份描述
一个problem×engine×输出层级×调用槽的具体执行，pair_id只关联匹配计划的P2/P3操作。
结果按operation_id保存或按candidate_id下的操作子键保存；同operation_id重传只查询，
新官方复核/独立重复必须新operation_id并独立扣费。可采用其他命名，但必须规定作用域。
计数同时区分提议数、评价请求数、按problem的实际/潜在E0次数；投机窗口也要说明按哪层计。
K−1个被越过的提议不自动等于K−1次E0（一个提议可有配对或复核操作）。

## 两处需补入具体契约的接入约束

1. 需求文档和研究brief提到parent，但第4节请求示例/完整身份列表没有明确parent plan hash。
   建议epoch引用不可变manifest，含parent hash（直接构造明确null）、objective/tie-break/
   决策模式/提议有序清单。评分数值缓存与研究谱系可分层，不要求所有谱系字段都进入编译键。
   仅epoch整数不足以发现调用方无意换了parent或选优目标。
2. Q3当前一次官方验证即完整在线路径。需明确支持从同一资源入口直接发
   `official_full`/E0，圈存并消耗1次最终额度，不强制先native score再做第二次E0。
   现设计原则能容纳它，只需写清；否则薄适配可能增加无用评分和固定开销。

## 研究材料的出处范围小勘误

`PRO_R02_RESEARCH_BRIEF.md` L13–17面对三问统一描述“官方推荐5～10分钟”。
同提交 `OFFICIAL_OBJECTIVES.md` L17–18明确：原题第5页脚注1直接修饰问题1；
Q2/Q3共同采用这一效率目标属于团队口径，题面没有在两问另列该硬时限。
建议补齐这句范围。无需因此打断已在途Pro或重启长研究，后续归档/必要追问携带短更正即可。

## 已对齐的范围

Q3单候选不凑批、聚合score与少数逐事件诊断分开、P2不硬筛P3、未知成本不退款、
完整有序计划/场景隔离、每个候选重新初始化模拟FIFO，以及20次旧额度封存均正确保留。
strict与显式投机停止契约分开、完成未确认仍占窗口也符合有限探索需求。
这些是文档方向的匹配，不表示10项控制面模型证明真实进程、预算持久性或性能正确。

## 修订核对：文档问题已解决，运行验收仍待完成

随后实际读取 `aa3649cad9c2b46bca70f3f43314752ccaa37875` 相对被审版本的设计/勘误/模型范围差异：
operation_id结果键、分问题候选与proposal/pair关联、score/full独立操作、按proposal的窗口与
按evaluation的在途/费用计数已明确；epoch冻结parent/result、objective/tie-break与清单revision，
Q3可直接一次official_full，官方5～10分钟的出处范围也已更正。上述Q3文档层意见已解决。
新README明确原10项模型只覆盖每proposal一个操作，多操作分组/费用/前缀确认尚未检查。
本次不运行模型或评价，也不把文档修订提升为真实服务、适配器或性能验收。
