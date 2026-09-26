# 容量窗口与重分量路线四核10图官方实测

事前固定 `round10b-spec.json` 唯一执行，10/10个`capacity_window`变体用例成功；10次新进程solver、10次独立未修改官方E0、0在线E0、E1/E2为0、无重试。源码固定`384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`，runner`fa6522a3266fe040379dd064092beb27c0b20a5e`，官方`45f647b395b84e9569f418fd33d62c2b8eb4d190`。T0`2026-09-24T18:07:55.157993Z`，T1`2026-09-24T18:08:43.437481Z`，批墙钟48.279414秒，固定字节预检另计5.236837秒。solver合计12.279016秒，外部E0合计30.679839秒。

| 图 | 本轮官方cycles | 旧同图四核tensor_packet | 本轮spill B | 旧spill B | 本轮分区额外B | 实际路由 |
|---|---:|---:|---:|---:|---:|---|
| 025 | 1,177,484 | 2,650,833 | 0 | 95,195,136 | 82,944 | capacity_window |
| 007 | 246,118 | 417,689 | 0 | 11,727,360 | 82,944 | capacity_window |
| 036 | 233,584 | 503,212 | 0 | 11,223,040 | 3,456 | capacity_window |
| 001 | 58,984 | 78,028 | 0 | 622,592 | 3,456 | capacity_window |
| 013 | 66,982 | 81,714 | 0 | 0 | 24,576 | capacity_window |
| 061 | 22,400 | 27,318 | 0 | 0 | 128,512 | heavy_component_packet_override |
| 037 | 53,852 | 53,852 | 0 | 0 | 614,400 | guard_unchanged |
| 050 | 71,014 | 103,057 | 0 | 0 | 1,529,690 | heavy_component_packet_override |
| 066 | 157,982 | 247,248 | 0 | 0 | 4,754,212 | heavy_component_packet_override |
| 068 | 147,316 | 292,385 | 0 | 0 | 3,384,362 | heavy_component_packet_override |

本10图按固定官方单核A分母逐图B/M算术均值为本轮3.430905060、旧tensor_packet同10图2.319595384。9图改善，037守卫原样回退且相同；这是事前选的开发子集，不能冒充四核全100提升。025/007/036的E0同时报告Makespan下降和spill归零，但仍存在表中的分区额外DDR搬运。`capacity_window`路线的5图逐个非空核在元数据中有window≥1及闭区间峰值不超容量的保守证书。061/050/066/068转到独立的重分量packet分支，**没有容量证书**，其无spill与Makespan改善来自本批官方E0而非理论保证。037既无证书也未改方案。

`export_board`内置preflight为10 records/10 eligible；`analyze`成功。独立只读`audit_saved.py`核对spec/source身份、20份gzip原始/存储哈希、feed引用、67492个trace操作区间、官方单核基线身份、实际路由与逐核证书口径，退出码0。逐图搬运和墙钟在`measurement-audit.json`/`summary.csv`。本批与另一P2 lane及系统任务共享CPU、内存和OS缓存，不作为独占速度比较；旧连续方案另列，不能混作旧tensor_packet基线。
