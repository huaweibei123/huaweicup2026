# P2 三核 round8b 测量与原件审计

固定 `round8b-parallel3-spec.json` 一次执行，33/33 个 `tensor_packet` 用例成功，0 失败；33 次 solver 冷进程、33 次独立官方 E0，0 重试。源码 `e64723bdf99669c44f76d8e90ab0379a8578522e`，runner `fa6522a3266fe040379dd064092beb27c0b20a5e`，官方 E0 `45f647b395b84e9569f418fd33d62c2b8eb4d190`，spec 固定提交 `d0810e0193c30558166e89b92b5a070b6b60ba70`。

- T0 `2026-09-24T17:42:28.709426Z`；T1 `2026-09-24T17:46:14.560214Z`；批次墙钟 225.851408 秒。
- 本批 33 图逐图固定官方 A 单核分母 / 三核 E0 Makespan 的算术均值为 **2.439428299**，仅为部分样本。最低 064=1.095、066=1.453、050=1.453；逐图原值和 DDR/spill 在 `summary.csv`、`measurement-audit.json`。
- 每例新 solver 进程与独立官方 E0 分开计时；OS 文件缓存与其他 P2 流水线共享资源未控制，不作独占冷缓存效率比较。

`board-feed-*.json` 为 33 eligible / 0 failed，preflight 退出码 0。`audit_saved.py` 独立复核固定 spec/source、66 份 gzip 原始/存储哈希、268123 个 trace 操作区间、plan、E0/feed、固定分母身份和阶段非重叠，退出码 0；无新 solver/E0/E1/E2 调用。Windows 无 `dot_clean`；收尾只读扫描元数据。
