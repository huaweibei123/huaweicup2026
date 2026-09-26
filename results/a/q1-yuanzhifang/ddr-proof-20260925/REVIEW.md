# Sol high 独立证明审查

仅本机路径改为仓库相对入口；审查原始正文 SHA-256：`60ee601dd40516c29bb8f44a36fb640d4b8fbb5b9687e2a13c4dba1ba2fa68e9`。正文中“尚未固定”指审查当时状态，未改写。

**结论：条件下界成立；尚不能称为冻结 E0 的逐位严格定理，也不证明全局最优。** 对固定候选 `6fba2f5…`，我未找到跨轮 Task、最后 COPY 时刻、全链携带或 \(M\) 去重的反例。

合法 Task 商图无环使同一 Task 在依赖路径上凸闭。设 \(P\) 含前轮根，则它在当前每条链上只能含完整链或前缀。若 \(u<12\)，每条未完整留在 \(P\) 的链都须在 \(P\) 退休后完成一条 32768B COPY_IN；最后完成的那条 COPY 后，仍有至少 \(4p-p_{\max}+d_j\) 的依赖计算。\(u=0,c>0\) 时，\(P\) 中最后的前缀输出还须在退休前 COPY_OUT；\(u=12\) 由代码检查的 \(12(4p)\ge b_j+12p\) 单独覆盖。配合 \(p=524,w=547,g=100,d_j=39\)，得到首轮 8699、其余每轮 8799，合计 **211076**。证明与守卫见 [DDR_BARRIER_BOUND.md](../../../../docs/a/q1-yuanzhifang/DDR_BARRIER_BOUND.md) 和 [ddr_barrier_bound.py](../../../../src/q1_yuanzhifang/ddr_barrier_bound.py)。

同一原输入的消费 Task 若离开后返回，会违反路径凸性。因此 \(288-M\) 等于相邻轮同输入、同 Task 的次数，每次均占下一轮 \(P\) 的一条非空前缀。每个输入—Task 对至少一次 IN；每个私有内部跨 Task 边至少一次 OUT 和一次 IN。故联合必要界为
\[
C_{\max}\ge\max\{211076+524(288-M),\;547(M+2B)\}.
\]
冻结 [P1 评价器](../../../../data/raw/a/official/code/multicore_cut_evaluate_problem_1.py) 的边界规则对同核 Task 也生成 COPY；Task 退休、释放与 [Step3](../../../../data/raw/a/official/code/schedule_step3.py) 的共享 DDR 工作量支持上述条件。051 的**尚未固定**静态证书显示 24 轮最短归约路径均为 39、12 个输入、864 条私有内部边；既有 G 计划的 \(M=288,B=0\) 仅适用于该计划。

未证项是 E0 浮点事件实现中的 `1e-9` 容差及取整是否对所有事件序列严格保持整数容量界；本次也未做独立运行时验收。四项合成测试只检查守卫和算术。我没有运行 solver、E0/E1/E2 或 Task compiler。已读范围限于所指候选、051 静态产物、必要守卫、冻结 P1/Step3 源码和 Pro 答复第三节；Mailbox `check --full` 已抓取索引，未将其他话题全文导入本次复核。

---

会话与 Mailbox 元数据（本次补记）：

- 本次新生成的 session：`yuanzhifang30-sudo/s-874197db84874d63be3c5675ba5612dd`；GitHub login 由 `gh api user --jq .login` 实际读取。本会话此前没有生成或发布 session ID，Issue #26 登记由父会话处理，本人未发信。
- `check --full` 返回 `fetch_complete=true`、6 个 Issue、482 条评论、1 个 assigned open issue；索引：`Git common dir / team-mailbox/history/inbox-0tfvo5m4/index.json`。
- 我实际读取了索引中的 6 个话题编号和标题（#5、#15、#26、#33、#51、#98）；**没有读取任何 linked issue transcript 原文或评论**，因此不声称这些消息已读。
- 研究材料实际已读：固定候选文档、实现与测试；`star_frontier.py` 的必要守卫、`fork_frontier.py` 中 `stage_units` 必要定义、官方 P1 与 Step3 的必要片段、官方方案校验的必要片段、Pro 固定答复的第三节相关段落，以及未提交 051-bound.json / metadata.json 的必要字段。README、docs/SESSION_PROTOCOL.md、docs/TEAM.md、docs/a/ROUND1.md、docs/a/SYNC_UPDATE_20260923.md、docs/TEAM_WORKFLOW.md 与 team-mailbox SKILL 只读了工作相关入口/片段，未声称全文已读。AGENTS.md 的新资源策略与核心目标已核对。
