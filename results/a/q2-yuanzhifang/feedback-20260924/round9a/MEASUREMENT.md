# P2 9A 五核测量

固定 parallel3 spec 完成 001–033 共 33 图；tensor_packet 单 worker，各 33 次新 solver 与独立官方 E0，E1/E2 为 0，无重试。

T0 2026-09-24T17:25:55.844186Z；T1 2026-09-24T17:30:13.047369Z；批墙钟 257.203343 秒，预检另计 8.587672 秒。solver 逐图墙钟合计 48.654557 秒，外部 E0 合计 183.572649 秒。共享 CPU、内存及 OS 缓存未控制。

固定官方单核 A 基线逐图 B/M 算术均值 3.9628932318325583，仅代表本批 33 图。完整逐图结果与搬运量见 summary.csv 和 feed。

固定算法 e64723bdf99669c44f76d8e90ab0379a8578522e，runner fa6522a3266fe040379dd064092beb27c0b20a5e，官方 E0 45f647b395b84e9569f418fd33d62c2b8eb4d190。逐图 graph/config/official 哈希及 baseline 身份见 run.json、measurement-audit.json。

export_board preflight 33 records / 33 eligible；analyze 成功；audit_saved.py 只读核对 66 份 gzip 原件、固定源码、feed 引用、270947 个 trace 操作区间及单 worker 阶段顺序，退出码 0。Windows 仅只读扫描元数据，未运行 dot_clean。