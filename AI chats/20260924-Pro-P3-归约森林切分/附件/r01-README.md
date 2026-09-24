# P3 封闭子树团队构造：纯计算原型

## 边界

本目录没有下载、导入或运行官方评估器，也没有读取 case002/062/063 的原图或运行成绩。
`abstract_tests.json` 中全部数字都是微型人工图上的抽象数学单元测试。
它们不是官方性能成绩，不是实测案例的替代。

本轮通过有权限 GitHub 连接分段读到了固定提交
`b84e3670452603af1f08169f4dfb5809df8cd31a` 的六个指定文件：

- `src/q3/fragment_tree.py`
- `src/q3/reduction_tree.py`
- `src/q3/construct.py`
- `data/raw/a/official/code/multicore_cut_evaluate_problem_3.py`
- `data/raw/a/official/code/schedule_step2.py`
- `data/raw/a/official/code/schedule_step3.py`

另局部读取了 `stub_multicore_cut_and_schedule.py` 的收缩与方案校验逻辑，
以及 `multicore_cut_evaluate_problem_1.py` 中 P3 导入的原始 tensor 视图函数。
这不是对 Q1 算法的研究。
未读当前案例 JSON、配置文件和本地新成绩归档。

## 运行纯抽象测试

Python 3.10+，无外部依赖：

```sh
python test_abstract.py
```

## 接入

```python
from sealed_tree_dp import Model, Node, construct

# 必须由本地已有 Index 构造，而且逐边确认 COPY 收缩边的官方语义。
nodes = {u: Node(u, index.duration(u), index.ops[u]['pipe']) for u in index.ops}
children = {u: tuple(sorted(index.pred[u])) for u in index.ops}
model = Model(nodes, children)
plan, meta = construct(model, cores=5, delta=500)
# plan 恰好两字段；本原型使用按原操作 id 排序的稳定 singleton id。
# 若实验协议要求与 Index.order 完全相同的 singleton id，调用方重新编号。
```

首版只支持一个真正的二叉归约树（可有一元节点）。高入度和森林不会被偷偷改写为
含有新计算操作的二叉树。多棵同构树的整树分配、子树签名复用在正文中说明，未在此
原型里实现；多池内存 Pareto DP、缓存收益和 COPY 传输成本也未实现。

## 证据与不等式

`abstract_fifo_makespan` 是给定抽象图和输出词的增强 DAG 最长路。
`abstract_witness_upper` 是 LOCAL / SEQ / PAR 模板的时长上界。
代码检查前者不超过后者。二者都不能被称为官方 Makespan 上界。
增强 DAG 最长路只有在所有抽象依赖及其延迟都确为官方必需约束时，才是官方下界。

`local_signatures` 使用整数 max-plus 运算，保留各 pipe 的可用时刻和子树根完成行；
不存在把浮点近似相等当作逐位等价的处理。

时间 DP 的复杂度是 O(n*k^2 + n*P^3)，另加输入排序和输出/最长路核验成本；
P 是计算操作所用 pipe 数。时间-only 模板 DP 的最优性不等于实际调度全局最优性。
`restricted_family_failure_11_nodes` 提供模板构造耗时 7、另一个明确方案耗时 6 的反例。

## 内存工具的适用范围

`step2_interval_peak(tensors, edges, seq)` 必须接收官方同版本规则产生的、尚未插入
spill 的每核 Task 图与准确优先序。它保留 L1 / UB 区分，使用包含首末 use 的闭区间，
计入 alloc-before-free 瞬时峰值。

只有当这个输入与官方 Step2 输入一致时，峰值不超过各池容量才是该 Step2 不触发
spill 的证据。该函数不能直接应用到 COPY 收缩的计算图后声称“官方零 spill”，也
不能排除 Step3 初始驻留、容量门控或 MEMORY_REUSE 边的影响。

该原型按时间优先选模板，没有集成精确的多池内存约束选择，也没有以跨核 payload
字节数替代官方新增搬运量。`edge_payload` 可选，只用于记录 cut payload。
