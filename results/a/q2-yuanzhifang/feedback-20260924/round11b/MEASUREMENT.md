# P2 gap_packet 单核三图试测

固定 `round11b-spec.json` 只运行一次，3/3 合法完成，3 次 solver、3 次独立未修改官方 E0，0 重试。solver 源 `384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`，spec 固定提交 `027d4bf9ccecdc82e2c5ddbce52cea5345e95b8b`，runner `fa6522a3266fe040379dd064092beb27c0b20a5e`，官方 E0 `45f647b395b84e9569f418fd33d62c2b8eb4d190`。

- T0 `2026-09-24T18:08:55.989971Z`，T1 `2026-09-24T18:09:24.707171Z`，批次墙钟 28.717135 秒。新进程 solver 端到端和外部 E0 分开记账；本机与另一 P2 流水线共享资源、文件缓存未控制。
- 新官方 Makespan 与已审计旧 `tensor_packet` 同图单核值分别为：005 **71523 vs 90450**，016 **7715523 vs 7715523**，069 **19325 vs 24009**。016 按事前固定方案执行了 E0，是相等的负对照，未据此改动用例或调用次数。
- 三图新旧额外 DDR 和 spill 均为 0 字节。逐图固定官方单核分母 B/M 的部分均值 1.212666 仅描述此三图；不能充当全 100/全 500 性能结论。

导出 feed 3 eligible、0 failed，preflight 退出码 0。独立 `audit_saved.py` 核验固定 spec/source、6 份 gzip 原始/存储哈希、23291 个 trace 操作区间、plan、E0/feed、固定分母身份和阶段非重叠；退出码 0，未调用 solver/E0/E1/E2。Windows 无 `dot_clean`，收尾只读扫描元数据。
