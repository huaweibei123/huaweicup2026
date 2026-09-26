# P2 gap_packet 五核四图试测

固定 `round11c-spec.json` 只运行一次，4/4 合法完成，4 次 solver、4 次独立未修改官方 P2 E0，0 重试。solver 源 `384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`，spec 固定提交 `027d4bf9ccecdc82e2c5ddbce52cea5345e95b8b`，runner `fa6522a3266fe040379dd064092beb27c0b20a5e`，官方 E0 `45f647b395b84e9569f418fd33d62c2b8eb4d190`。

- T0 `2026-09-24T18:11:06.291380Z`，T1 `2026-09-24T18:11:24.454594Z`，批次墙钟 18.163263 秒。新进程 solver 端到端和外部 E0 分开记账；本机与另一 P2 流水线共享资源、文件缓存未控制。
- 以下新值来自**本批独立 P2 E0 原件**，旧值来自已审计 `full-coverage/all500/per-cell.csv` 的同图五核 `tensor_packet`；额外 DDR 与 spill 单位均为字节。

| 图 | gap M | 旧 tensor M | gap 额外 DDR | 旧额外 DDR | gap/旧 spill |
|---|---:|---:|---:|---:|---:|
| 069 | 12679 | 16295 | 536664 | 522926 | 0 / 0 |
| 071 | 10529 | 14522 | 394488 | 380624 | 0 / 0 |
| 005 | 47017 | 58532 | 2346552 | 2165300 | 0 / 0 |
| 086 | 66039 | 67995 | 3458936 | 2521524 | 0 / 0 |

四图官方 Makespan 均改善，额外 DDR 均增加，086 仅有较小 Makespan 收益。四图逐图固定官方单核分母 B/M 的部分均值 1.901646 仅描述此小样本，不能充当五核全量结论。

P3 原方法属于 `a37eb931a22fb7df7e0d00d193538ce5289ae045`，准确来源包括 `src/q3_yuanzhifang/gap_list.py`、`dag_list.py`、`gap_calendar.py`。其固定第 8 批数据提交 `data412bdf6d92207999099a7391a6dfcf2247b0950c` 报 069/k5 P2=12679；第 9 批数据提交 `b3d7d266b74b104139d4500a73f5cf03dfc4269a` 报 071/005/086 的 k5 P2=10529/47017/66039。这些是**外部作者参考记录**，不是本批成绩来源；数值相同由本批保存的独立 plan、E0 result/trace 与原件审计核实。

导出 feed 4 eligible、0 failed，preflight 退出码 0。独立 `audit_saved.py` 核验固定 spec/source、8 份 gzip 原始/存储哈希、19193 个 trace 操作区间、plan、E0/feed、固定分母身份和阶段非重叠；退出码 0，未调用 solver/E0/E1/E2。Windows 无 `dot_clean`，收尾只读扫描元数据。
