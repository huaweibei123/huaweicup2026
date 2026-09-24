# 082 / 四核 attention-ffn 正式原件独立读回审计

**通过本次只读审计。** 新运行账本为 **1 solver + 1 online E0**，0 E1/E2、0重试记录；本审计新增调用全部为0。新正式计划与事先静态计划逐字节完全相同，未把重新构造或新评分混进读回。

| 指标 | 旧 attention | 新 attention-ffn | 新−旧 |
|---|---:|---:|---:|
| 官方Makespan（cycles） | 183595 | 172746 | -10849（下降5.9092%） |
| 官方额外搬运 added_copy_bytes | 3557904 B | 2858128 B | -699776 B（下降19.6682%） |
| 官方调度搬运 scheduled_copy_bytes | 4149910 B | 3450134 B | -699776 B |
| 官方spill | 0 B | 0 B | 0 |
| Cache字节命中率 | 36.074886% | 38.103584% | +2.028697个百分点 |
| 完整solver进程墙钟（s） | 0.566816833 | 0.591535125 | +0.024718292 |
| 已包含于solver墙钟的online E0分项（s） | 0.305377042 | 0.319260542 | — |

新单格批次墙钟 0.735667944s（含runner处理）；与完整solver进程墙钟分开，不相加。两次均为单次、非独占观测，不足以声称程序速度显著改变。新方案质量改善，观测到的求解墙钟略增，应同时报告。

## 身份、调用账及原件

- 新固定source `e3df1cdca0729a972b5408bc6bd2f9e8ffbc90f5`，实际执行worktree HEAD相同；逐项核对stage记录的 **35** 个source/input/hash：tracked文件匹配该提交与当前字节，忽略的原图则匹配该提交中的冻结原ZIP及manifest。官方10个Python文件逐字节匹配冻结清单。
- 旧原件直接从固定发布 `b934eb8485056059512b1121774a9c15a9350e2f` 读取，其as-run solver为 `80fabde1bd49faf28765d3caa8541780579d89d4`；不是从之后修改的目录猜旧结果。旧plan/result/receipt同时与前次静态审计原件相同。
- 相同graph `f230fbc200ad75797f3024f84431d1d26f7747d6a284378ee83eabde77b7e70c`、config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`、official `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。
- 新plan SHA256 **`2c35a3c2917c45650e1b1781bca205f92375c7df71f883c34e1c3a48f7b70a35`**，与 `/tmp/q3-attention-ffn-static/new-plan.json` 完全相同；新候选meta与静态meta相同、attention源文件字节相同。
- 新完整result gzip SHA256 `365e84b33bafcf955dd93564807346e53bd39bbb4228c386c81175f0cf26765d`；receipt SHA256 `202b632fa51367277b82e43dc60779a4c683b42c3cc86411baa12f5c23111d6a`。均与run引用一致，解压后官方metrics与run/receipt逐字段相同。
- batch仅1record、预算使用1、run调用1solver/1E0、receipt official_e0_calls=1、仅1成功candidate、evaluations.json仅ordinal0成功记录、仅evaluated-plan-0文件。在线实际评价的plan、seed plan和最终plan字节一致，seed/full result字节一致；无第二候选或重试记录。
- 命中率独立按 `869648/(869648+1412678)` 复算，与官方值一致，未使用按次数命中率替换。

## 原操作与轨迹一致性

静态 `derive_multicore_plan` 通过；原4113个计算操作在新plan中各出现一次、保持singleton，并在完整官方timeline中各出现一次，所属核、op类型、pipe和原cycles时长全部一致。四核M/V共8条原计算pipe序列与提交序列完全相同，同pipe无重叠；6258条原tensor/direct计算依赖全部满足执行先后，跨核至少等待500；总timeline最晚结束与Makespan一致。

21个FFN均同核，旧19/21分核变为0/21；静态内部远端payload代理282624 B→0与相同计划身份对应。实际额外搬运减少699776 B，但它不是内部payload代理的直接等式：分配、最终次序与其他边界也可能变化，Cache命中率也变化。当前证据支持这个候选改善了该格，不足以分离各机制对10849周期收益的贡献。

事先严格L500=166910，新官方172746，界与实际一致；差5836周期。静态界并未预言具体收益。本任务是**独立读回与算术/轨迹检查，不是独立重跑**，不扩展为全部用例、其他核数或其他平台验收。

完整逐项identity、source、artifact、calls、metrics及核对结果见 `audit.json`。所有写入仅 `/tmp/q3-attention-ffn-audit`，未修改仓库、未运行solver或任何额外E0。
