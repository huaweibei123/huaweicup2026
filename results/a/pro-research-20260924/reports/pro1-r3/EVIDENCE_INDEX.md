# R3 证据索引与实读边界

## A. 输入身份与读取范围

|对象|本轮实际动作|不能据此声称的事项|
|---|---|---|
|官方原ZIP|解压114原文件，对100个JSON及全部code/config/docs逐项size/SHA256核对|不是全100例新算法评估|
|source-manifest|实际重算代码集合hash，结果de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0|不是拿ZIP hash代替代码集合hash|
|PRO_ROUND2_DELTA|运行随包VERIFY_BUNDLE，452payload匹配|不等于验收成员全部理论/性能|
|64份E0 gzip|通过FAST的_load_pool解压、JSON/hash/身份/makespan表核验|没有重跑这64份，不是旧295份|
|FORM86b095f|读取SPEC修正、关键规则/覆盖与缺口、疑义、队长复核；对照冻结源码关键函数|不是逐规则全文题面对齐证明|
|FAST3357d7e|读取P1索引改写、隔离加载、两条E2主要路径/比较脚本，运行新候选|不外推到P2/P3|
|旧报告与证据包|读取旧审计/策略索引与本轮相关摘要，复用四个legacy构造/检查脚本；保留原源文件|没有重跑旧100例，不将旧缺失结果填回|
|本轮正式算法输入|实际解析并评估15个正式case|不是全部100例平均成绩|

DELTA不是COMPLETE布局，本轮起初没有假称运行其要求独立official-cases.zip的a_materials --extract，而是复用已有完整官方原ZIP，按完全相同清单/配方核对。随本证据包的PREPARE又在独立vendor路径实际解压并验证一次，见evidence/portable_prepare_check.json。

### 授权GitHub镜像读取

使用实际GitHub连接，非匿名网页、非只看main；未写仓库。

|路径|固定commit|读取范围|
|---|---|---|
|docs/a/source-manifest.json|8ba6248f16a85324901a787676b1658e532f5c1c|全文返回及顶部10行复核|
|formal/SPEC.md|86b095fc6eff27f91a26c38424b460280caae926|74–104行修订段，全文本地原件可读|
|src/eval_exact/problem1.py|3357d7ef9c1ad443dd0799f6ecb5b813df6753b3|远端1–80行；完整实现本地读取|
|docs/a/FAST_REVIEW_20260923_CAPTAIN.md|dbf9894f77ad7bfe5c8d13d94be1d2b6e15519bc|全文|

四个返回Git blob SHA均对上本地文件完整字节，evidence/github_read_receipts.json。PR/main现在是否继续变化不属于这份冻结研究的已核实事实。

### 残余旧缺口

`prior/R2_archived_runs_integrity.json`保留295个缺失完整历史result的具体路径：Q2=123,Q3=93,单核=69,Q1=10。本轮没有找回它们。某些case/plan重复出现是新E0身份，不能补写旧运行时间/Trace。

### 残余FORM文字冲突

SPEC、F-EXEC-001和F-RESOURCE-001已修正。`formal/ambiguities.md`§5仍写旧的单链24/双链44加核论断；本轮不用它作因果证据。队长的定点复核和成员覆盖标签都不冒充全形式化验收。

## B. 新算法主实验

机器可读表：analysis/official_run_catalog.json。每条指向results中的独立目录，保存：plan.json、construct.json、完整result.json.gz、run.json、stdout_stderr.txt；失败时保存异常，不填零分。

|阶段|问题/核数|完成E0调用|作用|
|---|---|---:|---|
|pilot_v1|Q2/4|49|7例×7构造，包含最小割失败|
|validation_v1|Q2/4|40|8预列例×5构造，保留两例新方法退化|
|refinement_v1|Q2/4|28|7例×4方法，固定/重新归属消融|
|phase_refinement_v1|Q2/4|14|7例×2连续Pipe段细化|
|q3_transfer_v1|Q3/4|56|8例×7构造，Cache下重新评价|
|n2_transfer_v1|Q2/2|35|5例×7构造|
|n5_transfer_v1|Q2/5|35|5例×7构造|
|window_refinement_v1|Q2/4|18|6例×3固定参考窗口|
|window_validation_v1|Q2/4|7|固定factor8转移，未事后换参数|
|window_q3_v1|Q3/4|5|窗口在Cache下重新评价|
|window_n2_v1|Q2/2|3|窗口核数转移|
|window_n5_v1|Q2/5|3|窗口核数转移|
|合计||293|全部有完整E0结果，调用数不是独立样本数|

15例：001,002,010,019,026,037,044,048,051,064,069,071,080,094,096。参数开发/验证界线见evidence/*predeclared.json。这些case此前的结构摘要或其他讨论可能已见，不冒称全部未见封存集。

关键路径：
- `results/window_refinement_v1/case_002_window8_response_q2_n4/`：66376。
- `results/pilot_v1/case_002_chain_response_q2_n4/`：71904。
- `results/pilot_v1/case_002_unit_q2_n4/`：旧unit111212。
- `results/refinement_v1/case_002_unit_response_q2_n4/`：相同新成本、单操作104109。
- `results/window_refinement_v1/case_044_window32_response_q2_n4/`：105715退化。
- `analysis/fixed_ownership_checks.json`：68组保持核心归属/partition字节的独立比较。

完整构造源码版本见evidence/versions；source_version_check.json检查主run中所有记录的constructor/runner/solver哈希均能在包内找到对应源码。原型的固定配置/未覆盖范围记录在源头与README中，不把源码存在当实验。

## C. 机制与数学检查

13次公开接口机制图，`results/mechanism_probes/summary.json`：
- reentrant.json，Q2/Q3各5个方案：粗链204 vs分段交错104。
- export.json，Q1三个方案：6014 vs合法融合11005 vs出口保护6014。

全部使用原配置。没有增加等待/预取/重算或修改原图操作语义。

数学检查`evidence/math_checks.json`：固定seed2026092303，300随机DAG，2400次compute profile、600次链/重入商图、1785次接受的cover contraction核对；0失败。这些不是E0 Makespan对照。

完整包自带原件再解压后，REPLAY另跑两个新调用并做**完整JSON逐类型**对照：case002窗口66376、export失败11005，均无差异。位于evidence/portable_replay_*，不是历史恢复。

## D. 真正E1/E2的新比较

用于正式诊断汇总的40条记录（37个原始plan哈希）：
- 002,010,026,044：`results/p1_fast_v2/`对应各8条。
- 051：`results/p1_fast_051/`对应8条。
- 原样完整E0/E1分别为e0.json.gz/e1.json.gz；两种E2为rank.json/event.json，明确为估计/排序。
- `results/p1_fast_complete_rows.json`是从以上已完成记录选择的派生索引，不是新的执行。
- `analysis/fast_diagnostics.json`给40记录加权；`fast_unique_notes.json`给37份去重结果。

E1成功对照40/40不是全域证明。E2的top1损失是8条诊断池，不是团队至少64池发布标准。未采用跨机器旧E0时长来计算本轮加速。

计时：results/timing_e1_*每例一对warmup与三对正式E0/E1，全部完整输出存档。结果1.846/1.275/1.481倍为本机新构造上的完整函数API，排除读取/序列化，不能代替完整CLI成绩。

### 包装器错误与中断

首版p1_fast在E0/E1/E2已经执行后，包装器误取P1没有的task_count字段报KeyError。保留31个叶目录完整E0和相应异常；顶层runs只在每例完成时落盘，不能用顶层24条覆盖叶目录。

工具层执行时限还中断了首版和v2的跨例批命令，留下某些未完成目录或尚未写入顶层索引的叶记录。所有存在/不存在状态见analysis/harness_event_inventory.json。最终采用的40条来自完整叶记录；051单独重跑并有新目录。没有把工具中断写成官方认定非法。

## E. 真实端到端与公平口径

`results/solver_*`为实际运行的有限候选控制器，E0通过原版CLI子进程调用。

- 使用30秒预算；结果111212/71108/66376/28637与README所列模式对应。
- 每候选完整CLI输出含result、Trace、log、stdout/stderr；根目录获胜输出整份复制，**根目录副本不是额外调用**。
- 图解析、构造、候选选择、CLI启动、序列化、回退都在墙钟中。每次只计一次实际测量，不宣称统计速度保证。
- 不同构造数、去重后E0调用数不同；不能把池最好值当零成本选择或纯模型消融。
- 预算中断覆盖E0子进程；构造阶段仅候选间检查，未证明大图硬实时。

## F. 目录完整性

`MANIFEST.json`对实际打包payload逐项字节hash；VERIFY脚本不会把后续本地新增结果误报为源文件。依赖ZIP本身也在manifest中，展开后有source-manifest与bundle manifest双重核对。

原始绝对沙箱路径只是运行时来源。独立运行用PREPARE、REPLAY及README中的相对命令。没有修改官方代码/配置/数据，没有安装服务，没有GitHub写操作。
