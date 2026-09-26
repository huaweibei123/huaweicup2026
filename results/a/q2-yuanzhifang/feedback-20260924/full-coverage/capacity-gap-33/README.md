# 容量与空隙路线：33 项固定开发试测汇总

本目录只汇总已保存的 `round10a/b`、`round11a/b/c` 原件。五批均完成、原有批次审计均通过；本次汇总未运行 solver、E0、E1 或 E2，也未修改源文件、spec、原批结果。实际新增调用为 **33 次冷进程 solver + 33 次独立未修改官方 E0**：`capacity_window` 20+20、`gap_packet` 13+13；0 自动重试。新构造源码固定 `384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`，spec 固定 `027d4bf9ccecdc82e2c5ddbce52cea5345e95b8b`。对照是唯一固定 `tensor_packet` 全 500 格源码 `e64723bdf99669c44f76d8e90ab0379a8578522e`，不混入其他算法。runner `fa6522a3266fe040379dd064092beb27c0b20a5e`、官方 E0 `45f647b395b84e9569f418fd33d62c2b8eb4d190`。

`per-unit.csv` 列出 **全部 33 项**的新旧官方 Makespan、逐图固定 A 单核分母 B/M、额外 DDR、spill、端到端 solver 墙钟和单独外部 E0 墙钟，以及正/等/负比较、实际构造路由、对应 run 原件路径。新减旧的 Makespan 与字节差值同时保留，没有仅挑改善项。按 Makespan 比较：

| 固定候选 | 单元 | 改善 | 相等 | 退化 | 额外 DDR 总差值 | spill 总差值 |
|---|---:|---:|---:|---:|---:|---:|
| `capacity_window` | 20 | 17 | 3 | 0 | -253,918,552 B | -263,629,312 B |
| `gap_packet` | 13 | 12 | 1 | 0 | +20,577,448 B | 0 B |
| 合计 | 33 | 29 | 4 | 0 | -233,341,104 B | -263,629,312 B |

这些是事前挑选的结构证伪图，不是随机样本，也不是新算法全 500 图的平均成绩。两个候选在部分四核图上重复测量，但每个固定单元都有自己的保存结果。`capacity_window` 的 solver/E0 分段墙钟合计 25.099/74.935 秒，`gap_packet` 为 37.913/59.350 秒；机器同时承载其他批次，缓存和共享负载未控制，不能据此声称独占机器的算法速度优势。每批实际 T0/T1、预算、单例墙钟和来源哈希见 `summary.json`。

`diagnostic-envelope.json` 单独保存已测格的逐格最小 Makespan 历史包络，用于观察潜在缺口。它需要预知新候选的 E0 结果来事后选择，**不是同一算法固定 SHA、入口、参数与结构分支规则的全 500 主成绩，不作论文数字或路线胜负依据**。未测的新候选没有填零、填 1 或推测分数；二核、三核仍只有原固定 `tensor_packet` 的全量测量。后续正式比较需要另行冻结统一入口和结构分支规则并完成全 500 官方测量。复用旧 E0 的前提是计划原字节、输入、配置、核数与评估语义一致；新 solver 墙钟仍须独立测量。本汇总没有进行这项正式验证。

复现命令（仓库根目录，读保存原件并重写本目录两份结果，不调用任何构造器或评估器）：

```powershell
.venv/Scripts/python.exe -X utf8 -B results/a/q2-yuanzhifang/feedback-20260924/full-coverage/capacity-gap-33/summarize_saved.py
```

脚本核对旧表完整 500 格及其保存 run/result、五批 spec 与 Git 固定字节、源文件 SHA-256 与固定提交、账本调用数、feed/preflight 哈希、原批审计哈希、33 个新 run 的身份和 E0 result 压缩原件与 feed 指标。`summary.json` 记录新旧源码哈希、五批 spec/ledger/feed/preflight/audit 的路径和 SHA-256 与逐项结果；历史包络和每核选入来源只放在独立诊断文件。运行退出码 0，得到 33 项、29/4/0；Windows 本次写入目录只读元数据扫描无 `._*`、`.DS_Store`、`__MACOSX`，不运行不存在的 `dot_clean`。
