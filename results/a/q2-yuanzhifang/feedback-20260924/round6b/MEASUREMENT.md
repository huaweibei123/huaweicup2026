# P2 单核 round6b 测量与原件审计

固定 `round6b-parallel-spec.json` 一次执行，33/33 个 `tensor_packet` 用例成功，0 失败；33 次 solver 冷进程、33 次独立官方 E0，0 重试。源码 `e64723bdf99669c44f76d8e90ab0379a8578522e`，runner `fa6522a3266fe040379dd064092beb27c0b20a5e`，官方 E0 `45f647b395b84e9569f418fd33d62c2b8eb4d190`，spec 固定提交 `737e6ab7ba07d586026f24a6e2b83e4249a5995d`。

- T0 `2026-09-24T17:17:32.380942Z`；T1 `2026-09-24T17:21:17.104414Z`；批次墙钟 224.723500 秒。
- 33 图固定官方 A 单核分母除以当前 E0 Makespan 的算术均值为 **1.024794896**。这是部分批次均值，不能替代同一算法 100/100 完整单核均值，也不等于成绩台历史最佳混合均值。
- 正负结果均保留。036 的 B/M 为 0.694，061 为 0.901，042 为 0.940；046 为 1.304，032 为 1.163。更多逐图原值见 `summary.csv` 和 `measurement-audit.json`。
- 每例为新 solver 进程，端到端 solver 阶段与独立外部 E0 阶段分别记账。OS 文件缓存与共享机器负载未控制，不作独占冷缓存效率比较。

`board-feed-*.json` 为 33 eligible / 0 failed，本地 preflight 退出码 0。`audit_saved.py` 独立读取保存原件，核对 66 份 gzip 的原始/存储哈希、210742 个 trace 操作区间、固定 spec 和源码、plan、E0、feed、固定单核分母身份与阶段非重叠；退出码 0，无新 solver/E0/E1/E2 调用。Windows 无 `dot_clean`；批次收尾只读扫描元数据。
