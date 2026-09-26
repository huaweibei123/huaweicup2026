# 需求来源与本次核对

本次 owner：`nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`；2026-09-24。
这是专项已读与反馈记录，不替他人签收，不用账号级消息代替 session 级角色。

**当前已确认路由**：P1=s-6607；P2=s-8ee33与Fang s-25ac协同；
P3=s-3172；本任务s-55b6维护三问共同基础设施；公共整合/Atlas由s-a5bd负责。
以下早期反馈中“无算法写权”“待回交”等是接收当时的历史状态，已被本段及后续本人接手回执替代。

## 已收到的直接反馈

- 历史首轮调度反馈（早于用户明确P1回交） `s-a5bdb19389ee43d686b7976d3bcdf766`：三个本机任务不能直接等同于三问当前单写者。
  Q1 旧父任务已释放写权；s-8ee33 又从 Q1 转 Q2，Fang 仍写 src/q2；本机新 Q2 范围需原通道对齐。
- 本机新 Q2 `s-8ee33b891eb94c529bf5be94bb5d8894`：当前1 worker，无在途；拟每轮3–12候选、
  固定graph/core assignment改序、阶段间自适应。稳定candidate_id、显式失败、原计划保存、
  完成即返且轮内汇合；不因别的实验整批没完成延迟本实验结果。Q1已停写于4dff90e/PR34。
  这是预期新Q2接口需求，尚无已运行的新适配器和样本。
- Q3 `s-3172f7b01b604cfb90aefd6396bd87bc`：固定完整画像
  [517cd105 / EVALUATION_PROFILE.md](https://github.com/huaweibei123/huaweicup2026/blob/517cd105d1330cfbcf7b11b9a1ab9061242f3d54/docs/a/q3/EVALUATION_PROFILE.md)。
  当前1候选+1官方P3，全阶段封存20次E0，0新可用额度。未来普通score需COPY分项和聚合
  cache_stats，少数诊断才需逐事件；full=True的E0成本不可隐藏。支持未来ID/epoch关联，
  当前尚无异步消费者；配对缺一半记incomplete，不同候选不能延续模拟Cache。
- 历史首轮Q1父任务反馈（早于本人重新接手） `s-6607cb2735304751b36662035723372b`：现无算法写权；只提供历史13d6的profile轮次背景。
  本提案以固定4dff代码核对补充，不将历史摘要充当当前开发者接受接口。

## 跨账号需求请求

Fang Q2 coordinator `yuanzhifang30-sudo/s-1926b07caa22406881a4f0e51fdbe4c7`、
writer `s-25ac3f7459f94fabb940724245a20ade`：
[Issue33 需求请求与范围](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5805116566)。
消息已提交并回读为 NikolaStarx 正文；已收到并全文读取Fang本人的
[5805179167画像](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5805179167)。
实际HEAD `5f072d9303552d13334e8f83cfc2e335717ea1e0`，构造/搜索不变于StageB
`0b58c123cccf02fc993b741d79dcd8511e4dd38f`：`GraphIndex/specifications/propose`生成
固定池，`budget_search.py`逐候选官方CLI，`stage_b.py`串行case×method。M1/M2去重后含
最终复核12–16/20–26次；评分仅更新incumbent，同分保留原proposal次序，首意外失败停。
每候选过去写full/Trace，Trace不参与生成；新需求允许普通score、按需full。历史122次E0、
92.983s评价、59.318s生成、181.094s九单元及账本，只是该范围计时。未测CPU核数/并发，
4GiB采样停止阈值不是硬限制；所有旧额度封存，无在途。

两个反馈已落设计：请求预声明可审计最大E0费+最终复核圈存；首失败停止的严格串行与显式
投机窗口两模式（开始/取消事务竞争与未知额度均保留）。本次不重跑StageB或独立测试。
固定接入样本由Fang提供：上述0b58c提交的
`results/a/q2-yuanzhifang/stage-b-20260924-042906/044-M1.zip`，其中
`044-M1/proposal-07/plan.json`，SHA256
`68a57b92f6c40a72d4e856333a4074761a8684455f03ccb367f38ee72b45a242`；
`044-M1/eval-16-final/result.json`，SHA256
`29bf1bac5337c5d1b966c86c5f943248ef3d818e582d6df0868db2367bb3565a`，74530 cycles。
这是使用方给出的固定引用，本轮未重新解包验哈希或执行。

后续本机s-8ee33新反馈：用户明确把P1回交原父s-6607，P2由s-8ee33与Fang协同；
原Q1固定4dff、无在途已向父交回。随后已收到s-6607本人接手回执，真实HEAD/无tracked dirty
和接口均已核对；公开角色更正[5805221872](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5805221872)。
新的P1画像区分：search逐候选依incumbent生成；profile_refine每轮从固定parent生成池；
prospective_priority冻结pool/ranking_before_evaluation的position/pool_index再顺序评分。
后二者非ok即失败，官方确认后才发布checkpoint，保留已确认parent。请求必须有parent plan hash、
原proposal序/position及各入口objective；默认strict 1在途，投机仅同一冻结轮，失败轮不提交。
本机Q2提供新PR59固定`c5df001aa4b3efe95da9cf4ae6836ebd912c7db9`，入口
`src/q2_nikolastarx/pilot.py`和`results/a/q2-nikolastarx/joint-20260924/`，
自报13/13 P2封存，1worker、30s单次/180s批、120s停发，无在途；本轮未重跑。
随后最新交付`74c46372faf5910b9b3cce6ad9a61a7e040b17aa`仅增加零评价时间线诊断。
本专项已回复确认：P1=s-6607、P2=s-8ee33+Fang、P3=s-3172；本专项负责三问共同基础设施。

LYX本人已在[5805058735](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805058735)
回报旧E2目录无在途/未提交生产改动，后在5805166783核验Atlas94；共享写权由调度正式汇总。
本专项已建议由LYX做固定603b的路由/最大E0成本只读矩阵审计，0调用/0构建、30分钟首检查点，
不触碰Fang的C/D/E PID门禁。调度后续已正式派发PR61任务卡，回报LYX本人5805307559实际
确认接手，T0 08:31:14 Asia/Taipei、09:01:14前首检查点；尚无本专项实际核对的审计交付。

## 固定源码和数值依据（只读，未新跑评估）

| 结论 | 固定依据 |
| --- | --- |
| E2池整块等待，单worker单在途、spawn、驻留图、默认单worker | [997813 / pool.py](https://github.com/huaweibei123/huaweicup2026/blob/997813c7c83d4d18a0a8e2a19b5be37b90223e01/research/a/e2_search/pool.py) |
| P23自动E0回退及full、返回字段 | [997813 / scene_b.py](https://github.com/huaweibei123/huaweicup2026/blob/997813c7c83d4d18a0a8e2a19b5be37b90223e01/research/a/e2_search/scene_b.py) |
| 1/2worker旧正式测量、不同问题总账、边界 | [603b074 / P23_HANDOFF.md](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/P23_HANDOFF.md) |
| 旧准备占比及Amdahl推算，未新增正式调用 | [Issue15 理论分析](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805002188) |
| 当前Q1实际使用P1BatchEvaluator，逐候选调用 | [4dff90e / search.py](https://github.com/huaweibei123/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/search.py)、[profile_refine.py](https://github.com/huaweibei123/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/profile_refine.py)、[prospective_priority.py](https://github.com/huaweibei123/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/prospective_priority.py) |
| P2Windows C完整类型未通过、不能用序列化后相等代替 | [Issue15 只读复核](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5804816099)；这是该检查点结论，后续独立续测另记 |

本机Q2反馈曾提 `src/q1/fast_score_adapter.py`；本专项实际 `git ls-tree` 固定4dff树无此文件，
已将纠正发回该task，文档引用真实三个调用文件。协议设计以证据为准，不因转述路径直接造API。

本轮完整Mailbox抓取6issues/260comments成功，按专项范围读取最新需求和公共角色信息；
没有宣称260条均进入上下文。共享main基线6a7c678、原E2固定worktree及算法worktree均未改动。
本轮检查的物理/logical CPU均18，物理内存48GiB；不是空闲资源测量或实验授权。

## 交付与未完成事项

- 当前交付：[设计 v1](CONCURRENT_EVALUATION_DESIGN.md)，以及
  `research/a/evaluation_service/` 的离散调度/额度状态模型；它不导入任何evaluator、
  不启动worker进程、不建立服务。结果目录会清楚标为模型输出。
- 未完成：持久化账本、IPC、OS资源限制、真实三客户端公平压力测试、算法适配、跨平台/多机。
- 接受状态：已收到真实需求，提案供技术审阅；消息发送和PR创建不是接口已接受或部署。
- 任务分工：本专项写公共基础设施研究，算法方写各自薄适配，原独立测试保留；
  公共任务卡、AGENTS和Atlas由调度汇总。无正式E0/E1/E2新增调用，无新正式实验预算。
- 用户追加探索机制问题后，三问本人均给出机制族/交互/负例，已汇总并实际投递
  [Pro r02](PRO_R02_STATUS.md)。后续完整答复与原件已取得并交中央归档，上传/镜像/Pro读取/研究有效性分层记录。

## 路由审计与父阶段反馈（后续补读）

已全文读LYX固定09eef20的矩阵/JSON及Issue15#5805508214；Fang协调的
[路由回执](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805578444)和
[父stage停止域审阅](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5805545792)
也已全文读。本专项有限源码复核见[ROUTE_COST_REVIEW.md](ROUTE_COST_REVIEW.md)；
新设计明确E1独立预算以及stage→unit experiment→epoch祖先许可。身份分层先前已修正，
本次补父级停止域，不把使用方对旧原则的接受当新版接口接入验收。公开路由记录改用session
和Issue来源，移除本机任务ID；历史已发送Pro材料保持原件，后续更正另记版本。
