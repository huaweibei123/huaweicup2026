# FORM PR17 独立复核：阶段结果与两项修订请求

被复核提交：`dab91d612bd26183e12d30848b13d5fb14e071c7`。复核人：NikolaStarx。
此文记录本地独立复现，不代表 FORM 全部验收、E1/E2 验收或 PR17 可合入。

## 复现结果

- macOS / Python 3.12.13，`uv sync --locked --offline`。官方代码聚合 SHA-256 为
  `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`；运行前后均核验 114 个原件、100 个用例哈希。
- 成员提供的 18 个脚本均退出 0。另逐项比较其 17 份观察 JSON、3 份夹具与 coverage，共 21 份产物。
- 20 份与提交逐字节相同。剩余 `fplan-005-observation.json` 仅 `/fixture` 的 Windows 反斜线与 macOS 正斜线不同。这个产物路径差异被原样记录，没有悄悄归一化。
- 这只说明所交观察可复现。多数探针只记录观察而不自动判定规则正确，不能由退出码推出全部 36 条规则文字正确。
- 排序夹具的两个方案确实得到 1052 与 152 cycles，差 900；`cross_task_traffic=256`、`added_copy_bytes=768` 和 `partition_added_copy_bytes=768` 均相同。

原始提交副本、复现副本、命令、脚本哈希、标准输出、耗时和结构化差异见
`results/a/review/20260923-captain-dab91d6/`。耗时只是此次探针墙钟时间，不是 E0/E1 性能基准。
发布的终端日志仅隐去个人 checkout 前缀并去行尾空白，原日志另存本地，转换前后哈希见 `published-log-transform.json`；观察 JSON 与比较证据未作此转换。

## R1：F-EXEC-001 的量词写反（需修订）

`formal/rules.jsonl` 的 `F-EXEC-001.transition_or_predicate` 写成：
“若任一核的 order 长度 <= 1 则直接返回”。

冻结源码 `evaluation_validation.py:217-224` 实际为：

```python
if not any(len(order) > 1 for order in view['core_orders'].values()):
    return
```

因此应为“所有核的 order 长度均 <= 1 才提前返回”。该规则标题与正例叙述正确，谓词字段却与它们冲突。

独立单元反例：`core_orders={0:[1,0],1:[]}`，子图依赖 `0 -> 1`。虽然存在一个空核，
官方函数仍追加 `1 -> 0` 顺序边并报告 `task schedule: dependency cycle`。
将空核换成独立单子图核，结果仍拒绝。正向顺序与全单子图核的对照均接受。

这是**手工 view 的单元级证据**，不是正式公共入口可达性证明；公共方案入口可能提前拒绝逆序。
请修订规则谓词并加入混合长度核的回归样本，避免重写者照文字实现错误分支。

## R2：加核结论的原对照混入了工作量变化（需修订）

`formal/SPEC.md:86` 和 `F-RESOURCE-001.counterexample_tests` 用“单链 1 核=24”与
“双链 2 核=44”说明加核不保证提速。两个输入图的工作量不同；该对照能展示共享 DDR 争用，
不能单独支持固定工作量的加核结论。

本次保持图、划分、配置不变，补充实际对照：

| 图与划分 | core_schedules | makespan |
|---|---|---:|
| 两条独立链、两个子图 | `[[0,1],[]]` | 148 |
| 同上 | `[[0],[1]]` | 44 |
| 有依赖的两段、两个子图 | `[[0,1]]` | 148 |
| 同上，只添加空核 | `[[0,1],[]]` | 148 |
| 同上，改分配到两核 | `[[0],[1]]` | 1048 |

这支持“具体分配方案未必因使用更多核而更快”，不能外推为“核预算增大时最优值必然变差”。
请保留原 24/44 观察作为带宽争用证据，修正其因果解释；需要加核论述时使用同图对照。

## 复现入口与剩余边界

```sh
uv sync --locked
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/a_materials.py --extract
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B src/review/a_r1_form_reproduction.py --output results/a/review/my-form-reproduction
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B src/review/a_r1_form_probes.py
```

在独立 worktree 执行。复现驱动要求成员脚本与原始产物仍匹配固定提交；它拒绝覆盖已有输出目录，
但成员脚本会重写本 worktree 中其原定观察/夹具/coverage 路径。不要在他人工作区运行。

R1/R2 的输入、图哈希、划分哈希及观察位于 `captain-probes.json`。
没有修改官方原件、公共真值、阈值或成员提交。尚未穷尽其他规则、正式 100 用例语义、未覆盖机制，
也未检查用户最终浏览器体验。当前未收到可拉取的本轮 E1/E2 代码，因此未给出速度、零差分或误差合格结论。

## 后续定点复核：4d34f21

被复核修订为 `4d34f21fc113e456ee0fe7ef1dae9ee5a56319c5`。独立 detached worktree 中，
两个新增脚本的观察 JSON 均与提交逐字节相同；6 个单元结果和 7 个耗时观察符合实测。
仅 F-EXEC-001、F-RESOURCE-001 两张规则卡改变；核心量词已改正，同图对照及其结论边界已补全。
114 个官方原件/100 用例哈希仍通过。详见 `fix-recheck-4d34f21.json`。

仍需更正一个新增说明：`verify_fexec_r2.py` F 用例只有一个长度为 2 的核，
`any(len(order)<=1)` 与 `all(len(order)<=1)` 都是 False。它在两种量词下都不提前返回，
所以只是单核逆序拒绝对照，不能称作“反向量词会漏判的最小情形”。
A/B 的混合长度反例仍然有效；这个说明问题不推翻核心修订和已有观察数值。
请修正脚本注释/记录 note 与对应论文措辞，不改数字凑结论。

## 最新定点复核：86b095f

`86b095fc6eff27f91a26c38424b460280caae926` 已修正 F 用例说明及其派生记录，区分了
A/B 的拒绝结果差异、C 的分支差异但接受结果相同，以及 D/E/F 的一致控制。
两个受影响脚本再次在独立工作区运行；2 份 JSON 与新提交逐字节一致，6 个分类与 7 个耗时数值不变。
规则、SPEC、论文及探针中 E0 术语也已澄清。见 `fix-recheck-86b095f.json`。

本报告提出的 R1、R2 及后续 F 说明修订已在限定范围内确认，当前没有这三项的未解决请求。
其余未覆盖机制及全 FORM 验收仍未由本次复核覆盖；状态继续 review，不据此宣称 E1/E2 已通过。
