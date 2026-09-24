# Windows 启动门禁修复（独立实现已送静态审查、未运行）

本方案回应固定 `bf9be734426262839eba744e4172f2b0972e5047` 的零评价预检失败。原失败交付与事后纯文档审计固定于 `2d202e77f9d4c039973771c57dd5c9221572ad6e`，不修改原运行驱动、门禁、T0、账本或证据。本文件不批准新进程启动、E0/E2、BC DLL 加载、编译或安装。

原方案固定于 `dcdf3ea024bf25810c6906d7b88fbd1f75cd9375`。经协调明确批准仅实现后，新代码位于 [gate_repair](../../../../research/a/review/e2_p2_windows_20260924/gate_repair/STATIC_REVIEW.md)，包括独立 helper、control runner、契约和静态检查清单。尚未 import/执行新模块或任何控制回归，不能据此声称防护已验证。具体代码冻结后须再单独批准控制执行；控制通过也不自动启动 C/D/E。

## 任务卡六字段

1. **目标**：用真实执行子进程属于指定 Windows Job 的证明取代启动器 PID 与脚本 PID 相等的错误假设，并保留随机门禁绑定与双向放行。
2. **输入**：旧失败驱动/原件、现有相同 Windows venv Python、固定命令路径；Win32 官方接口文档。无图/plan/config、无评价器输入。
3. **产物**：本握手/句柄生命周期方案、新目录中的独立实现及静态检查说明、四个纯控制用例与明确计数/时间、退出与证据规则。当前仅实现和静态检查，执行另审。
4. **限制**：当前新增控制进程/E0/E2/DLL/编译均 0。拟议控制回归仅 Python 标准库和 Kernel32 系统 API；不 import 项目包/NumPy，不加载 BC、E0/E2 或任何第三方 DLL，不运行全套旧测试。
5. **验收**：目标 Job 精确匹配、真实 PID 证据、nonce 对齐、父进程再次核对后才放行；正例可达纯控制标记，反例不可达，所有子进程清理、所有查询句柄关闭。没有评价器正确性结论。
6. **拟截止**：单独控制窗口 300 秒，包括准备、4 个控制用例、清理、证据/提交/公开回读；准备 45 秒、每用例最多 20 秒、T0+150 秒后禁止新启动，余下到 300 秒仅交付。未创建该 T0。

## 已知事实与归因边界

旧运行的 Popen.pid=37868，子脚本断言自己的 PID 不等而失败；Job 观察到两个进程，结束均退出。venv Python 与同版随附 Windows 启动器字节相同。支持“启动器/真正解释器存在不同 PID”的归因，未保存实际脚本 PID/祖先快照，因此新方案必须在验证之前保存这些观测。

不删除校验、不接受任意 PID、不将 `IsProcessInJob(process, NULL)` 当指定 Job 证明。微软文档明确：NULL 查询的是“任意 Job”；传入具体 Job 句柄才查询指定对象，需检查 API 调用成功和布尔结果两层。来源：[IsProcessInJob](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob)。

## 双向握手

每个用例独立生成 `nonce=secrets.token_hex(32)` 和随机 Local 命名 Job（例如 `Local\CodexE2Gate-<随机标识>`），二者仅用于本次短窗口。父进程 `CreateJobObjectW` 后拒绝 `ERROR_ALREADY_EXISTS`，不接管旧对象；设置 kill-on-close，句柄不可继承，不设置 breakaway。CREATE_SUSPENDED让初始线程在ResumeThread前不运行，依据[进程创建标志](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)；ResumeThread返回1才表示此次恢复已完成，依据[ResumeThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread)。对象名和重用返回值依据 [CreateJobObjectW](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw)。

1. 父进程在新私有目录记录窗口/用例身份，拟用CreateProcessW的CREATE_SUSPENDED（加CREATE_NO_WINDOW）创建启动器，并保留hProcess/hThread；先AssignProcessToJobObject成功再ResumeThread，只接受返回1，其他返回值按失败清理而不循环恢复，随后立即关闭主线程句柄。这样避免先运行的venv启动器在Assign之前派生未纳入Job的解释器。Assign失败时主线程尚未恢复，终止这个受控进程并关闭句柄，不尝试无Job启动。expected Job名、nonce、stage、批准代码hash经子进程环境传入；标准输出/错误从启动前已打开的私有文件捕获，只允许必要stdio句柄继承。返回的启动器PID只作观测字段，不作脚本身份等式。
2. 父进程将 launcher 归入自己创建的 Job，只有 Assign 成功且ResumeThread成功才原子发布 gate。gate 包含完整 stage/代码 hash/Job 名/nonce 和 launcher PID；同目录临时写、flush/fsync、原子发布，禁止覆盖旧初始门禁。
3. 子脚本在 import 任何项目模块之前等待 gate，最多 5 秒。先把实际 `os.getpid()`、`os.getppid()`、launcher PID、阶段和失败位置写入私有原子记录；不要求 parent PID 固定，因为启动器可能有额外层。
4. 子脚本用 `hmac.compare_digest` 核 nonce，严格核 stage、批准代码 hash 和 expected Job 名。任一缺失/不符拒绝，不从 gate 自行选择新的期望 Job 或放宽至任意 Job。
5. 子脚本以 `OpenJobObjectW(JOB_OBJECT_QUERY, FALSE, expected_name)` 打开**准确命名对象**，调用 `IsProcessInJob(GetCurrentProcess(), handle, &result)`；调用失败或 result=false 均拒绝。用 finally 立即 CloseHandle 查询句柄，成功关闭后才写 ready、等待父 ACK。Open 的访问权限与不继承参数依据 [OpenJobObjectW](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-openjobobjectw)。
6. ready 记录真实 PID/PPID、nonce hash、目标 Job 名的 hash、精确成员查询结果、查询句柄已关闭、失败码等。完整 nonce 只保留在本次私有 gate/环境，公开证据只给 hash；nonce 是防旧文件/误路由绑定，不宣称隔离同用户的恶意进程。
7. 父进程持有原创建 Job 的句柄，用 `QueryInformationJobObject(JobObjectBasicProcessIdList)` 取完整 PID 集合，核 ready 中真实 PID 属于该对象，保存集合及 launcher/真实 PID。容量不足必须重新取完整结果或在固定上限内拒绝，不能拿截断列表或“任何 Job”替代。来源：[QueryInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)、[进程 ID 列表结构](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list)。
8. 成员证明和 nonce/阶段/代码身份都成立后，G1 父进程原子发布 ACK，绑定本次真实 PID 和 nonce；普通子脚本最多再等 5 秒并复核后才进入 payload。G4 特设 15 秒、受单例总期限约束的等待，父进程不发 ACK，以便区分 Job 强退和 ACK 自超时。纯控制 payload 仅写 `control_payload_reached=true` 后退出；不加载 E2/DLL。未来是否把握手用于 C/D/E，须另行代码与预算批准。

仅用私有目录/随机 token 不能代替成员证明；仅成员证明也不能代替本次 gate/ready/ACK 的身份绑定。所有等待均受同一用例/外层截止，不能在握手失败后生成新 nonce 自动重试。

## 查询句柄必须及时关闭

父进程是唯一长期持有 Job 控制句柄的一方。子脚本的查询句柄不可继承，存在期仅覆盖一次成员查询，在 finally 中关闭，**不跨 ready/ACK 等待、不跨 payload、不传给后代**。CloseHandle 失败也不得放行。

这是 kill-on-close 正确性的必要条件：该限制在**最后一个 Job 句柄**关闭时才触发，子脚本若留着查询句柄会改变语义。来源：[CreateJobObjectW 的句柄生命周期](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw)。

父进程异常路径仍优先显式 TerminateJobObject，等待被跟踪进程退出并核 active=0，再关闭 Job 控制句柄；kill-on-close 是最后一道保护。用于观察退出的独立**进程句柄**不等于 Job 句柄，finally 也须逐个关闭。实际 handle 检查失败、活跃数不能归零或强制回收均按真实失败保存，不能标成自然退出。

## 新实现与旧文件边界

| 旧驱动位置 | 拟在新实现中替换/增加 | 旧文件处理 |
| --- | --- | --- |
| child 的 `gate.pid == os.getpid()` | 保存二者，再做 nonce + 指定 Job 成员证明 | 不改旧行，不重跑旧驱动 |
| 匿名 CreateJobObjectW | 每阶段随机命名、不继承；拒绝已存在 | 新文件实现 |
| 父进程写一个 gate 即等待退出 | gate → 子成员证明/ready → 父 PID 集合复核 → ACK | 新文件实现 |
| 只留下 launcher PID | 明确记录 launcher/实际脚本 PID/PPID/Job PID 集合 | 新私有工件 |
| 子进程查询 Job 句柄 | finally 立即关闭，ready 后不持有 | 必须静态审阅与控制回归 |

新实现保留原子 JSON 写、调用前预算、外层 Job、首失败停止机制。表中的实现均在新 gate_repair 目录；没有向原驱动应用 patch。

## 独立纯控制最小矩阵

建议固定四个顺序用例，每个恰好一次受控 CreateProcessW 启动请求，共 **4 次**；沿用真实 `.venv/Scripts/python.exe`，不通过换成另一个解释器绕过启动器情形。启动器可能派生解释器，实际 Windows 进程数单独观测，不能把 4 个启动请求报成 4 个实际进程。

| 用例 | 场景 | 必须得到的结果 | E0/E2/BC DLL |
| --- | --- | --- | ---: |
| G1 正例 | 正确 Job + nonce + ACK | 实际 PID 在指定 Job 集合内；记录 launcher/脚本 PID，不要求相同；payload 标记出现、正常退出 | 0 |
| G2 nonce 反例 | 子环境的期望 nonce 与 gate 不同，进程仍受父 Job 控制 | 明确 nonce_mismatch，payload 标记不存在；不得改用 gate 的 nonce；清理为0 | 0 |
| G3 Job 反例 | 子树实际放在 Job A，却告知同进程创建的空 Job B 为 expected target；nonce 正确 | 精确 Job B 查询返回 false，payload 不可达；证明“在某个 Job”不够；A/B 均关闭 | 0 |
| G4 句柄生命周期 | 正确成员验证并 ready 后，父进程故意不发 ACK，关闭自己的最后一个 Job 句柄 | 用独立进程句柄观测 launcher/真实脚本均退出；payload 不可达，证明子查询句柄没有跨等待遗留 | 0 |

G4 在关闭 Job 前保存完整成员列表并为实际进程打开退出观察句柄，不保留额外 Job 查询句柄。子 ready 保存同一 GetTickCount64 系统时钟的自退出绝对期限（ready+15秒与单例20秒总期限取较早者）。父关闭前须核距子期限至少6秒，并仅在从关闭前开始的总计2秒窗口观察全部已跟踪进程退出，结束仍须距子期限至少4秒；保存逐进程 exit code、wall、期限/实际PID及关闭前后证据，禁止 ACK/正常 child.final/payload，不把最终 active=0 单独当强退证据。失败时仅为有界清理重开该同一 Job 的 terminate/query 权限并显式终止，再关闭句柄；该清理路线使本例失败，不能借此重测。

每用例主 Job 最多允许 4 个同时活跃进程；G3 另一个 Job 为空，不启动额外进程。私有证据的正式进程数以 Job/PID 回执为准。不会为了制造 mismatch 再启动一个无归属进程，所有子树始终有控制 Job。G2/G3 的拒绝是预列结果；任何与预期不同的错误、意外 payload、句柄/清理失败都是首个非预期失败，立即停后续用例，不再发起剩余受控启动。

各用例包含启动/门禁/清理最多20秒，父工作段15秒、预留至少5秒清理；gate和普通ACK各最多5秒，G4子ACK等待特设15秒并受单例总期限约束。全窗口300秒，前45秒完成身份准备，150秒后不启动任何新控制进程；所有计时从新批准后、第一次环境/身份准备之前开始。源码/CLI、命令行和参数见新目录静态审查说明，当前不建立窗口或启动用例。

“无 DLL”在本控制任务中特指不加载 BC/评价器/第三方 DLL；门禁机制需引用 Windows 的 Kernel32 系统 API。控制实现只能依赖标准库和这些系统 API，不能导入旧 P2 驱动、research/src 模块或把评价器载入当作预检。实现静态审查须列出 import 与每个 ctypes 动态库入口。

## 后续审批所需具体材料

提交独立控制实现和新门禁 helper 的固定 diff、完整 import/API 清单、唯一 CreateProcessW 调用点（固定四例最多各一次）的审查、handle关闭路径、批准文件示例和未启动命令。stdio采用 STARTUPINFOEX 的 HANDLE_LIST，仅继承三个明确duplicate；Job/process/thread/query均检查不可继承。协调对具体代码和300秒/4次启动预算明确批准后，才执行控制回归；此次代码提交不代表该批准。

控制结果需要保存每个阶段的原始 stdout/stderr、launcher/脚本 PID 与成员集合、nonce hash和失败点、原子 gate/ready/ACK 工件、handle关闭及退出回执、原始/共享/Git hash、全过程 wall。私有完整随机标识不当作公共授权凭据，也不扩大工具权限。

G1–G4 即使全部通过，只证明控制机制的有限观察。C-full/D/E 的下一次合成评价须在其后另固定版本/新窗口并批准原定调用数；不沿用旧17槽或旧600秒窗口，不自行写 Atlas/done，不据控制回归放行 Q2。
