# R4 最终审计入口（2026-09-25）

此前 `paired-bounds-v4.json` 保留为咨询发送时的**条件DDR界**快照，不直接充当官方E0全域证书。最终采用保留计算窗口和通用屏障整数gate下界：

- [本地独立核验及来源身份](local-audit-20260925T082007Z/verification.json)
- [同身份500格配对CSV](local-audit-20260925T082007Z/paired-500.csv)
- [均值精确分数与汇总](local-audit-20260925T082007Z/summary.json)
- [论文证明与限制](../../../../paper/sections/P1-R4-理论界与优化差距.md)
- [原始公开问答](../../../../AI%20chats/P1-fork-join-yuanzhifang/README.md)

2–5核当前均值1.947513173/2.739046557/3.453039755/4.025907474；证书上包络2.475951486/3.691400439/4.898841162/6.068017159；相对均值收益上限27.1340%/34.7695%/41.8704%/50.7242%。这不是可实现收益预测，500格均未闭合。没有新增求解或评分。

## 原咨询发送时的条件表

`paired-bounds-v4.json` 将固定v4的500格feed、旧静态界扫描和100个单核分母审计配对，全部graph/config身份一致。其DDR下界转移到官方binary64/EPS数值语义的证明未完成，保留原始条件标签；正式引用应使用上面的新证书表。一核正式参考点为1，重新分区的一核候选另外报告。

输入包复现：`python scripts/p1_pro_r4_packet.py --repo . --output-dir <new-directory>`。本地静态证书复核：`python -X utf8 -B scripts/p1_pro_r4_verify_static.py --output-dir <new-directory>`。两者都只读固定Git身份和做静态算术，不调用求解/编译/响应/评估。新运行的UTC与ZIP时间戳可能不同，应核对固定源哈希和逐格数字。输入包来源见AI chats清单，没有重复列成AI输出附件。
