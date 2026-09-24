# 验证记录：retained priority 候选

固定基线算法：`3c6e41b938c764d207de45584fb526c64f4eb845`。本审查树原先没有 overload/heavy 两个实现，因此本地准备提交 `66c89213` 仅恢复该版本的 `heavy_suffix.py`、`component_overload.py` 及原 overload 测试/说明，现有 sink/bounded/component_pack/官方源码与该版本一致。主控已有这些依赖，集成时只需本候选提交，不需重复准备提交。

实际执行使用主项目已经安装的 `.venv/bin/python`（Python 3.12），未安装或修改依赖，未写其他 worktree。

```sh
python -B -m unittest tests.q1.test_retained_priority tests.q1.test_component_overload -v
python -B results/a/q1-retained-priority-20260925/static_priority.py
```

第一条 **13 项通过**：新增 7 项与原有 6 项（包括原 64 个小 DAG 的枚举检查）。合成测试运行 0.027 秒；这不是真实求解器端到端时间。测试只操作小合成图，没有 Task 编译或 E0/E1/E2。

最关键见证：一个完整工作 150 的 retained 包，ready key 可降为 50，但 `finish_proxy − start_proxy` 仍严格等于 **150**，相邻同核 Task 仍至少等待完整完成后再加 100。集成合成图的三个 retained 包均工作 900、priority 300，且新旧 mapping 完全相同。缩小 soft-chunk 阈值后，两种 priority 仍有相同的最终成员分块。

第二条只读取固定历史 JSON，计算四图初始 ready 排序，不运行真实图构造或 `_place`。031/053/087 原先 5 个 retained 包均高于最高 split root，新规则变成 0；077 变成 2。结果是机制描述，**没有新方案 Makespan**，`candidate_makespan` 明确为 null。详见 [static_priority.json](static_priority.json)，其中记录源码和输入 SHA。

本次真实图 constructor / placement / Task compiler / E0 / E1 / E2 调用均为 0。未 push、未发外部消息、未写成绩台。新算法的官方质量、容量可行性、DDR 时序和真实求解墙钟仍待主控批准的有限外部验收。
