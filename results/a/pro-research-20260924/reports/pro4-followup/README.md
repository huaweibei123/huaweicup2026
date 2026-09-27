# HuaweiCup Route 4 — reproducible research package

先读 `RESEARCH_REPORT.md`。本包含独立新原型、114 份冻结官方原件（100 case）、96 张合成图、709 次主实验的完整官方结果与 Trace、一次封包复跑和完整性索引。没有前三路新 sandbox ZIP 或旧 295 份缺失历史结果。

## 验证与最小复跑

```bash
python VERIFY.py
python tools/reproduce_run.py pilot3_c002_q2_k4_chain_stage_tail_g0.5_h8 \
  --output /tmp/huaweicup-route4-check
```

复跑目录必须不存在。该检查使用本包 `official/` 未修改 E0，比较完整 result 和 trace 的 JSON 值，不忽略时间线或列表顺序。原实验在 Linux/Python 3.13.5；团队 Python 3.12 和 Mac 需实际复跑，差异应保留，不选漂亮结果。

## 从原图在线求解

```bash
python src/solve.py official/data/case_002.json \
  --official official --cores 4 --problem 2 --budget 30 \
  --strategy frontier --output /tmp/case002_plan.json \
  --evidence /tmp/case002_evidence
```

`--strategy baseline` 是本轮四候选参照组合，不是官方 stub，也不是最强已知基线。Q1 只运行两个粗候选。构造及 E0 子进程有剩余预算 timeout，但初始索引和末尾 I/O 不属于硬实时保证。没有成功 E0 候选时返回非零，不冒充可行解。

单候选构造不跑 E0：

```bash
python src/construct.py official/data/case_002.json --cores 4 \
  --assignment chain --method stage_tail --gamma 0.5 --output /tmp/one_plan.json
python tools/check_certificate.py official/data/case_002.json /tmp/one_plan.json
```

证书仅针对限定域 Q2/Q3 singleton 的 Step2 spill，不证明完整执行合法，不预测 Makespan，不更改官方内存峰值。

## 重新运行一个实验协议

```bash
python tools/run_protocol.py audit/validation1_protocol.json --tag rerun_validation
```

协议按原顺序执行；更换 tag 后不会覆盖旧实验。正式图路径自动使用包内 official，合成路径自动使用 synthetic。重复 tag 对已存在目录报错。完整 24 组验证有 144 次官方调用；这不是秒级 smoke test。

## 学习复跑（可选）

构造、证书、E0 只需 Python 标准库。学习额外依赖 NumPy、scikit-learn、PyTorch；原环境版本见 `learning/report.json`、`audit/environment.json`。不自动安装软件或启动云运行时。

```bash
python tools/retrain.py --output-name learning_reproduced
```

使用已保存的全池 E0 标签，不重新跑 480 次 E0。该包装器只对冻结 `learn_selector.py` 做路径和输出目录替换，不改变算法、数据、随机种子与损失。原始 `learning/` 不覆盖。`.pt` 仅是本包自行训练的小 MLP state_dict，不是下载的任意可执行模型。

## 目录与统计边界

- `analysis/evidence_audit.json`、`all_e0_results.csv`：709 次主 E0 记录、560 组身份去重、17 个正式图、96 张合成图，完整文件重读校验。
- `analysis/certificate_audit.json`：521 次 singleton 审计、492 正证书、104 对同方案检查；`*_pretransfer.json` 是此前快照。
- `analysis/validation_portfolios.json`：四候选对四候选的 24 组比较。其 wall 字段是分项测量合计，不是独立冷求解器计时。
- `analysis/end_to_end.json`、`end_to_end/*/solver_report.json`：真正独立启动的冷端到端数据。
- `runs/*/run.json`：命令、原图/配置/方案/result 哈希、时间、错误；`result.json.gz`、`trace.json.gz` 是完整原输出无损压缩。
- `reproduction_check/comparison.json`：封包后又复跑一次 case002，完整 JSON 相同；不计入 709 次主实验。
- `learning/report.json`：三个 seed 和线性/树/固定动作完整指标；`dataset.npz`：特征、标签、划分与训练规范化参数。
- `audit/*protocol.json`：实验请求及预冻结信息；早期构造源快照保留。`construct_validation1_recovered.py` 由最终文本撤销后来新增 word 分支得到，SHA-256 **恰好匹配运行前保存的 validation1 源哈希**，不是推测代码等价。

历史命令保留当时绝对路径用于证据，不要求在另一台机器照抄；使用 tools 的便携入口。运行后会产生新文件；VERIFY 只核验打包时 manifest 中的 payload，不将后续新输出误算为历史原件。

完整性通过不是算法全域正确性或队长独立验收通过。
