# P2 完整分量 / DDR 固定候选 R4

session=yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24。2026-09-25恢复时实际get_goal为active（updatedAt=1790303015）；旧暂停及17c控制错误不回写历史。继续本人独立P2工作树与写区，不改队长或共享evaluator源码。

## 已实现规则

入口 `python -m src.q2.feedback.construct <graph.json> --cores <k> --strategy component_gate --output <plan.json>`，仍只输出官方两个字段。先调用既有F1；如果F1已采用获证resource word、其word已被容量拒绝、存在alias/超出整数域、或当前没有跨核COPY压力，保留F1。否则只再构造一份当前图/核数的tensor_packet A，以最终F1为B。

每条基础COPY分别累计 `max(1,ceil(size/bandwidth))`，包括0 B direct的两条COPY；输入按消费核、最终输出按生产核、tensor传输按生产/消费核对统计，原图COPY不重复计入。不调用官方任务编译/Step2/Step3/E0，不读图号、保存计划或历史分数。tensor/direct字节及eligible cycles限制至`2^31`，避免已发现的巨整数除法差异；这不是全事件循环的误差证明。

仅当A为完整弱分量、无跨核链接、singleton、无alias、物理闭区间容量证书通过，并满足 `U_A=max_c sum(d_v)+W_A < L_B=W_B` 时返回A；否则按字节保持F1计划。见[Sol审阅](COMPONENT_GATE_REVIEW_R4.md)。这是理想服务模型启发式，尚非官方浮点模拟器的严格改进定理。基础流量相同而只因spill退化时没有判断力，不能替代F1容量处理。

`outer_plan_count`最多2，不包含F1内部word/gap/修复构造。COPY统计为`O(V+E+k²T)`；索引、候选构造、合法性验证/排序、证书全部计入端到端求解时间，不声称整条算法线性或比队长更快。

## 验证与成本

`python -X utf8 -B -m unittest tests.q2.feedback.test_component_gate tests.q2.feedback.test_frontier_gap -v`：11项通过。覆盖0 B direct、按核去重、61 B逐条取整、容量差1 B、等号保留、跨核A、不同核数、大整数/alias拒绝及word计划保持。0真实图冷求解、0 Step2/Step3/E0。

`results/a/q2-yuanzhifang/feedback-20260924/component-gate-r4-static/probe.py`只读020/045保存的旧tensor A及最终F1 B，核对图/配置/计划/结果哈希。两例`U_A/L_B=146980/279174`、`34996/93219`，均触发；A/B基础COPY字节与保存E0的scheduled减spill一致。脚本0.888549秒，不含启动；0新方案构造/0评分，不能当作R4新成绩或求解时延。report.json含本次源码/脚本哈希，复现必须指定新的`--output`路径。

Sol medium独立理论审阅软预算约6000 tokens，窄审追加≤3000 tokens；未用Astra、未递归、无真实图构造或评分。软预算是工作约束，未取得工具级精确token账单。

## 对照与待排程小试

算法源码已固定为 `a8a4ce538e60650594f6d9df43c9731275648599`。`round18a-proposed-spec.json` 的check-only通过，3个单位、19个源码/runner文件身份核对通过、0 solver/E0；这不是派发许可或RAM入口检查。

已读队长`1c00079aadbd071de62db17686d5ba3fed1da0f2`全量报告：固定c665算法100×1–5核均值1.206139/2.316727/3.235566/3.971149/4.549757，至多3个在线native E2候选，1131 E2/500独立E0，平均solver墙钟4.029秒、p95 18.841秒（共享Mac）。未重跑队长500格，不作跨平台速度比较。队长在Issue26 #5823085955接受统一交付优先建议；正式TeX由协调者单写，成员交方法与证据。

新增只读对照 `component-gate-r4-static/{compare_c665.py,vs-c665.json}` 核对每格图/config哈希后，旧tensor对c665为85胜35平380退，gap为43胜162平295退，F1五核为9胜18平73退。020/5保存旧tensor107650优于c665110112，045/5为26164优于29103，因此本候选有针对性的团队补益空间。这里只读取队长固定摘要中的E0记录与结果哈希，未独立重验其500份raw结果；0新评分，不把这些优胜格拼成算法或宣布均值改善。

拟提交排程：007/020/045、5核、固定本候选，最多3 cold solver+3独立E0、0 E1/E2、0重试、1 worker；solver60秒、E0 90秒、batch600秒、cleanup15秒，入口RAM≥1.5 GiB。020/045针对已知过度拆分，007保留F1修复负例，均为公开开发诊断，不是独立留出集。非法/超时/原件不一致停止，不自动扩全量。正式评分按Issue33/成绩台唯一排程，尚未分配或启动；旧17a/b/c、M/S等封存窗口不重置。P3准备其067小试，本轮P2只做低成本代码/静态工作，不占其评分窗口。

## 实际补读与指标边界

本轮Mailbox完整抓取6话题/649评论；专项补读Issue33新增29条（5823368300至5825608120）及Issue26公共决定5823085955，未导入无关P1/P3聊天。网页请求仍归c909会话，不冒领。维护方在5823464206撤回17c“中央准入到首次快照5m33s”的归因，首次应为5.157秒，页面精确首次可见未知；不影响100格真实性。

Makespan周期、求解端到端秒数、额外DDR字节分列。5～10分钟是P1题面效率建议及团队沿用目标，不是P2硬600秒淘汰线。本候选基于固定结构比较，不能仅凭“有限次数”声称非暴力；所有在线成本需实测。更快E2或低于10分钟均不足以完成质量与效率目标。
