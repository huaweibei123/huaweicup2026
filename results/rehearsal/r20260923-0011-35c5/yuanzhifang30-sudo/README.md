# 合成直线拟合交付

负责人：@yuanzhifang30-sudo。任务：`fit-yuanzhifang30-sudo`。
分支：`codex/rehearsal-r20260923-0011-35c5-yuanzhifang30-sudo`。
控制帖：https://github.com/huaweibei123/huaweicup2026/issues/5
计算分配：https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780065751
交付 PR：https://github.com/huaweibei123/huaweicup2026/pull/7 （不合并）。逐阶段证据与未测项见本目录 [member-report.md](member-report.md)。

1. **任务目标**：以带截距普通最小二乘基线拟合 `distance_m = slope * time_s + intercept`，验证无噪声参数恢复。
2. **输入文件**：`tests/rehearsal/observations.csv`，仓库人为构造的五行合成数据；时间单位 s、距离单位 m。输入 SHA-256 见 `result.json`。全部样本用于拟合，仅检查样本内恢复，无训练/测试性能比较。
3. **输出要求**：本人脚本 `src/rehearsal/r20260923-0011-35c5/yuanzhifang30-sudo.py`、本目录 `result.json` 和说明。JSON 记录逐行预测、残差、单位、命令、环境、输入/脚本/锁文件哈希及脚本提交版本。
4. **限制条件**：使用已锁定环境中的 Python 标准库；确定性算法，`seed=null`；从 CSV 实际计算系数，不硬编码答案。截止前交付，不改原件、不合并 PR。
5. **验收标准**：n=5、斜率 2 m/s、截距 1 m、MSE≤1e-20 m²；给出最大绝对残差；队长独立重跑并验收 PR。该阈值仅用于本轮无噪声样例。
6. **截止时间**：2026-09-23T00:56:45+08:00。

## 复现

从项目根目录执行：

```sh
uv sync --locked
uv run python src/rehearsal/r20260923-0011-35c5/yuanzhifang30-sudo.py --input tests/rehearsal/observations.csv --output results/rehearsal/r20260923-0011-35c5/yuanzhifang30-sudo/result.json
```

脚本先提交、后运行，再单独提交结果，避免结果嵌入自身最终提交 SHA。重跑时生成时间和 checkout 提交可能变化，比较输入/脚本哈希、算法及全部数值，不要求 JSON 字节完全相同。

## 实际运行记录

2026-09-23T00:27:02+08:00，在 Windows、CPython 3.12.14 上完成上述命令。脚本提交 `fd8c49b0d71b1d09adb4ceba3d15cbb7dfef21d7`；输入 SHA-256 为 `816ac9cd41a026a8622d6fa81ae16bc62470717af1ba87a110ca7d4fda47d265`。

实测 n=5、斜率 **2 m/s**、截距 **1 m**、MSE **0 m²**、最大绝对残差 **0 m**；预测依次为 `[1, 3, 5, 7, 9] m`，五个残差均为零。程序计算和 JSON 输入哈希核对通过。另以 `distance=-3*time+7` 的五点数据直接调用拟合函数，恢复斜率 -3、截距 7、MSE 0，说明结果随输入变化；空数据、恒定时间和非有限观测均实际触发 `ValueError`。未将这些边界检查扩展为真实数据有效性声明。

Mailbox 完整查收并读完 1 个话题、11 条评论（00:27:17+08:00）。队长挑战 `521901e3` 已在[本人回复](https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780067408)准确回传，反向码 `1330bc82` 已由[队长回复](https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780082894)并经本人完整查收回读。队员互通和会话结束后的主动补读另行记录，不因本轮持续查收而算通过。

## 范围和未测项

这是合成无噪声基线检查，不证明真实赛题性能、抗噪能力或外推能力；本轮任务不要求图表。成员实际运行及代码审查结果与队长独立重跑分开记录。

本机为原生 Windows，未安装 WSL/Linux。按联测入口，Atlas 0.5.0 阶段阻塞；未初始化私有身份、未获得成员 grants、未读取签名 board 或字段版本、未提交 doing/review/deliverables 请求。队长允许独立计算交付，此 PR 不代替 Atlas accepted 回执或状态闭环。网页未打开，同 cursor Human/Agent、设计字段/批注、原子拒绝、旧版本冲突、离线恢复均未测。
