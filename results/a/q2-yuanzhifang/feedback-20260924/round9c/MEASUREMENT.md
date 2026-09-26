# P2 9C 五核测量

固定 parallel3 spec 完成 067–100 共 34 图；tensor_packet 单 worker，各 34 次新 solver 与独立官方 E0，E1/E2 为 0，无重试。

T0 2026-09-24T17:38:37.501307Z；T1 2026-09-24T17:44:01.159445Z；批墙钟 323.658452 秒，预检另计 6.582588 秒。solver 逐图墙钟合计 60.734680 秒，外部 E0 合计 227.811963 秒。共享 CPU、内存及 OS 缓存未控制。

固定官方单核 A 基线逐图 B/M 算术均值 4.309730336287904，仅代表本批 34 图。完整逐图结果与搬运量见 summary.csv 和 feed。

固定算法 e64723bdf99669c44f76d8e90ab0379a8578522e，runner fa6522a3266fe040379dd064092beb27c0b20a5e，官方 E0 45f647b395b84e9569f418fd33d62c2b8eb4d190。逐图 graph/config/official 哈希及 baseline 身份见 run.json、measurement-audit.json。

export_board preflight 34 records / 34 eligible；analyze 成功；audit_saved.py 只读核对 68 份 gzip 原件、固定源码、feed 引用、423561 个 trace 操作区间及单 worker 阶段顺序，退出码 0。Windows 仅只读扫描元数据，未运行 dot_clean。

## 三批全 100 图

9A/B/C 的 case 001–100 无重复、无缺失；三批均 completed，100 次新 solver + 100 次独立官方 E0，0 E1/E2，无重试。每图取固定官方单核 A 基线 cycles 除以本算法五核 B cycles，再对 100 个比值作算术平均，结果为 **3.89603690404328**。最小逐图比值 1.160162650968016，最大 9.84688972667295；100 图均大于 1。该均值只代表固定 tensor_packet 算法本轮全量，不等同成绩台历史最佳混合均值。

三批批墙钟合计 846.154888 秒，solver 逐图墙钟合计 167.492125 秒，外部 E0 逐图墙钟合计 590.478467 秒；跨批间的导出、审计与等待不计入批墙钟。三路共享资源与 OS 缓存状态未控制，不能据此声明独占机器或冷缓存提速。各批独立审计合计核对 969758 个 trace 操作区间。