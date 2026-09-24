# P2 Windows C/D/E：接入已固定门禁的零运行送审

当前仅允许实现与 AST/源码/字节静态检查；新 Python/PowerShell 文件均未 import/执行，包括 --help。没有加载 DLL、探针、E0/E1/E2/debug、编译、安装或新 T0。本目录不授权执行；固定代码和新契约须再由协调明确批准。旧 continuation、原运行工件、生产 backend/pool 一律不改。

## 六字段任务卡

1. **目标**：补验此前未完成的 C_full、D_order/D_timeout/D_rss、E_search/E_full_valid/E_full_invalid；使用准确 Job 成员与 nonce/ready/ACK 门禁，绕开已证实错误的启动器 PID 等式。
2. **输入**：生产代码 `997813c7c83d4d18a0a8e2a19b5be37b90223e01` 对应既有字节；原 P2 固定输入、R plan、配置及基线原件；原 typed/canonical 对照设计 `bf9be734426262839eba744e4172f2b0972e5047`。原始输入/34项源代码与依赖身份继续由 `contract.json` 和旧 IDENTITY 严格核对。
3. **产物**：新外层 PowerShell 包装器、gated runner、共享 runtime、从旧驱动按函数复制的 payload、固定契约与静态清单；以后如获执行批准，独立私有目录保存完整 gate/ready/ACK、进程/句柄/外层时间、逐调用账本、pickle/typed/canonical/CLI原件和脱敏映射。
4. **限制**：本轮零运行。拟议运行一次，最多12 record + 5显式E0 = 17潜在E0；debug/正式图/P3/Q2为0，不构建、不改生产后端、无自动重试。原始失败的未用额度封存，不能挪作本次授权。
5. **验收**：每阶段精确门禁、零残留、原有完整结果类型/数值、排序/回收/超时恢复/RSS、CLI退出/产物判据全部保留；首非预期错误停止后续。功能/清理/时间/发布完整性分别判定，控制成功不代替 E2 总体验收。
6. **拟截止**：新的900秒外层全过程，90秒准备，评价与各阶段清理在T0+300秒截止；T0+600前完成证据/Issue发布，T0+750前完成最终收据提交及固定HEAD回读，最后150秒只留交付缓冲。总计900秒含初始准备、父解释器启动/导入、执行、清理、脱敏、Git发布与最终回读。当前不创建这些时钟。

## 固定门禁来源与集成差别

只引用已有 `../gate_repair/gate_helper.py`；实际 SHA-256 为 `e5af8da2e6cc4288d7066769bb246c68f51da8bc3c2d6da2f4acc45698c88621`，运行前再次按字节核对。helper 的实际控制 as-run 是 `569c65f2673d6fc2a99507f151ca04b814e1dc68`；四项控制证据 `556b2104176a4f37a76d5dab85fe8a4406c0ee3f`，事后超窗审计 `213182ca5609987150483441abd691346a249291`。不 import 原 control_runner，不重跑 G1–G4；同一 helper 的 G4 只证明当时一次控制行为。

**新集成需要另审的差别**：控制 Job 的 active limit=4，本提案在新创建的同一 Job 上、创建子进程前显式重新设置 kill-on-close + active limit=12；不启 breakaway、不改变 frozen helper。原因是阶段启动器链之外还有最多2个worker或嵌套CLI/worker，4的上限不足。限制12是拟议资源边界，不是已验证运行结果；控制测试观察到每例3进程不能推导所有生产启动都恰好3进程。实际OS进程数用Job accounting记录，启动请求与OS进程数分开。

仍使用原 `.venv/Scripts/python.exe`（SHA `81bac8328c3df7c80a0915ea0baf01996355ebcc00ab6f8dbfefb4e60935e2bc`），不换解释器来回避启动器层。父/阶段入口 `-I -B`，需既有 venv site-packages 的 NumPy 2.5.3，因此与纯控制 `-I -S -B` 相比明确恢复 site；仅在路径固定后加入本目录、固定helper目录和项目ROOT。CLI保留原官方/adapter命令语义，添加 `-B`，工作目录固定ROOT，不改官方源码。所有spawn子进程继承stage Job；查询句柄在ready前关闭，父完整PID集核验后ACK。外层若parent超过310秒（300控制截止+10秒保险清理）或发生异常，只清理这一次父进程树，标为失败，不重试；900秒剩余部分仅交付。

`payload.py` 内 typed、canonical、preserve_object、frozen_inputs 函数从旧驱动逐函数复制；run_stage 的评估/比较主体保持原样，只删除旧PID门禁前缀并由新握手后调用、CLI加-B。typed依然区分int/str键、list/tuple、bool/int、float.hex，完整Python结果先留pickle（只写不反序列化）、typed和canonical原件，再比较；JSON归一化契约另列，不能拿JSON重建对象代替原类型比较。

既有 BC DLL `c01a4e0f6c1868945392067ef70825b7ed6e8090c3240af91d18242199f706d9`、libc++ `9779d03d9bdb4bed763a5b18d0aa5b9002ce5dad6d0adc2d496e783a3f336e3f`、libunwind `5de310284e361c8d10a92e0a18f8b17d2d5a0de1d091d9e3c0b92d86f9f6c7c2` 只拟复用，缺失/变化即停止，不安装/编译替代。静态查看 `_native_b.get_lib` 仅加载固定路径、检查ABI，没有自动build路线。preflight以后如获准才检查 ABI=1；它不发起评分。

## 调用及启动上界

| 阶段 | record | 显式E0 | 潜在E0保留 | 阶段启动 | 嵌套CLI | 常规预期worker / 保守上界 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| preflight | 0 | 0 | 0 | 1 | 0 | 0 / 0 |
| C_full | 1 | 1 | 2 | 1 | 0 | 1 / 1 |
| D_order | 4 | 0 | 4 | 1 | 0 | 4 / 4 |
| D_timeout | 2 | 0 | 2 | 1 | 0 | 2 / 2 |
| D_rss | 2 | 0 | 2 | 1 | 0 | 2 / 2 |
| E_search | 3 | 0 | 3 | 1 | 1 | 1 / 3 |
| E_full_valid | 0 | 2 | 2 | 1 | 2 | 0 / 0 |
| E_full_invalid | 0 | 2 | 2 | 1 | 2 | 0 / 0 |
| 合计 | 12 | 5 | 17 | 8 | 5 | 10 / 12 |

**额外计入两个 adapter execv 请求**：E_full_valid/invalid 各一个adapter在 `_full_cli.py:14` 把执行交给官方Python命令；同一E0调用链不能重复收费，但Windows进程/程序启动统计必须另列这两个execv请求，不把POSIX就地替换假设套到Windows。加一次父Python，Python层程序启动/exec请求保守总上界28=1+8+5+2+12（正常路线预计26=1+8+5+2+10）。28不是OS进程总数；venv可能多层启动。静态依据为冻结pool `_start`每候选最多创建一个worker，无同候选自动重试；其崩溃/超时替换只服务下一候选，所以12个record提供12个worker创建的保守上界。E_search CLI的3行可能在后续行替换失败worker，因此上界3而非只报正常1。准备另有最多4次Git身份/clean查询，不属于评分或Python启动，但计入外层wall；Git不在评价阶段偷偷执行。

瞬时层级分别为：D_order的stage+两个worker；E_search的stage+search CLI+一个worker；完整adapter路线的stage+adapter CLI+官方exec目标。其余阶段层级更少，八stage严格顺序。控制测试观察每个stage启动有3个OS进程，但未识别第三个进程角色，不能称其必为Python重定向链；只把“每个程序请求可能占3个OS进程”用于容量估算，上述三条并行路径估算峰值9，拟议硬上限12留3个余量。此估算不是最大12必然足够的证明：worker与execv/控制台辅助进程的实际数量仍未知，若触碰Job限制，记录startup/派发失败并停止，不动态提高上限或补投。

已只读本机固定Python 3.12.14的 `Lib/multiprocessing/popen_spawn_win32.py`：venv分支在每worker的一个CreateProcess调用前可改用 `sys._base_executable` 并设置 `__PYVENV_LAUNCHER__`。这是标准库实现选择，本驱动没有擅自更换stage launcher；其源码hash纳入contract并在以后获准运行时核对。该分支条件实际是否成立及OS副进程数没有新探测，因此未将worker强行按3倍或1倍报成已实测数。一次控制max4通过不能证明本次max12和worker/execv层级已通过。

每stage启动前整体预留record/显式/潜在E0，子进程每次调用前再写事件reserved。超时、未知route、started/结果不明均不退费；若preflight失败，只有其0调用stage被预留；若后续门禁失败，其整阶段潜在预算仍保留。每record都按可能回退一次E0计；C_full的full路线已有1次E0包含在它的record预留里，另一个fresh oracle为显式1。显式5含fresh oracle1与完整CLI4，不能重复相加成18或漏掉CLI。无新增随机样本或补测路线。

已实际阅读 LYX 固定 `09eef20b2285fadb88b2a6e2cad9b4bd9c389d88` 的 ROUTE_COST_MATRIX.md 与 route-costs.json，以及[原交付](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805508214)（实际作者lyx0217/323482921）；核对本机对应pool和完整CLI源码。该审计输入603b074的P2/P3单候选、无外部重试条件下完整E0≤1，支持本提案每record预留1；它没有证明本driver总量，因此这里另逐阶段累计12+5。caller、worker、exec包装链不能重复收E0费用，额外fresh oracle/完整CLI另算。route/counter可能先于参数绑定完成，不能充当函数体已进入证据；派发后timeout/取消/响应丢失的actual保留unknown，静态max仍为1。

pool先处理完一个chunk再按序yield；因此已消费/已保存行数不是实际执行数。`batch`在调用evaluate_batch之前预留整份plans长度，D_order一次预留4而非按已读行扣费，E_search在启动CLI之前预留全部3行；中途停止仍保留整批可能费用。startup失败能证明当前chunk未派发时可另记“该chunk完整评价0”的证据，但本轮总预留不退款，也不能抹掉此前chunk；没有给接口虚构started协议。CLI内部wall排除启动/import，仍以本包装器外层T0为准。

资源配置保留最多2个pool worker、每worker缓存16MiB。Job的active limit不是硬内存上限；RSS用例仍以1字节阈值验证回收标记，并保存实际峰值，不声称物理内存被限制为该数。所有子树在Job内，一例失败后禁止开始后续例；父进程清理与潜在fallback都计外层时间。

## 时间与交付策略

前次控制实际执行3.233秒，但证据与Issue/PR阶段回读279.935秒，最后收据提交回读308.184秒，已如实判交付超300秒。本提案保留原评价截止300秒，扩大的是明确提案中的交付时间至900秒，不是追认旧窗口或增加调用。

`launch_once.ps1`在真实批准文件准备、Git/环境身份、唯一父runner前同时保存原始UTC字符串、Stopwatch ticks/frequency、Tick64；父与子统一复制此T0，父无自建新窗口。包装器保留parent stdout/stderr与退出码，ledger产生前失败也保存outer记录。不用PowerShell自动日期反序列化来算秒；最终发布计时使用原Stopwatch。各stage绝对work/final截止由同一系统Tick64约束，调用前检查同时考虑UTC/Tick64及阶段截止，留10秒清理。preflight/C_full各30秒，其余每stage至多120秒且共同受T0+300硬截止；stage工作结束必须早于所留清理段。

运行后先将当前所有原件打一个冻结清单，再按实际字节批量核对Git（避免为每个文件单独起Git子进程导致交付浪费）。完整nonce/Job名/个人路径在共享副本处理，保留raw/shared/Git映射和空stdout/stderr；严禁为完成预算省略证据。先固定证据commit、发布一条原Issue消息，再读回完整作者/正文和PR HEAD；发布收据最多一次提交，最终HEAD回读留私有原件并向协调报告，避免“为保存最后一次回读再不断提交”的循环。任何超窗都单列实际时间与事后文档勘误，不能重置T0。

T0+600是证据发布目标，+750是最终收据回读目标，+900才是全过程上限；750后禁止继续做新实现或追加分析，只完成剩余交付/如实报告。网络延迟不可保证，若最终未在900内完成，就记录交付失败；不降低调用/准确性标准换取表面通过。

## 未执行命令及审批字段

下面只列拟议入口，**当前未执行**：

```powershell
& research/a/review/e2_p2_windows_20260924/continuation_gated/launch_once.ps1 -ApprovalReference <新批准评论URL> -AuthorizedCommit <审核通过的完整HEAD> -ExpectedBundleHash <静态清单bundle SHA-256> -EvidenceName <全新私有目录名>
```

新批准必须明确本目录完整bundle hash、生产/输入/DLL/标准库身份、28次Python程序启动/exec请求上界与Job=12、12/5/17调用、900/90/300/600/750时间口径。`approval.example.json` 当前false，修改文件不自动产生授权。批准前仅做AST、文本与hash复核，包括对PowerShell使用Parser.ParseFile；不import新driver/helper、不测ABI、不调用任何生产评价入口。

官方Makespan是模拟cycles，求解wall与本测试窗口又是不同量。官方第5页Q1脚注的5–10分钟推荐不是这次900秒控制交付预算的来源；更快评分不证明方案更好或全流程更快。仍需最终官方E0质量与端到端质量—时间/资源对照，本任务不扩为Q2、P3、共享并发设施或真机。GitHub只用既有免费Git/Issues/PR，Actions保持停用，不拿缺失CI当通过。
