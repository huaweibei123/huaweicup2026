# P2 Windows C/D/E 一次续测：C/D/E-search通过，完整adapter CLI失败后停止

1. **目标**：按新门禁补验完整类型、pool排序/回收/超时恢复/RSS与CLI契约。只测既有合成输入，不是E2整体/算法终验。
2. **输入**：as-run固定 `a96f3ff445e6e85febb9fc13e4a0f2341fe10d3f`，bundle `d1c404073b8742d6441ac09e9856193a05aa71885f4d3d0ea5b54ff83d0e2e73`；[明确一次批准](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805687858)。6份原件、34份生产/依赖、Python 3.12.14/NumPy 2.5.3、既有BC DLL和spawn标准库身份通过；ABI=1，无安装或重编译。
3. **产物**：127份完整运行原件的共享副本、RAW_SHARED_HASHES.json逐文件raw/shared/Git映射、VERIFICATION.json；保留空stdout/stderr、pickle/typed/canonical、成功与失败CLI产物、全部门禁/进程/清理/账本证据。完整原件私有保留，公开副本去nonce、随机Job名称和个人路径。
4. **限制**：唯一包装器一次；首非预期失败后没有补投、补测、改参数或源码。12条record、3次显式E0请求，潜在完整E0预留15/授权17，剩余2封存。debug、正式图、P3、Q2、原生构建、安装为0；未触发Actions，不写Atlas/done。
5. **验收**：preflight、C_full、D_order、D_timeout、D_rss、E_search通过；E_full_valid失败，E_full_invalid未运行。父包装器未强杀，但E_full_valid阶段控制器确实执行Job强制清理，最终所有7个Job的ActiveProcesses=0。不能概括成全程无强制清理或整套通过。
6. **时间**：外层T0=`2026-09-24T01:15:51.2572454+00:00`，Stopwatch=`223642109096`、frequency=`10000000`、Tick64=`22364187`；准备至父启动0.8035492秒，父结束于外层16.9917732秒，exit1。900秒完整交付截止01:30:51.2572454Z，600/750秒发布/最终回读目标分别01:25:51.2572454Z与01:28:21.2572454Z。评价和阶段清理均在300秒内结束；后续仅证据整理与发布，T0不重开。

## 实际结果

| 阶段 | 用时 ms | 结果 | record / 显式E0 / 潜在E0预留 | Job累计OS进程 | 控制器Job强清理 |
| --- | ---: | --- | ---: | ---: | --- |
| preflight | 1610 | ABI=1，固定DLL路径 | 0 / 0 / 0 | 3 | 否 |
| C_full | 1468 | 原Python类型和值、canonical及旧truth均一致，两个core字段键均为int 0/1 | 1 / 1 / 2 | 4 | 否 |
| D_order | 3344 | 0–3顺序；两slot达到count=1后旧process关闭且换PID，invalid行符合契约 | 4 / 0 / 4 | 7 | 否 |
| D_timeout | 1985 | 预列tiny timeout；下一候选native成功恢复 | 2 / 0 / 2 | 5 | 否 |
| D_rss | 2266 | 两行均有正RSS、peak_rss_threshold且换PID | 2 / 0 / 2 | 5 | 否 |
| E_search | 2110 | native / invalid / native，索引0/1/2，CLI exit1及metadata符合预期 | 3 / 0 / 3 | 6 | 否 |
| E_full_valid | 1891 | 官方CLI成功；adapter返回0但结果文件不存在，FileNotFoundError | 0 / 2 / 2 | 9 | 是，active 3→0 |
| E_full_invalid | — | 首失败后未启动 | 0 / 0 / 0 | — | — |

C-oracle与C-pool-full的pickle、typed.json、canonical.json均分别逐字节相同（未反序列化pickle），不仅比较了摘要。保留旧失败所缺的原始类型证据；memory_peak_by_core和step3_by_core键都是int。成功记录makespan=506；另外两个评分字段也由冻结typed比较逐值检查，不能仅凭makespan推全结果相同。

Job进程表是每stage整个生命周期的累计数，共39，不是瞬时峰值，也不含父包装器/父runner或交付工具。配置的Job活跃上限为12；实际峰值未采样证明，不写成测得峰值12。记录到10个不同worker PID。源码与收据可归因的程序启动/转交为父1、stage7、直接嵌套CLI3、worker10、adapter execv转交推断1，共22，低于提案上界28；exec转交归因为源码/日志推断，未保存API逐次启动回执，不冒称OS进程数22。

正常pool关闭、max_tasks/RSS替换及预列timeout会按冻结pool实现终止/回收worker；这些与控制器的TerminateJobObject和外层父进程树强杀分开记录。只有E_full_valid触发控制器Job强清理；外层forced_parent_cleanup=false。各控制器cleanup_errors均为空，全部active_after_cleanup=0，所有已记录句柄关闭成功。

## 完整CLI失败的事实与未证实归因

E_full_valid官方直调退出0，JSON/Trace/log均存在，完整结果已与旧truth比较通过。adapter也由subprocess.run观察到退出0，但stdout为空，stderr只有路线标记，紧接着读adapter.json抛FileNotFoundError。该错误使payload退出1；此时Job仍有3个活跃进程，控制器立即TerminateJobObject，再等待至active0。最终snapshot中adapter JSON/Trace/log仍不存在；不能用其rc0或路线标记宣称完整官方函数已进入或完成。

冻结 `_full_cli.py:14` 使用 `os.execv`。Windows进程转交与调用方等待对象的生命周期问题是值得队长核心继续只读核对的线索，与本次观察一致；**当前证据未记录最后3个活跃PID的身份，未证明精确根因**。既未改生产代码，也未为归因增开探针。此处不是数值误差结论，而是完整CLI返回/产物就绪契约失败；正式E_full_invalid不得在本窗口补跑。

## 费用：预留、返回与实际进入分开

12条record全部保留：8 native ok、1 e0_full ok、2 e0_fallback invalid、1 timeout/route未知。子账本显式E0请求3次：fresh oracle、成功官方完整CLI、失败adapter完整CLI。17授权中当前预留15=12+3，剩余E_full_invalid的2从未启动，封存；没有按未yield或未生成文件退款。

可确认完成的完整E0成功结果至少3份：fresh oracle、pool full、官方完整CLI。两条invalid带后备route及预期错误，但route/counter本身不是逐函数体进入标记；tiny timeout与被中止adapter是否进入/完成完整E0仍unknown。本次没有函数体级started插桩，不报告伪精确的完整E0实际进入总数，也不把unknown记0；保留全部潜在15。同一caller/worker/adapter exec包装链不重复收E0费用。准备步骤、native CPU以及worker初始化成本另属耗时，不因为完整E0入口未知就算免费。

## 原件、脱敏和范围

127个运行文件先冻结完整清单，再产生共享副本。其中22文件有脱敏：14个gate/ACK文件的nonce/Job随机名替换为SHA-256，8个JSON/文本文件的个人、私有、项目或Python安装绝对路径替换为标签；其余105文件按原字节保留。两份pickle仅检查字节/哈希后原样复制，未unpickle或手改结果。`* -text`防止Git改行尾；RAW_SHARED_HASHES逐项保留原始和共享hash，并对Git批量取回核对。

本机Codex的LocalAppData存在包内路径重定向，某些错误/命令原件记录包内绝对路径；所有这些个人路径在共享版统一去除，不改变私有原件。路径脱敏不抹去“adapter结果不存在”的错误文本、时序、PID、退出码或源文件相对定位。

冻结as-run源码及helper hash与批准一致；只在实验停止后新增此结果目录，旧失败、控制测试、308.184秒超窗审计均保留不改。Actions按免费策略停用且没有触发，不能记为CI通过。官方Makespan、完整求解质量/时间、真机收益与E2速度/误差总体验收均未被本次局部合成结果替代。
