# 容量窗口单核10图官方实测

事前固定 `round10a-spec.json` 唯一执行，10/10 个 `capacity_window` 用例成功；10次新进程solver、10次独立未修改官方E0、0在线E0、E1/E2为0、无重试。源码固定 `384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`，runner `fa6522a3266fe040379dd064092beb27c0b20a5e`，官方 `45f647b395b84e9569f418fd33d62c2b8eb4d190`。T0 `2026-09-24T18:04:24.008988Z`，T1 `2026-09-24T18:05:26.420751Z`，批墙钟62.411716秒，固定字节预检另计5.094587秒。solver合计12.819726秒，外部E0合计44.255097秒。

| 图 | 本轮官方cycles | 旧同图单核tensor_packet | 本轮spill B | 旧spill B | 路由 |
|---|---:|---:|---:|---:|---|
| 025 | 4,703,126 | 7,124,388 | 0 | 103,650,816 | capacity_window |
| 007 | 979,322 | 1,416,254 | 0 | 19,345,920 | capacity_window |
| 036 | 931,510 | 1,342,437 | 0 | 15,093,760 | capacity_window |
| 001 | 233,110 | 308,637 | 0 | 2,805,760 | capacity_window |
| 013 | 263,949 | 370,525 | 0 | 3,964,928 | capacity_window |
| 061 | 84,083 | 85,673 | 0 | 0 | capacity_window |
| 037 | 210,533 | 210,533 | 0 | 0 | guard_unchanged |
| 050 | 142,613 | 143,391 | 0 | 0 | capacity_window |
| 066 | 348,773 | 349,025 | 0 | 0 | capacity_window |
| 068 | 348,358 | 348,358 | 0 | 0 | capacity_window |

上述10图按固定官方单核A分母逐图 B/M 算术均值为本轮1.010202784、旧tensor_packet同10图0.856970604；这是事前选择的开发子集，不能冒充单核全100提升。037是路由守卫原样回退，构造方案与结果一致；其余9图的每个非空核均在元数据中有 `window≥1` 且闭区间峰值不超容量的保守证书，但证书本身不是Makespan或官方无spill结论。本轮E0在这10图确实报告spill为0。050/066/068改善极小或相同，不能仅凭这10图推断可推广收益。旧连续方案是另一固定对照，勿与旧tensor_packet混为同一基线。

`export_board`内置preflight为10 records/10 eligible；`analyze`成功。独立只读 `audit_saved.py` 核对本轮spec/source身份、20份gzip原始/存储哈希、feed引用、56444个trace操作区间、官方单核基线身份、容量路由与逐核证书口径，退出码0。逐图搬运量和墙钟在 `measurement-audit.json` / `summary.csv`。本批与另一P2 lane及系统任务共享CPU、内存和OS缓存，不作为独占速度比较。
