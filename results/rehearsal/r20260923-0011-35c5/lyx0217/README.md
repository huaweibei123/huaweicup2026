# lyx0217 合成直线拟合结果

本目录是 `r20260923-0011-35c5` 真机预演的独立计算交付，只使用人为构造的无噪声数据，不代表华为杯真实赛题结果。

## 任务与输入

- 目标：从五行观测拟合 `distance_m = slope * time_s + intercept`。
- 输入：`tests/rehearsal/observations.csv`，`time_s` 单位为秒，`distance_m` 单位为米。
- 输入 SHA-256：`816ac9cd41a026a8622d6fa81ae16bc62470717af1ba87a110ca7d4fda47d265`。
- 方法：标准库实现的闭式普通最小二乘；确定性算法，`seed=null`，未增加依赖。

## 复现

```powershell
uv run python src/rehearsal/r20260923-0011-35c5/lyx0217.py
```

脚本提交：`ba16ceae67752816aaad698788db6ba5c2f2ec9c`。运行环境为 Windows 11、CPython 3.12.13；脚本和 `uv.lock` 的完整哈希记录在 `result.json`。

## 结果

| 指标 | 实测值 |
| --- | ---: |
| n | 5 |
| slope | 2.0 m/s |
| intercept | 1.0 m |
| MSE | 0.0 m^2 |
| 最大绝对残差 | 0.0 m |

`result.json` 包含五行逐行预测与残差。该结果只验证这份合成输入和脚本的可复现性，不证明真实观测、噪声数据或正式赛题模型的性能。Atlas 签名状态闭环因本机缺少 WSL/Linux 未在此交付中验证。
