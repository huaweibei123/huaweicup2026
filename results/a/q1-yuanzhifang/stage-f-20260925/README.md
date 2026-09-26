# Stage F：051/k5 单例证伪完成

实测合法但退化：E0 Makespan **325520**，旧 C 为 **253856**，增加 **71664 周期（28.2302%）**。solver 冷进程 **1.2007275 秒**，独立 E0 **2.0575621 秒**。本批实际 **1 solver + 1 E0，0 retry/E1/E2**；所有进程正常结束，无失败记录。共享资源窗口可能有 P2 至多2个 worker，本 P1 为1 worker，不能据此声称独占环境或跨批程序提速。

固定作者 `916a19e57c041ca5dc4aa1f3748e23726464b762`，实际 runner `2b79198675838415baee96ccca64e81067ff6781`。批次 T0 `2026-09-24T17:16:28.123478Z`，T1 `2026-09-24T17:16:31.674371Z`，3.5507643 秒；solver 起止与 E0 起止另保存在原 run/events。预算全部封存，不追加评分。

新方案总额外 DDR **15,205,872 B**，比 C 增加 **6,160,476 B**，全部为分区增加，spill 为0。已从两个固定计划逐 tensor 对照：94个新增32KiB重链切口各增加一次 COPY_OUT/IN（6,160,384 B），另增加46个2B COPY_IN（92 B）。12个外部32KiB输入仍各加载24次，重复外部输入9,043,968 B没有减少。

F 调度搬运15,599,090 B在60 B/cycle容量下的必要时间至少259985周期，已超过旧 C 的完整253856周期。故这一固定 F 分区无法赢过 C；R 模型的166540周期改善没有抵消搬运增加。这个必要资源界不是325520周期的完整因果分解。

原件与比较见 [run/comparison.csv](run/comparison.csv)、[run/ddr-analysis.json](run/ddr-analysis.json)、[run/copy-delta-analysis.json](run/copy-delta-analysis.json)。标准 feed 为 [board-feed-20260924T171730Z-stage-f.json](board-feed-20260924T171730Z-stage-f.json)。[本地预检](precheck-local.json) `valid=true, eligible=1`；科学验收、维护者接收与实际上台不由格式预检代签。复现及范围说明见 [REPORT.md](REPORT.md)。

原件固定提交 `d18529b4189d4b6091fea0cb1ddcb10865745f4c` 的 [Git 字节预检](precheck-fixed-d18529b.json) 同样 `valid=true, eligible=1`；未调用 solver/E0 或中央服务。

## 原准备记录（保留）

算法 `q1-guarded-split-chain-star / twelve-four-fixed-tail-v1`，作者源码固定 `916a19e57c041ca5dc4aa1f3748e23726464b762`。任务与完整预算见 `tasks/a/q1-yuanzhifang-stage-f.md`。

准备时只冻结 runner 与导出器，未启动真实 solver/E0。新授权为最多 1 solver + 1 E0、1 worker、30/90 秒、全批 180 秒、0 retry/E1/E2。后来父会话明确 START：E4 已于 `17:14:10.325759Z` 完成；P2 用户改为允许共享并行，旧串行窗口约定随明确授权更新，实际 token 保存在 `run/protocol.json`。

旧 Stage C 051/k5 的 253856 周期只引用 `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a` 已有原件；官方 singlecore 分母也复用，不新增评价。R=166540 是忽略 COPY/DDR/容量的模型值；不得放入 Makespan 成绩字段。静态重复输入加载分析于实测后生成，不猜测 trace readiness 或唯一耗时归因。

`preparation-checks.json` 记录实际零评分预检。后续 `run/` 只允许首次创建，保留官方 plan/result/trace/log、全部 stdout/stderr、参数/源码/输入身份、UTC、完整 solver wall、独立 E0 wall、失败和调用账。Windows 无 dot_clean，只在本输出范围扫描元数据残留。

准备阶段没有可提交的成功 board feed；实测后导出独立不可覆盖快照，固定 Git 原件预检，再交父研究会话联系成绩台维护者。此目录存在不表示已执行、已上台或已验收。
