# 008 / 4核：Pro auto 单候选官方机制验证

**候选合法但退化，不采用为生产改进。** 官方 Makespan 为 **162326 cycles**，旧固定 bounded 为 **123060 cycles**，增加 39266 cycles（31.90801235%）。没有重复旧基线，没有参数扫描或第二候选。

材料源固定 `a556d534382cc670a6e5450661da6f8adbe638ca` 的 `AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py`。最终执行 runner 冻结 `dfa8de323b1b24087cfda02c25de9b0652b32f60`，依赖的微图公共工具未修改，哈希见 manifest。首次准备提交 `aae58ef7956738ec3254346b62f037cb32f6bd8a` 后，在执行前添加本目录 `case_008.json -text` 以保存 ZIP 原始 CRLF；最终固定 Git 字节、ZIP 成员和旧基线 graph SHA 都为 `c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d`。

## 方案质量

| 指标 | 旧 bounded 固定原件 | 本次 auto 候选 |
| --- | ---: | ---: |
| 官方 Makespan / cycles | 123060 | 162326 |
| 原图 COPY / B | 2654424 | 2654424 |
| scheduled COPY / B | 2654424 | 5898456 |
| partition / total added COPY / B | 0 | 3244032 |
| spill added COPY / B | 0 | 0 |
| Tasks | 4 | 112 |

原始 auto CLI 直接调用 `choose_and_construct`，这次实际参数为 packet=1、cut_chains=88、whole_packet=1，与事先静态预测相符。没有调用会退回 bounded 的 `integrate_construct`。即使 certificate=false 仍执行一次 E0，是本次已授权的机制测试方式；不能把它写成生产选择器通过了采用门禁。

## 模型与官方结果分开

- 作者局部模型：115736 cycles；保守上界：224551 cycles；官方：162326 cycles。
- `virgin_capacity_certificate=true`，但 `all_DDR_intervals_disjoint_in_relaxation=false`、`conditional_exact_model=false`、`conservative_dominance_certificate=false`。因此这次没有否定其已明确条件下的精确模型声明，且官方结果仍在报告的保守上界内。
- 模型与官方的 M/V 重叠都是 97272 cycles（各核重叠之和）；完整 boundary 也一致：scheduled 5898456 B、partition added 3244032 B。
- 官方 112 个 Task 的 MEMORY dependency count 全为 0，spill 为 0。现有证据不支持把退化解释为新增内存复用边。
- `official-structure-audit.json` 按官方最终时间线保存每 Task/Pipe 的实际开始顺序、操作 ID / 开始 / 结束和各 Task MEMORY 数量。官方原件未输出 MEMORY 边端点，未另跑编译器、未凭时间线补造端点。

这些事实支持“有 Pipe 重叠不等于总体更快”。共享 DDR 与 Task 编排如何分别贡献差额，尚未通过机制拆解量化；不把模型与官方差额全归给单一因素，也不宣称所有拆链候选都无效。

## 实际运行效率与预算

UTC `2026-09-24T17:23:01.204Z` 至 `2026-09-24T17:23:01.751Z`；整批 0.547423916 s。

- 新 solver 完整进程（读图、构造、模型诊断、plan/diagnostics 落盘至退出）：**0.126234875 s**。
- 外部官方 E0：**0.186556125 s**，未参与在线选优，不计入上面的 solver 时间。
- 旧基线历史 solver 0.040776375 s、外部 E0 0.127527875 s，仅保留历史口径；不是同批独占受控速度对照。
- 实际调用 **1 solver + 1 E0**，0 重试 / E1 / E2 / baseline E0；1 worker，无 GPU/Colab。限额 solver 含清理30 s、E0 含清理60 s、整批120 s；每个子进程预留最后1 s处理清理。
- Python 3.12.13、M5 Pro 48 GiB，`uv sync --locked --python 3.12` 已通过；共享主机，不宣称受控延迟或加速比。原始图的 ZIP 提取在准备期完成，原件未修改。
- 评分前 root 明确释放窗口，原授权见 `EXECUTION_AUTHORIZATION.json`。solver PID 32473 与 E0 PID 32513 均退出且进程组消失；执行门 CLOSED。运行结束已立即通知 root 释放 P2 窗口，之后只有归档。

## 原件及核验

`manifest.json` 保存固定 source/code/config/input/baseline 与运行依赖收据。旧 baseline 引用 a556 固定提交中的完整 plan/result/run/trace/log，**没有使用 Pro 附件中截断的结果前缀**。

本目录保留新 plan、完整 diagnostics/result/trace、原始官方 log/stdout/stderr、两份带 PID 的 process receipt、run、comparison 和 resource-release。不凭 exit 0 判成功；已核官方图/plan/Task联合顺序合法性、最终 scene/core/数值、完整结果/trace、哈希与清理。此批目前未提交成绩台；不把单候选结果扩写为全100图表现。

只读固定 Git 校验（0新 solver/E0）：

```sh
.venv/bin/python -B src/q1_benchmarks/pro_case008_verify.py <完整数据提交SHA> results/a/review/p1-pro-case008-e0-20260924/20260924T1720Z-pro008-auto
```
