# 共享输入生命周期窗口：独立有界原型

`src/q2/feedback/lifecycle_window.py` 先调用现有 `capacity_window.build`。仅当它选中 `capacity_window`、未因别名或重分量转入其他路线、某非空核的原容量窗口为 0、且该核包含完整弱连通分量时，才为该核生成一个新候选。其他核保留原优先序。它不注册到 `construct`，不调用 E0，也没有按图号选择或评分循环。

作业共享外部输入由**本核**的作业引用次数定义：被至少两个作业消费的外部 tensor 计为共享。每个作业按共享 tensor ID 排序形成 tuple 签名；按照原核作业首次出现位置建立签名组。每组复用 `memory_window` 求宽度，并用 `pipe_window(..., prefer_fill=False)` 排序，宽度至多 8。任一组宽度小于 1，整核保持基准优先序。拼接后用 `footprint(index, full_sequence)` 对整核闭区间逐桶核算 L1/UB；任何池越界则整核回退。组内证书不能代替整核证书，尤其相交签名可能让早期输入活到后续组。最后调用 `derive_multicore_plan` 校验完整输出，保留原 `node_to_subgraph` 和每操作单子图映射。

元数据给出原宽度、组数、各组宽度、已构造候选的完整峰值及采用或回退原因；不复制基准 `cohorts` 清单。命令行与容量原型一致：

```text
python -m src.q2.feedback.lifecycle_window GRAPH.json --cores K --config CONFIG.txt -o PLAN.json
```

在原共享组件路线的适用域内，改变核的完整闭区间证书可按冻结 Step2 的先分配、检查、执行、释放语义保证该核不发生容量 spill；未改变核沿用原优先序。分核、映射和原始 COPY 端点不变，因此相同映射下由分区产生的额外 COPY 字节不变，spill 字节不增。这里的结论仅针对上述条件下的额外 DDR **字节**，不保证 Makespan 不退化，也不保证现有 072 图能获得证书或性能收益。重分量 packet 分支、逻辑别名与不完整组件放置均不在这个证明范围。

增量开销：令 I 为各操作输入、输出的总引用数，n 为操作数。统计共享输入引用 O(I)，排序并构造签名保守计 O(I log I)，`pipe_window` 对每操作比较至多 8 个活动作业为 O(8n)，完整闭区间检查 O(n+I)。基础 TensorIndex、容量构造、图派生和进程启动另计；端到端时间不由此式直接给出。

合成测试覆盖不相交组的成功、AB/BC/AC 组内可行但完整峰值超额的回退、组内不能准入、别名/非目标路线保持原计划、确定性与合法计划结构。命令：`.venv/Scripts/python.exe -X utf8 -B -m unittest tests.q2.feedback.test_lifecycle_window -v`，4 项通过；没有运行官方图或 E0。

最小后续证伪实验：先固定少量包含不相交及相交共享输入结构的官方图/核数组合，记录基准与新方案的每核原/新宽度、完整峰值、合法性及求解端到端墙钟；随后用未修改 E0 分别测 spill 字节、总额外 DDR 字节和 Makespan。若宽度不增、完整证书失败、spill 不减、时间显著变慢或 Makespan 退化，应原样报告并保留基准路线，不能将局部容量证书解释为性能证明。
