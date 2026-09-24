# P2 Windows 进程适配层：候选实现，尚未实机准入

目标是在 Windows 上给 P2 producer 提供可核对的启动、计时、内存观察与清退收据。本次新增 `windows_process.py`、`windows_gate.py`、替身测试，并接入 `evaluate_feedback.py` / `evaluate_matrix.py` 的平台路由。新 runner 待 root 统一冻结，不覆盖旧固定提交；算法、协议和封存成绩不变。本次未启动 solver/E0/E1/E2 或 Windows 原生进程，不建立共享调度服务。

## 已有依据与复用范围

- 优先依据实际运行版本 [`569c65f2673d6fc2a99507f151ca04b814e1dc68` 的 gate_helper.py](https://github.com/huaweibei123/huaweicup2026/blob/569c65f2673d6fc2a99507f151ca04b814e1dc68/research/a/review/e2_p2_windows_20260924/gate_repair/gate_helper.py)，SHA-256 `e5af8da2e6cc4288d7066769bb246c68f51da8bc3c2d6da2f4acc45698c88621`。复用其固定宽度 ctypes 布局、明确 argtypes/restype、不可继承的 Job/process/thread 句柄、stdio duplicate 白名单、`CREATE_SUSPENDED → AssignProcessToJobObject → ResumeThread` 顺序及失败后持有句柄清理的设计。本适配层是经过整理的派生实现，不冒称与旧文件字节相同。
- 已读 [`213182ca5609987150483441abd691346a249291` 的控制报告](https://github.com/huaweibei123/huaweicup2026/blob/213182ca5609987150483441abd691346a249291/results/a/review/e2-p2-windows-20260924/gate-control-run-20260924/README.md)及 G1–G4 各 `result.json`。四例 `passed=true`、成功分配后 Resume 返回 1；G1–G3 最终会计 ActiveProcesses=0，G4 关闭最后 Job 句柄后三个已跟踪进程均 signaled。四项有限控制通过，完整发布耗 308.184 秒，超原 300 秒窗口；它不是完整 runner 或本适配层的 Windows 验收。
- [s55 后端能力说明](../coherent/backend-capabilities-s55-20260924/README.md)仍提供旧 PR74/203 失败与 PR75/80 静态范围。先前仅据该表判断“没有已测原语”不完整；本实现按 s55 后续提供的 G1–G4 固定原件修正来源判断，不补测旧 M/S 窗口。
- 参考 `6f91055d37bd94d4d0b9f7789ccb36baf0d44f88:research/a/review/e2_cli_fix_validation_20260924/win_support.py` 的进程内存结构，但改为读取当前 `WorkingSetSize`。`PrivateUsage`、`PeakWorkingSetSize`、Job commit 都不冒称当前 RSS。

微软 [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) 与 [QueryInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject) 是原生语义依据。查阅过 [PROC_THREAD_ATTRIBUTE_JOB_LIST](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)，最终没有引入该额外属性，沿用已有有限实测的挂起创建与分配路径。

## 接口与集成要求

```python
from src.q2_nikolastarx.windows_process import monitored

receipt = monitored(
    argv, process_folder, absolute_perf_counter_deadline, rss_limit_bytes,
    cwd=repository_root,
    env=dict(os.environ),
    cleanup_timeout=5.0,
)
```

前四个参数对应原 `common.monitored`；`cwd` 默认由文件位置推导项目根，不依赖 shell 工作目录。`argv` 必须为列表，不经 shell；可执行文件必须是绝对路径或相对 cwd 的明确文件路径，例如 Windows 的 `.venv/Scripts/python.exe`，不搜索 PATH。环境是调用时复制的完整字典；只保存身份哈希，不打印值。独占新进程目录，已有目录拒绝重复派发。标准输出和错误原始字节分别写入 `stdout.txt`、`stderr.txt`。

调用方仍负责固定源码/输入、预算预留、实际评价入口计数与发布收尾。进程模块不导入官方代码、不选择算法、不增加候选、不自动重试或写中央台。当前集成处理以下差异：

1. 判断 `status == 'runner_error'` **或** `stop_dispatch` 即停止新派发；不能仅检查 `surviving_pids` 是否为非空列表。清理未知时该字段是 `null`，不是虚构的空列表。
2. `pid` 非空意味着 CreateProcess 实际成功，即使 Assign/Resume 后来失败。`creation_reserved` 与 `creation_reservation_persisted` 分别记录预留和落盘返回，`creation_attempted` 仅从 native backend 的实际 API 尝试标志取得，不能把落盘前的预留 OR 成 API 已调用；后续另记 `created/resume_attempted/resumed/target_entry_entered`。终态收据确认未恢复线程则 E0=0；恢复后缺少入口证据与完整输出则 E0=null，不把 PID 当 E0。成功解析完整的冻结 P2 CLI 输出结构和输入身份可确认一次 E0，即使后续清理失败；该次仍作为失败行。solver 计数明确表示 OS 进程创建，另列 `os_processes_created`，未恢复 solver 的在线 E0 为 0。在途未完成收据不能据假初值断言未创建/未运行。实际计数与 `reserved_E0_upper_bound` 分开，未知保留预算占用并停止派发。
3. 尚未取得有效 RSS 样本时，两个 peak 字段是 `null`。board 导出须保留未知及原因，不能用 0 补齐，也不能直接对含 null 的峰值列表 `max()`。
4. `deadline` 是工作阶段绝对 perf_counter 截止，清理最多另留 `cleanup_timeout` 秒，实际 wall 包含准备、创建、工作、关闭输出和清理（终态收据自身序列化在测量后）。清理截止取“清理开始+grace”和“工作截止+grace”的较小者，超时 API 不得顺延总上限。sample/poll 返回后重新读钟；晚到退出保留 exit_code/退出事实，status 为 timeout。ActiveProcesses=0 仅晚到时仍可 `cleanup_verified=true`，但 `cleanup_within_budget/within_budget=false`、`deadline_status=deadline_unverified`、`stop_dispatch=true`。close 与父输出流关闭后也复核时点。外层协议必须预留清理时间；同步原生 API 本身没有独立硬中断保证，外部 watchdog 仍由执行端负责。
5. `evaluate_feedback.monitored` 在 Windows 路由至本层，POSIX 保留原监测函数。Windows CPU 读注册表，RAM 读 `GlobalMemoryStatusEx`；失败保留 null 和具体原因，不调用 sysctl 或猜测配置。matrix 优先使用协议显式 `python`，Windows 默认当前 `sys.executable`，POSIX 默认仍为 `.venv/bin/python`。新冻结清单包含适配层；JSON 明确按 UTF-8 落盘，Windows 子进程设置 `PYTHONUTF8=1`。此模块没有修改算法。
6. matrix 的 Windows 工作 deadline 从阶段墙钟和剩余批次墙钟中扣除 `process_cleanup_grace_seconds`（默认 5 秒），cleanup 仍计入实测 wall。grace 必须小于 solver 和 final 的阶段限额。未知清理在 final 评分之前即截断；后续格式预检同样不再启动。正常路径上的 Windows 格式预检是独立记录的 Job 子进程，最多工作 10 秒加同样 grace，受剩余批次时间约束；它不计 E0。POSIX 预检保持旧实现。真实派发以 PID/创建收据计数；计划、预算预留、CreateProcess 尝试都不伪装成实际评价调用。

旧固定 `evaluate_feedback` 的完整 CLI 仍是首批专用入口，不因此获得 Windows 或再次运行封存批次的许可。新集成入口为 `evaluate_matrix`；`plan` 只核对固定文件和枚举，既不创建原生 Job，也不启动 solver。

## 运行及失败语义

Job 先创建、设定并回读 `KILL_ON_JOB_CLOSE`，不启用两种 breakaway 标志。CreateProcess 挂起创建；成功后立即接管 PID/两个句柄，在 Assign 和成员关系回读成功后才首次放行。Assign 失败时，进程尚未运行，但已实际创建，必须对持有的 process handle 调用 TerminateProcess 并观察退出；不能依赖空 Job 的终止来回收它。没有无 Job fallback。

调用 TerminateProcess 前先查询同一持有句柄是否已 signaled。微软 [TerminateProcess 文档](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess)明确已退出进程再次终止可能返回 ERROR_ACCESS_DENIED(5)；只有即时复查同一句柄已 signaled 才记录为退出竞态。仍存活或无法观察时保留原错误，不能普遍忽略错误 5。GateJob.close 同样先检查，不在 monitor 已完成清退后无条件再终止一次。

s55 对 `75bb3e9` 的后续定点审查发现：首次等待观察失败时跳过 TerminateProcess，会留下尚未加入 Job 的挂起子进程。修正版保留观察错误，同时仍尝试终止该持有句柄；GateJob.close 复用这一逻辑。终止成功本身不冒充已观察到退出，收据继续 unknown/stop。新增 ctypes 替身贯穿 Create 成功、Assign 失败、Wait 失败、仍发出 TerminateProcess 的完整清理链。根会话本次四模块 **72 项通过**，无原生 Windows 或评分调用。

保证的边界是“首线程放行前已归属 Job”，不是“OS 创建前就归属”。父程序在 CreateProcess 成功与 Assign 成功之间被强制杀死的窗口，没有在本模块内建立独立外部回收者；成功 PID 也可能尚未持久化。该进程仍挂起，但可能需要外部 owner 收尾；本次不声称关闭了该窗口。父进程突然退出后的 Job 自动回收，从成功分配以后成立。当前实现不是恶意代码沙箱，也不能把经 WMI/外部服务创建的进程声称为受控后代。

每个样本查询 Job PID 列表，打开成员句柄并确认仍属于该 Job，读取当前工作集求和，再加观察进程当前工作集用于阈值判定。成员在列表读取与打开句柄之间退出的有限竞态，只有新的完整 Job 列表已排除它才允许忽略；其他观察异常停止派发。共享页可被多个进程重复计入，短峰可能漏采，故是观察阈值而非内核硬 RSS 上限。

正常返回码 0 为候选 `ok`，非零为 `failed`；deadline 为 `timeout`；RSS 超限为 `rss_limit` 并停止派发。任何原生观察/创建控制异常、句柄关闭失败或清理无法证实，最终为 `runner_error` 并停止派发。清理阶段调用 Job 终止后仍须成功读取 **ActiveProcesses=0 且直接进程 handle 已 signaled**，否则 `cleanup_verified=false`、`surviving_pids=null`。不使用 taskkill，不把终止 API 返回成功当作全部清空。失败收据保存最后一次真实会计值，不用 unknown 覆盖为 0。

## 独立 Windows 合成门禁（准备，尚未执行）

`windows_gate.py` 不导入 solver 或官方模块，只提供 `plan` 与显式 `run --execute-native`。执行时要求实际 64 位 Windows、新输出目录、完整 runner SHA；先按 Git 字节核对适配层和门禁脚本。以下是未来另行授权后由执行 owner 使用的接口，不表示当前已分派或准入：

```powershell
python -B -m src.q2_nikolastarx.windows_gate plan --runner-commit <root冻结的完整SHA>
python -B -m src.q2_nikolastarx.windows_gate run --execute-native --runner-commit <同一完整SHA> --output <独占新目录>
```

固定七项控制依次为：UTF-8 stdout/stderr 正常退出、退出码 7、包含孙进程的超时清退、当前 RSS 超阈值、内存观察失败注入、Assign 失败注入、清理会计查询失败注入。后面三项是在真实 Windows 进程上由门禁明确注入的 Python 原生调用边界故障，不能称作真实 OS 故障复现。非预期错误、句柄关闭错误或清理证据不足，立即停止，不重试、不进入后续项。

建议固定预算已写入脚本：1 worker，最多 7 个直接 CreateProcess 请求、fixture 内 2 个 Popen 请求，0 solver/E0/E1/E2，控制执行窗口 60 秒；每项工作 4 秒、适配层清理 2 秒、独立清退 witness 最多另 2 秒，均受剩余外层窗口约束。Job 另有 active process limit 16 和 commit limit 512 MiB；commit 上限不是 RSS 上限。普通当前 RSS 观察阈值 512 MiB，RSS 注入项分配并触碰 128 MiB、阈值 96 MiB。解释器重定向器可能增加 OS 进程，因此实际数量读 Job 会计，不硬写“9 个 OS 进程”。样本漏短峰限制仍存在。

门禁末项有意保留生产适配层的 `cleanup_verified=false/surviving_pids=null/stop_dispatch=true` 收据；门禁自己通过未注入的原生查询进行独立清退见证，不能把该见证反写成生产收据成功。正常通过项也须有真实 ActiveProcesses=0 和直接进程退出证据。每项保留 fixture argv/hash、原始输出、适配层收据、单项结果；汇总计实际创建请求/成功进程，生成逐文件 manifest。任何控制器异常保留失败和已有 PID，停止派发；已有输出目录不能续跑。

门禁 `wall_seconds` 包括控制执行、逐项原件落盘和清退见证，明确不包括最终 manifest 序列化；发布整体时延需由外部 owner 另测，不能重演旧 G1–G4 的整体窗口误报。同步原生调用仍缺独立硬中断，父进程强制退出的创建/Assign 窗口仍需外部 owner/watchdog。七项门禁只覆盖列明的控制面，不替代这些额外故障域、算法结果或整矩阵验收。它也不验证全部潜在权限、杀软、Python 版本和 nested Job 环境。

中央指定的首次统一源码六格由 root 在独立 macOS 工作区执行，本包不重复分配 Windows 六格或生成成员评分授权；剩余规模仍由中央另行安排。

## 本次检查与待验清单

实际命令：

```sh
.venv/bin/python -B -m unittest tests.q2_nikolastarx.test_windows_gate tests.q2_nikolastarx.test_windows_runner_integration tests.q2_nikolastarx.test_matrix_runner tests.q2_nikolastarx.test_windows_process -q
```

初版在 2026-09-25 本机 macOS 有 53 项替身检查通过，仍被 s55 对固定 `131d` 的独立复核发现三项实质缺陷：重复终止已退出的未分配进程、把创建 PID 等同 E0、API 跨截止返回成功。初版通过不代表这三项当时已验证。修正版增加实际 GateJob.close 方法链上的 ctypes 参数替身、调用计数/异常恢复/预算占用与晚到 API 假钟回归；当前 **71 项通过**，其中适配层 30 项、既有 matrix 12 项、平台集成 19 项、门禁控制器 10 项。

全部是替身/静态/内存内格式检查；测试本身未派发新子进程、Windows DLL、solver 或 E0/E1/E2。假单调钟/假 PID 收据仅为临时测试数据，不能作性能结果或导入成绩台。最初一次平台替身测试曾因 mock 意外截获 `platform.platform()` 的 macOS 查询而失败；本轮替身首次复测也暴露旧 Kernel substitute 未模拟新增的 Wait 调用，补齐实际返回值语义后通过。没有因此启动或补跑任何评价器。

检查覆盖：x64 ctypes 大小、原生参数替身上的 Job/创建/Assign/唯一 Resume 顺序与三份 stdio 白名单、成功和非零退出、超时后模拟孙进程清退、RSS 超限、Job 创建失败、CreateProcess 返回失败、成功创建后的 Assign 失败、Resume 失败、RSS/等待观察失败、Job 清理查询失败、终止返回成功但 Active 仍非零、句柄关闭失败、过期 deadline、拒绝旧目录重复派发、macOS 导入后拒绝构造原生后端。

平台集成增加：POSIX/Windows 路由隔离、显式环境副本、解释器选择、CPU/RAM/RSS 的 null 与原因、协议 cleanup 时间边界、清理未知前置截断、受控格式预检、CLI plan 的零派发及 UTF-8 JSON。门禁控制器增加：所有 child 源码仅编译、预检不建原生对象、非 Windows 拒绝、七项替身回执与 manifest 哈希、首异常停止、控制器异常保留真实创建身份的替身、无关异常不得冒作故意注入、旧目录拒绝续跑。

待中央另行固定源与小预算后，在实际 Windows 执行并核验门禁。空格/非 ASCII 工作路径、真实 argv/env、每种 OS 查询故障和外层强退责任还需明确实际覆盖，不能用本机替身或过去有限原语结果补齐。必须保留实际 API 返回/即时错误、PID/句柄、Resume 次数、当前 RSS 与最终会计/退出证据；本轮尚未做这些 Windows 实测。门禁通过也不会自动授权全量矩阵。

本层源码与测试交 root 统一冻结/整合；不写 Git index、不推送、不重启封存测试、不扩实验许可。
