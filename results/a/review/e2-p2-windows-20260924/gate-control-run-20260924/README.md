# Windows 独立门禁控制：一次 G1–G4 全通过

1. **目标**：验证指定 Job + nonce + ready/ACK 机制及最后 Job 句柄关闭语义；仅控制可靠性，不是 E2/算法终验。
2. **输入**：冻结 as-run `569c65f2673d6fc2a99507f151ca04b814e1dc68`；[明确批准](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805365084)；既有 Windows venv Python 3.12.14 与固定 contract；无正式图/评价输入。
3. **产物**：evidence/ 完整脱敏运行工件、RAW_SHARED_HASHES.json 原件/共享映射、VERIFICATION.json 逐项复核；Git 字节复核与公开发布收据后续同窗保存。
4. **限制**：一次父 runner，4 个受控 CreateProcess 请求，无重试；每个 Job 实际观察 3 个 OS 进程，共 12（父运行器另计，不冒称整个系统只有12个进程）。E0/E1/E2/debug/BC DLL/编译/安装/正式图/P3/Q2接入均0；原C/D/E不运行，原证据不改。
5. **验收**：四项契约判据均满足，下表列实测。没有意外错误、清理重开或显式 terminate；所有已记录句柄关闭成功。G4 的预期 Job 强退与异常强制清理是两回事。
6. **截止**：外层 T0=`2026-09-24T00:42:53.3232152+00:00`，Stopwatch=`203862753852`、frequency=`10000000`，Tick64=`20386250`。300秒包含本报告、Git发布与公开回读；45秒准备，以这个更早外层T0计，不沿用内层main起点。

外层批准文件准备至父启动 0.8040068 秒；至父退出 3.2331282 秒（Stopwatch），退出码0。内层main T0=`2026-09-24T00:42:54.507124+00:00`，controls_wall=2.032秒，仅作内层统计。UTC与单调钟是顺序采样，不把两个读数当同一瞬间；完整交付以原外层单调起点继续计时，UTC原始7位小数保留。父及四例stdout/stderr全为空，空原件也保存。

| 用例 | launcher / 实际脚本 PID | 单例 ms | 实测结果 |
| --- | --- | ---: | --- |
| G1 | 29160 / 26132 | 578 | 指定Job完整PID集合[29160,38692,26132]；query先关闭、ACK后payload=true；三进程正常退出0，active=0 |
| G2 | 39724 / 36304 | 469 | nonce_mismatch，退出21，无ready/payload，active=0 |
| G3 | 30436 / 34344 | 454 | 指定空Job B的API成功、member=false、query_closed=true；退出22，无ready/payload；B前后空，A active=0 |
| G4 | 7548 / 11004 | 437 | 精确成员验证后query已关闭；完整跟踪[7548,38432,11004]，父不发ACK，最后Job句柄关闭后16ms全部退出 |

G4 子自退出deadline=20404390；关闭前tick=20389421、余量14969ms；全部退出tick=20389437，距自退出仍14953ms。2秒窗口/至少6秒关闭前余量/至少4秒退出后分离均满足。没有ACK、child.final或payload，也没有cleanup重开/terminate。三个实际退出码均0：本次强退判断来自明确关闭、完整进程句柄观察和远早于自退出期限的证据，不把0误判成自然ACK超时，也不伪造非零退出码。

每次CreateProcess返回的launcher PID与实际脚本PID不同；系统实际观察到3个进程，与旧失败时观察到2个不同。这是本次真实观测，不推测未保存的第三进程角色或祖先链；没有为解释它增开探针。所有启动均先暂停、Assign成功、Resume返回1；继承白名单只有3个stdio duplicate，query/job/process/thread/observer检查不可继承。

原始gate/ACK中的完整nonce和Job随机名仅私有保留，共5个公开文件将对应值替换为SHA-256；其他文件原字节复制。目录 `* -text` 保证Git不改CRLF。批准引用、as-run源码hash、真实PID与时间、原始/共享hash均可交叉核对。源码保持冻结；只有控制结束后新增本结果目录。

该结果只覆盖一次真实Windows环境的4项有限控制，不是长期/并发稳定性或所有故障注入验证，不满足或替代E2速度/误差、官方Makespan、完整求解wall或真机收益验收。后续C-full/D/E需另固定代码、调用数和窗口后获明确批准。Actions按免费协作规则停用且未触发，不算CI通过；不写Atlas/done。

## 事后纯文档审计：最终回读超窗

G1–G4功能判据全部通过，外层控制3.2331282秒不变；但**完整交付没有满足300秒窗口**。证据提交556b210及公开Issue5805420301/PR的完整正文、作者、证据HEAD回读完成于279.9353438秒，记录于PUBLICATION.json。随后收据提交49f9115的最终PR HEAD回读实际在308.1841277秒，超过预算8.1841277秒。最终原始回读记录见evidence/final-delivery.json及POST_WINDOW_AUDIT.json；后者是窗口结束后的文档审计，不延长或重置窗口，不修改原始控制证据，不补测、不新增评价。

PUBLICATION.json中的outer_t0_utc被PowerShell自动解析后显示为2026-09-24T08:42:53.3232152+08:00，与原件00:42:53.3232152+00:00是同一时刻，7位小数未丢失。所有elapsed秒数均由原Stopwatch ticks/frequency计算；保留原件，不把显示时区变化误作计时更改。四项功能通过与交付超窗必须分别审核，不能概括成整轮全部通过。
