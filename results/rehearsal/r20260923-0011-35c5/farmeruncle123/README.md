# 合成直线拟合交付

负责人：@farmeruncle123。任务：`fit-farmeruncle123`。
分支：`codex/rehearsal-r20260923-0011-35c5-farmeruncle123`。
控制帖：https://github.com/huaweibei123/huaweicup2026/issues/5
计算分配：https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780065751
交付 PR：见本目录同 PR（不合并）。逐阶段证据与未测项见本轮联测报告。

1. **任务目标**：以带截距普通最小二乘基线拟合 `distance_m = slope * time_s + intercept`，验证无噪声参数恢复。
2. **输入文件**：`tests/rehearsal/observations.csv`，仓库人为构造的五行合成数据；时间单位 s、距离单位 m。输入 SHA-256 见 `result.json`：`816ac9cd41a026a8622d6fa81ae16bc62470717af1ba87a110ca7d4fda47d265`。全部样本用于拟合，仅检查样本内恢复，无训练/测试切分。
3. **输出要求**：本人脚本 `src/rehearsal/r20260923-0011-35c5/farmeruncle123.py`、本目录 `result.json` 和说明。JSON 记录逐行预测、残差、单位、命令、环境、输入/脚本/锁文件哈希及脚本提交版本。
4. **限制条件**：使用 Python 标准库（无新增依赖）；确定性算法，`seed=null`；从 CSV 实际计算系数，不硬编码答案。截止前交付，不改原件、不合并 PR。
5. **验收标准**：n=5、斜率 2 m/s、截距 1 m、MSE≤1e-20 m²；给出最大绝对残差；队长独立重跑并验收 PR。该阈值仅用于本轮无噪声样例。
6. **截止时间**：2026-09-23T00:56:45+08:00。

## 复现

从项目根目录执行（脚本仅依赖 Python 标准库，任意 `python3` 可运行）：

```sh
python src/rehearsal/r20260923-0011-35c5/farmeruncle123.py --input tests/rehearsal/observations.csv --output results/rehearsal/r20260923-0011-35c5/farmeruncle123/result.json
```

脚本先提交、后运行，再单独提交结果，避免结果嵌入自身最终提交 SHA。重跑时生成时间和 checkout 提交可能变化，比较输入/脚本哈希、算法及全部数值，不要求 JSON 字节完全相同。

## 实际运行记录

2026-09-23T00:4x+08:00，在 Windows、CPython 3.13.14 上完成上述命令（托管运行时，标准库）。脚本提交 `0d34651d0105c086894cf7fd3e7044456d23f46a`；输入 SHA-256 为 `816ac9cd41a026a8622d6fa81ae16bc62470717af1ba87a110ca7d4fda47d265`。

实测 n=5、斜率 **2 m/s**、截距 **1 m**、MSE **0 m²**、最大绝对残差 **0 m**；预测依次为 `[1, 3, 5, 7, 9] m`，五个残差均为零。程序计算和 JSON 输入哈希核对通过。系数由 CSV 实际计算，未硬编码。

Mailbox 完整查收并读完本轮 #5 全部评论（25 条）。队长挑战 `15c7fbe9` 已在[本人回复](https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780461650)准确回传，反向码 `8df3658e` 待[队长回传](https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780461650)后经完整查收回读。队员互通码 `0081b2d9` 已在[独立回复](https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780462116)准确回传。

## 范围和未测项

这是合成无噪声基线检查，不证明真实赛题性能、抗噪能力或外推能力；本轮任务不要求图表。成员实际运行及代码审查结果与队长独立重跑分开记录。

本机为原生 Windows，未安装 WSL/Linux（本客户端沙箱禁用 `wsl.exe` 检测，无法在此确认；按 `docs/rehearsal/START_HERE.md` 第 16 行与 `AUTONOMOUS-001`，Atlas 0.5.0 阶段标记阻塞）。未初始化私有身份、未获得成员 grants、未读取签名 board 或字段版本、未提交 doing/review/deliverables 请求。队长允许独立计算交付，此 PR 不代替 Atlas accepted 回执或状态闭环。网页未打开，同 cursor Human/Agent、设计字段/批注、原子拒绝、旧版本冲突、离线恢复均未测。Windows 补丁（`WINPATCH/ASSIGNED-001`）由 @yuanzhifang30-sudo 承接，本人不重复开发。
