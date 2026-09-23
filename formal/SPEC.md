# SPEC.md — a-r1-form-adversarial 形式化规范（首轮增量）

负责人：farmeruncle123　run-id：`r1-20260923-farmeruncle123`
冻结输入：`official_code_hash = de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`
代码提交：`ea25b9334a1287766b4b2ebedc9875d5d341eff6`　任务 Issue：#14

**本文件是增量骨架，不是完成的八模块规范。** 模块状态如实标注，未覆盖的不填成完成。

## 0. 总体对象

\[
E_v(G,P,C,q;R)\longrightarrow (\text{status},\text{result})
\]

- \(G\)：原图 JSON（`tensors` / `ops` / `edges`，边为 `{source,target}`，包含 tensor↔op 二部连接）
- \(P\)：方案，字段集合**恰好**为 `node_to_subgraph` 与 `core_schedules`
- \(C\)：`data/config.txt`（冻结字节，LF，341 B）
- \(q\)：问题编号 1/2/3
- \(R\)：锁定参考运行环境

已确认事实：**候选方案不能自由指定全部操作的精确启动时间**，核内启发式由 Step3 固定（见 F-EXEC）。

## 1. 词汇（首轮已用到）

| 符号 | 含义 | 来源 |
| --- | --- | --- |
| eligible | `op.op not in {COPY_IN, COPY_OUT}` 的 op id 集合 | `stub_multicore_cut_and_schedule.py:15,124` |
| mapping | `op_id -> subgraph_id`，键归一化为 int | 同上 `:132-146` |
| core_orders / core_by_subgraph | 核的子图列表 / 子图到核的映射 | 同上 `:165-186` |
| dependency_pairs | 收缩 COPY 节点后的子图依赖有序对 | 同上 `:188-196` |
| pipe_ops | 每个 Pipe 内 op 的固定 FIFO 顺序 | `evaluation_validation.py:237-238` |

## 2. 八模块状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| F-IO | 未开始 | 题面/实现差异待列；已知 config.txt 冻结字节对 Windows 检出敏感（见 ambiguities） |
| F-PLAN | **首批已交（6 条规则，其中 5 条探针实测）** | `rules.jsonl` 的 F-PLAN-001..006 |
| F-TASK | **首批已交（001-003 实测，004 仍是 draft-sourced）** | 来源 `multicore_cut_evaluate_problem_1.py:86-143`；另两个入口 `problem_2.py:61`、`problem_3.py:69` 尚未比对 |
| F-LOCAL | 未开始 | 入口 `schedule_step1/2/3.py` |
| F-EXEC | **2 条已交（均有实测探针）** | F-EXEC-001/002，来源 `evaluation_validation.py:217-243`；unit-level 探针域已标注 |
| F-TIME | 未开始 | 入口 `multicore_cut_evaluate_problem_1.py:200`、`problem_2.py:284` |
| F-RESOURCE | 未开始 | 入口 `schedule_step3.py:74`、`problem_3.py:292` |
| F-METRIC | 未开始 | 结果组装与 `singlecore_evaluate.py` |

## 3. 规则卡格式

严格按契约 v1 第 3.3 节同一张卡：`rule_id / title / scope / kind / symbols_and_units /
preconditions / transition_or_predicate / outputs / failure_behavior / tie_break_and_rounding /
sources / positive_tests / counterexample_tests / implementation_sites / status`。

`kind` 区分：题面要求、实现行为、测试观察、推导结论、团队近似假设。目前全部为**实现行为**或
**测试观察**，尚无一条被标为"题面要求"——题面 PDF 尚未逐条对齐，不预先冒充题面口径。

## 4. 已观测到的语义对抗点（首批）

1. **ID 字面表示不唯一**：`node_to_subgraph` 的键 `"02"` 与 `"2"` 都通过整数校验并判定为重复，
   说明前导零字符串键与整数键同义。可用于构造"看起来不同、实际同一 op"的方案。
2. **空核合法且计入核数**：`core_schedules=[[0],[]]` 被接受，`num_cores=2`。任何把"核数"当成
   "非空核数"的代理实现都会偏。
3. **F-PLAN-005 疑似不可达**：收缩后的子图环检查可能被 `validate_graph` 的整图无环检查提前拦截，
   尚需构造性证明或反例（见 rules.jsonl 的 `blocked_reason`）。

## 5. 复现

```sh
python src/adversarial/verify_rules_r1.py
# 输出：results/a/form/r1-20260923-farmeruncle123/fplan-observations.json
```

只记录 accept/reject 与官方报错原文，**没有调用 E0 评分，也不构成任何性能或质量结论**。
