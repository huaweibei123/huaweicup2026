# Pro r02 研究材料：三问的并发算法探索机制

2026-09-24；由三问共享evaluator专项汇总。以下是本机已读代码/既有结果与使用方反馈，
不是本轮Pro实测。用户新问题：并发探索的变量怎样构造、怎样筛选和演化、怎样可靠高效，
以及怎样有依据地覆盖潜在好算法。**请优先研究这层机制，不只回答进程池怎么开。**

本轮接续同project的“研究评估器加速方案”会话，扩展到P1/P2/P3。旧r01对原生精确重放的
建议已用于研发，不需从旧E2的约25%误差重新出发。本轮仅静态研究/设计，不运行正式图评价，
不改源码或冻结契约，不创建云实验。可请求当前会话缺的最小材料，不假设其他聊天附件可用。

## 目标和真实决策对象

给定原始图JSON、1～5核和官方配置，算法输出仅含node_to_subgraph与core_schedules。
首要目标为官方E0 Makespan（模拟周期）；兼顾新增搬运，P3另报按字节Cache命中率。
从读取图到合法计划落盘的实际solver墙钟、CPU、内存是另一条轴；在线评分/回退/E0复核均算入。
官方推荐避免暴力迭代，单用例5～10分钟为佳，不是硬600秒淘汰线，也不是应当跑满5分钟。
本队追求更好质量、更低墙钟；离线算法研发的大量探索不等于最终在线solver允许暴力搜索。

需要区分：
1. 算法机制族/代码/条件参数的离线研究；
2. 某个固定算法在一个输入上生成和选择计划的有限在线过程；
3. 评估服务执行这些作业的资源调度。
线程数/候选次数不是新算法，也不应自动增加实验授权。

## 当前三问使用方与机制信息

### P1 / 情况A

负责人已确认固定4dff90ef699fd51845cf482951e8477066f5f566；实际使用P1BatchEvaluator。
search.py逐候选依incumbent生成，不能直接冻结成全批；profile_refine一轮从固定parent产生池，
下一轮才更新；prospective_priority先固定pool和ranking_before_evaluation顺序再评价。
默认1在途、status非ok即停止、E0确认才发布checkpoint。

可表达机制族来自源码：
- COPY收缩后的非分叉链包/弱分量/固定块/单大Task起点，再按官方局部时长放置。
- 固定划分的move/swap/合法插入区间/guided move；联合图需数据依赖+全部核链。
- 同核相邻cover合并；按实际Step1压力/首次overflow/远端入口出口做旧前缀二分。
  cover保结构无环，不保证容量/时长；出口保护只是启发式。
- 新的非旧前缀成员选择：最大释放理想、成本约束部分理想、完整出口闭包。
  仅数学核，尚无正式成绩。mincut只对pre-spill割字节－可加工作代理精确，有限价格不覆盖全部Pareto。

关键交互：Task成员/粒度 × 核归属/顺序 × 跨核整Task释放 × COPY/backing/Step1/2/3重建 × 全局DDR。
变化后父trace只供提议，不能当新计划精确评分。
反例/负结果（由P1本人只读报告，固定路径可复核）：
- 同池两个排序臂在008/003/044排序完全相同，003都654160→653263，不能把收益归因于新排序。
- Pro008的components→word，在P1为123060→588824，旧P2作者报告反向123060→63768；
  同op-core、spill=0，但新增partition COPY 0→23970816B，Task每核1→216。
  粒度/次序/mapping顺序同时变化，不是单因素实验。
- 合成例merge的spill更多(1835008 vs1572864B)，Makespan却更少(43729 vs48203)；
  compute-only内存峰也曾低估真实峰。因此零spill、低割字节都不能未经证明硬筛。

镜像固定入口：
- [P1候选构造](https://github.com/Vioano/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/profile_candidates.py)
- [P1搜索](https://github.com/Vioano/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/search.py)
- [释放理想审查](https://github.com/Vioano/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/docs/a/Q1_RELEASE_IDEALS_REVIEW.md)
同提交src/q1/{structure,neighborhood,profile_refine,prospective_priority,release_ideals}.py；
results/a/q1-trace-prospective-20260924/summary.json、q1-q2-mechanism-pro008-20260924/REPORT.md、
q1-pro4-audit-20260924/summary.json可追原证据。

### P2 / 情况B

Fang的src/q2，固定0b58c123cccf02fc993b741d79dcd8511e4dd38f的StageB源码，
最新5f072d9303552d13334e8f83cfc2e335717ea1e0只增加另一机制交付。
固定规格池非逐候选自适应：M1 24规格，M2 30规格；去重后含final实际M1=12–16次、M2=20–26次。
只有makespan严格下降更新incumbent，同分保留原序号；首意外失败停；原每候选E0+full/Trace，
Trace不参与生成。阶段正式122次E0已封存；0 E1/E2。单worker/Windows，不能移用Mac时间比。

本机协同src/q2_nikolastarx已完成13次P2 E0的有限pilot（全部封存，0在途），
固定M1核归属改变core_schedules/优先级，3基线+8候选+2完整复核。样本不是全算法空间：

| 计划 | 002 cycles | 044 cycles |
| --- | ---: | ---: |
| 父M1 | 72415 | 74530 |
| singleton id | 72415 | 125366 |
| critical32 | 72634 | 74099 |
| 全ready critical | 72056 | 74099 |
| earliest_start | 92004 | 71242 |
| 另一分核的既有M2 | 本轮无该对照 | 69113 |

同核分配不保证零spill：044-id spill2169984B。
002 earliest_start与critical的COPY/spill不变，core0/1/3完整M时间线相同、各核最后M结束相同，
最终关键核M之后尾段6259→26207，差19948恰为Makespan差。计算代理不捕获通信/FIFO尾段。
044 critical32与critical原始plan字节相同，本次真实重复成本保留，后续需先去重。

直接使用方建议：链/弱分量分核×同核子图粒度×ready优先级交互不能单因素先淘汰；
同质M-V*-M资源序列是受结构守卫的新机制族，参数窗口/权重/tie-break属于族内调参。
002/044策略方向相反，不能用一图或便宜proxy排名硬筛跨图算法族。

镜像固定入口：
- [Fang提议族](https://github.com/Vioano/huaweicup2026/blob/0b58c123cccf02fc993b741d79dcd8511e4dd38f/src/q2/proposals.py)
- [Fang串行搜索/停止规则](https://github.com/Vioano/huaweicup2026/blob/0b58c123cccf02fc993b741d79dcd8511e4dd38f/src/q2/budget_search.py)
- [本机联合构造报告](https://github.com/Vioano/huaweicup2026/blob/74c46372faf5910b9b3cce6ad9a61a7e040b17aa/results/a/q2-nikolastarx/joint-20260924/REPORT.md)
- [本机联合构造源码](https://github.com/Vioano/huaweicup2026/blob/74c46372faf5910b9b3cce6ad9a61a7e040b17aa/src/q2_nikolastarx/joint.py)
同提交pilot.py及结果目录的protocol/ledger/rows/plan/result.json.gz/trace.json.gz完整保留。

### P3 / 情况C

固定c41db7c0cef17bf4f915fce66da44610a95ab963；画像补充517cd105d1330cfbcf7b11b9a1ab9061242f3d54。
当前online只生成一个结构选择的候选，再做一次P3 E0，无在线试多个择优：
resource_word有严格同质串行M(a)→V*(b)→M(a)、b≤2a守卫，否则affine_eighth。
首批还含分量顺序基线；相同映射插入顺序/核归属/singleton编号、仅改core_schedules。
真实COPY、内存spill、FIFO约束不由纯计算结构定理担保。008/044/080四核有限开发例，20次E0
封存，0可自动续跑额度。完整online约100–121ms，是单候选路径；不能强迫凑批变慢。

普通score要Makespan、各COPY分项和按字节的完整聚合cache_stats；少数诊断才要完整事件。
P2/P3相同计划排名有反转（080），命中率高也不自动说明Makespan低；不能用P2硬筛P3。
未来可能变分核/组/序，不能把本轮固定assignment永久固化为缓存前提。
Q3本人进一步核对：080 component P2/P3=111466/90736，affine=112445/83124并增229376B
spill；044 hit43.54%→32.95%，P3却89039→70261；008三计划hit0/spill0/相同COPY，
Makespan仍123060/64686/63768。三个反例分别否定P2硬筛、命中率硬筛和按聚合指标去重。
受守卫resource_word的h由结构公式决定，不是本轮自由搜索变量；待探索的tensor-消费分量
关联驱动的分核×相位是未实现方向，不能填成绩。多个算法族在几个图生成同计划可复用计划评价，
但不能删掉算法族本身；它们在其他结构上可能不同。

镜像固定入口：
- [P3方法/守卫/局限](https://github.com/Vioano/huaweicup2026/blob/517cd105d1330cfbcf7b11b9a1ab9061242f3d54/docs/a/q3/METHOD.md)
- [P3源码](https://github.com/Vioano/huaweicup2026/blob/517cd105d1330cfbcf7b11b9a1ab9061242f3d54/src/q3/construct.py)
- [P3实际接入画像](https://github.com/Vioano/huaweicup2026/blob/517cd105d1330cfbcf7b11b9a1ab9061242f3d54/docs/a/q3/EVALUATION_PROFILE.md)
- [P3本轮探索反馈与原始CSV入口](https://github.com/Vioano/huaweicup2026/blob/c1935ab51e48b6f239212a4ba11bc8c326c7fd00/docs/a/q3/EXPLORATION_FEEDBACK.md)

## 评估器与并行设施的真实状态

E2已经精确重放C++17+Python准备，P1与P23各自路由；并非旧不合格近似模型。
P23固定997813c7c83d4d18a0a8e2a19b5be37b90223e01，说明603b0741e21c449d3db652ebd67c94f2dc014cc9。
每问题32不同计划开发验证三评分字段/全部op时刻一致，P3缓存事件/FIFO亦一致；有限域证据，
不是全域精确性证明。P23缺对应优化E1，>=10倍E1门槛尚不能验。Windows独立验收仍有未完成项。
case00516新方案全批：1worker P2/P3 E0=7.420/7.654s，E2=4.697/4.832s；
2worker E2=2.888/2.889s。准备占旧单worker全批约95%，全局native回放毫秒级；
继续提速须优化准备，不能只扩worker。P1特定固定划分池的25–30倍旧PythonE1不外推混合/P23。
现pool驻留图、显式worker、每worker1在途，但按worker大小整块等待，有慢项屏障。
现P23 native异常/unsupported自动E0 fallback，full=True也是E0；没有零预算安全禁止回退能力。

镜像入口：
- [当前E2说明](https://github.com/Vioano/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/P23_HANDOFF.md)
- [当前E2池](https://github.com/Vioano/huaweicup2026/blob/997813c7c83d4d18a0a8e2a19b5be37b90223e01/research/a/e2_search/pool.py)
- [当前P23自动fallback](https://github.com/Vioano/huaweicup2026/blob/997813c7c83d4d18a0a8e2a19b5be37b90223e01/research/a/e2_search/scene_b.py)

新基础设施提案（另附当前同会话Markdown原件）：单主机统一资源/预算入口、公平有界队列、
常驻有界worker/图、完成即返、input/candidate/parent/epoch/engine严格身份、结果/账本持久化。
三算法不各自开满CPU；也计生成器资源。预算含启动/准备/IPC/fallback/final E0。
每次请求前预留后端最大可能E0费，最终复核圈存；started未知不退费、不自动重投。
strict_serial_stop保持旧停止规则；显式bounded_speculative用“按原序号确认前缀”的窗口，
已完成但前序未确认仍占窗口；否则只限inflight不足以约束慢失败前被大量快请求越过的成本。
失败epoch不提交新incumbent、queued取消、started终止/排空记实际或unknown。
P3不继承上一个候选的模拟FIFO状态。类型/映射顺序不能盲目规范化后去重。
仅控制面模型10项通过，真实服务/三客户端适配未实现；0本轮E0/E1/E2，模型tick不是实测秒。
本机18CPU/48GiB为硬件容量而非独占配额；跨机器先静态manifest分片，不启用付费云。

## 待Pro审查的初案（不是已接受方案）

我们倾向“结构化算法族 + 条件参数/合法变换 + 分层配对评价 + 多样性保护”的小型研究控制器，
而非一开始任意代码自动变异/巨型参数笛卡尔积。每个候选算法有机制假说/适用前提/变量范围，
按DAG、DDR/计算比例、容量压力、同质/异构、Cache复用等结构分层选代表；变量在不同族条件生效。
先精确身份去重，单因素归因实验和关键二阶/多阶组合覆盖分开；保存谱系与负结果。
每个机制族有最低探索机会，剩余预算依据官方质量、成本、尚未解释的失败/不确定性分配。
新颖性依据可表达的合法结构和资源机制，不按参数名称/随机seed数量计多样性。
弱代理用于排优先级，未经可证明界或独立风险校准不作硬淘汰；少量官方审计抽查被降级候选。
晋级/淘汰按同图配对结果和结构分层表现，避免异步完成快的族垄断队列和只在简单图上显优。
保留跨质量、墙钟、内存的非支配候选；为反例触发重新分层、增加组合或新机制留空间。

**未拿准**：这样如何具体操作而不退化为口号/暴力枚举？小预算时应该固定多样化组合、
序贯 racing、Bayesian/进化方法中的哪一个做主？如何防止把便宜坏proxy当低保真真值？
怎样检测本身搜索空间漏掉好机制，而非继续在错误族里调参？“大概率覆盖”需要哪些可检验
假设/统计单位，不能从几例成功就报概率。

## 请给一份具体、能被反例推翻的答复

1. 明确推荐一个首版探索机制及一个备选，比较其样本效率、CPU/RAM/工程复杂度；不要只列名词。
2. 给P1/P2/P3条件化变量表、可表达算法语法/候选spec例，含合法性前提、交互组、禁用组合、
   同族调参与真正新机制的界限；指出哪些变量不应该暴露给用户/随机遍历。
3. 详细伪代码：起始种子、覆盖性提议、组合/变异/修复或重启、并发候选占位、晋级/淘汰、
   多样性保留、故障停止、最终官方复核；说明何时能异步、何时必须轮次汇合。
4. 给防漏优/误筛的反例：强交互、稀有结构、大图反转、proxy系统偏差、快但弱的候选先返回、
   自适应多次挑最好/公开开发集过拟合、超时删失、核心重编号/有序mapping假等价。
5. 建立“覆盖”的可审计定义与图/算法族的验证划分。若不存在无假设高概率保证请直接说明；
   条件理论与经验统计分开，给能测漏选风险/有效候选数/预算质量曲线的指标及停止或换方向条件。
6. 设计最小可执行研究试验（只设计、不代跑）：先无需正式图的机制/故障检查，再给很小且
   费用明确的正式方案；有同预算基线、消融、全池/被降级候选审计和独立确认，避免人为选赢家。
   说明需要多少证据才值得升级为进化/学习模型，哪些资料缺失则根本不能作结论。
7. 对照现并发设施提案指出接口缺口；算法层与共享基础设施层清晰分工，不把研究调度器变成
   官方在线暴力求解器。可附可下载Markdown/JSON契约或伪代码，但不要生成声称已测试的正式程序。

请先列本轮实际读取的固定文件与未读缺口。GitHub只授权Vioano，均须走已授权连接；
组织库/PR不是可读材料入口。公开文献如有帮助，仅引原论文/官方资料并区分建议、证明和实测。
本轮答案和附件将连同此追问按UTC快照追加为同会话r02，任何追问/更正继续保留版本。
