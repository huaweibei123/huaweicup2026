# P2 7A 二核测量

固定并行 spec 唯一运行成功：33 图均为 `tensor_packet`，单 worker，33 次新进程 solver、33 次独立未修改官方 E0，E1/E2 为 0，无重试。T0 `2026-09-24T17:11:51.384154Z`，T1 `2026-09-24T17:15:48.533995Z`，批墙钟 237.149870 秒；固定来源/输入预检另计 3.737575 秒。solver 墙钟合计 40.703133 秒，E0 合计 175.808210 秒。

保存的官方单核基线逐图 B/M 算术均值为 1.900942130，仅代表本批 33 图；二核全100尚未完成。逐图 cycles、比值、搬运量和两阶段墙钟在 `measurement-audit.json` 与 `summary.csv`。E0 的 014 单图约 56.67 秒，是本批明显长尾。

`export_board` 内置 preflight 返回 33 records / 33 eligible，`analyze` 成功；`audit_saved.py` 独立只读核查了 66 份 gzip 原始/存储哈希、固定源码、feed 引用、基线身份、272148 个 trace 操作区间与单 worker 阶段顺序，退出码 0。墙钟受共享 CPU、内存和 OS 文件缓存影响，不作为独占效率基准。Windows 不执行 `dot_clean`。
