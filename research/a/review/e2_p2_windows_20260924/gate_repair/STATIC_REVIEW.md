# 独立 Windows 门禁：实现后静态送审

本目录新增 helper 和四用例控制 runner；**尚未 import、执行或用探针验证新模块**。没有新控制启动、E0/E2/debug、BC DLL 加载、原生或字节码编译、安装、运行 T0。语法检查使用外部 Python 仅 `ast.parse` 文件文本；API、句柄和控制路径为源码审查，不是运行验收。机器可读清单及逐文件字节 hash 见 `STATIC_REVIEW.json`。

写范围为本目录和 `results/a/review/e2-p2-windows-20260924/gate-repair-plan.md`。旧 driver、旧 gate、账本、原件、事后勘误均不修改。当前分支 `codex/e2-windows-gate-repair-plan-yuanzhifang`；相对于固定方案 `dcdf3ea024bf25810c6906d7b88fbd1f75cd9375` 的 diff 即本次实现。

## 实现和限额

| 文件/函数 | 静态用途 |
| --- | --- |
| `gate_helper.py` / `WinAPI` | Kernel32 结构/签名、准确 Job 成员查询、完整 PID 列表、非继承句柄、唯一受控 CreateProcessW 入口 |
| `gate_helper.py` / `save` | 同目录临时文件、flush/fsync、原子替换；初始工件用 Windows `os.rename` 拒绝覆盖 |
| `control_runner.py` / `child` | 先保存真实 PID/PPID；nonce/阶段/代码/Job 校验；查询句柄关闭后 ready；父 ACK 后唯一 marker payload |
| `control_runner.py` / `one_case` | 一次预留、一个受控启动；G1 成功、G2 nonce 拒绝、G3 精确 Job B 拒绝、G4 最后句柄关闭导致退出 |
| `control_runner.py` / `parent` | 固定源码/启动器/HEAD/批准文件检查；四例顺序，首非预期错误停止；实际 OS 进程数和启动请求分列 |
| `contract.json` | 固定 4 次请求、300 秒含交付、准备 45 秒、150 秒启动截止、单例 20 秒含至少 5 秒清理；评价调用均 0 |

只有一个 `CreateProcessW` 调用点，由 `one_case` 的一个 `launch_assigned` 调用点使用；父循环固定 G1/G2/G3/G4，无重试。负例只改变既有子环境的 nonce 或 expected Job，不额外启动进程。每主 Job 的 active process limit=4；G3 的 B 单独创建且必须始终为空。启动器派生真实 Python 的进程计入 Job 统计，不能把四次请求当四个 OS 进程。`subprocess` 只调用 `list2cmdline`，不使用 Popen/run/shell/外部 git 来启动辅助程序。

`main` 中 T0 在参数/批准/源文件/环境身份准备前捕获。每次启动在入口及 CreateProcessW 前检查外层启动截止；单例前 15 秒工作，后至少 5 秒保留清理。G4 子等待可以延伸到其单例 20 秒期限，父正常判断仍必须在前 15 秒完成；失败后进入清理，不等它自行超时。同步系统 API、文件系统停顿或调度停顿不能由普通 Python 保证硬实时；若观测超过限额一律失败，不能增加新窗口或补测。控制结束仅写控制收据，原 T0 到公开交付的 300 秒由后续同窗交付另外记录；脚本不把 controls_wall 冒称全交付 wall。

## G4 消除 ACK 自退出误判

子进程先关闭精确 Job 查询句柄，ready 保存共同系统时钟 `GetTickCount64` 的 `ready_tick_ms` 和 `ack_self_exit_deadline_tick_ms=min(ready+15000, case_final_deadline)`。此后只有 ACK 或该绝对期限可以结束正常等待；G4 父程序根本不写 ACK。

父进程完成准确 Job 的完整成员快照、为每个 PID 打开非继承退出观察句柄，再复查完整 PID 集合未变、所有观察句柄尚未 signaled。关闭前要求自退出期限至少还剩 6000 ms，且前 15 秒工作段至少还剩 2000 ms。以关闭前 tick 为起点，在**同一个总共 2000 ms 的窗口**检查所有已跟踪进程退出，不是每个 PID 分别给 2 秒；要求距子自退出期限仍有至少 4000 ms。

证据包含最后关闭前/后 tick、全部退出 tick、wall、每进程退出码、实际脚本 PID、成员集合、子期限和剩余差值；不得存在 ACK、payload 或 child.final（包括 ACK timeout）的正常终止收据。退出码 24 或脚本已知正常拒绝码也拒绝。Win32 文档未给本控制应硬编码的 kill-on-close 唯一退出码，故退出码原样记录，不以 `code==0` 单独宣称自然退出，也不以 `code!=0` 单独证明强退。结论来自提前关闭与等待期限分离的完整证据。

G4 的预期结果明确为 `forced_by_last_job_handle_close`。此时 Job 控制句柄已关闭，无法再冒称读到了 active counter；记录完整已跟踪 PID 集合全部退出这一依据。若任何进程仍活着，只能为清理重开已知随机 Job 的 query/terminate 句柄，显式终止并有界等待；该路线设置 cleanup_forced 并使本例失败。最终 active=0 本身不能代替 G4 验收。

## 导入与 API 清单

helper 导入：ctypes、hashlib、json、msvcrt、os、pathlib.Path、subprocess、tempfile、time。runner 导入：argparse、datetime.datetime/timezone、hashlib、hmac、json、os、pathlib.Path、secrets、sys、time，以及同目录明确列名的 gate_helper。没有旧 driver、research/src 包、NumPy、E0、E2 或 BC 导入。父子命令均要求 `-I -S -B`，禁用 site/用户路径和字节码落盘，只加入当前 helper 目录。正常 Python/标准库依赖的 Windows 系统组件不是本任务所禁止的第三方评价 DLL。

唯一显式动态库入口为 `ct.WinDLL("kernel32", use_last_error=True)`，位于 WinAPI 构造器而非模块顶层。绑定的完整 API：

| 分类 | API |
| --- | --- |
| 时钟/当前进程 | GetTickCount64、GetCurrentProcess |
| 句柄 | CloseHandle、GetHandleInformation、DuplicateHandle |
| Job | CreateJobObjectW、OpenJobObjectW、SetInformationJobObject、QueryInformationJobObject、IsProcessInJob、AssignProcessToJobObject、TerminateJobObject |
| 进程/线程 | CreateProcessW、ResumeThread、TerminateProcess、OpenProcess、WaitForSingleObject、GetExitCodeProcess |
| 继承白名单 | InitializeProcThreadAttributeList、UpdateProcThreadAttribute、DeleteProcThreadAttributeList |

参数/返回类型均显式绑定。`IsProcessInJob` 同时检查调用成功和 BOOL，禁止 NULL 目标。PID list 动态容量 8/16/32/64，必须 assigned==listed<=capacity，容量不足重新取，不能使用截断结果。`GetCurrentProcess` 是伪句柄，不关闭、不列入继承白名单。所有实际拥有的句柄验证继承位。

## 句柄生命周期和失败路径

| 对象 | 成功路径 | 失败路径 |
| --- | --- | --- |
| 主 Job/空 B | 随机 Local 名，安全参数 NULL；非继承；新对象设置 kill-on-close + active limit；用例 finally 关闭，G4 提前关闭主 Job | ERROR_ALREADY_EXISTS 仅关闭本次新取得的引用然后拒绝，不 set/terminate 旧 Job；新对象失败清理后关闭 |
| CreateProcess 返回 process/thread | 安全参数 NULL、检查非继承；CREATE_SUSPENDED，Assign 成功再 ResumeThread，返回值必须恰好 1；立即关闭 thread；process 保留到退出观察完 | Assign 前失败则直接 TerminateProcess 尚暂停进程；Assign 后失败则 TerminateJobObject；有界等待、记录退出与清理失败；关闭两个句柄；不无 Job 重试 |
| 原始 stdin/stdout/stderr 文件 | 私有 stdout/stderr 启动前 `xb`；原始 fd 非继承；stdin 为 os.devnull；CreateProcess 后关闭父持有文件 | finally 尝试全部关闭 |
| 三个 stdio duplicate | DuplicateHandle 产生仅这三个 inheritable 真句柄；STARTUPINFOEX 的 HANDLE_LIST 白名单；CreateProcess bInheritHandles=TRUE；创建结束立刻关闭父 duplicate | finally 尝试关闭全部；任何关闭失败保留并终止当前用例 |
| Attribute list/value | 存储 buffer 和 whitelist 一直存活到 DeleteProcThreadAttributeList | 初始化完成后所有后续失败路径都 Delete；未初始化成功不假调用 Delete |
| 子查询 Job | OpenJobObjectW(QUERY,FALSE,精确名称)，finally 关闭成功后才 ready | API 失败仍 finally 关闭，关闭失败不得 ready；G3 false 成员结果包含 query_closed=true |
| 进程观察句柄 | OpenProcess(SYNCHRONIZE\|QUERY_LIMITED_INFORMATION,FALSE)，不保持 Job 存活；观察退出后统一关闭 | 打开/继承校验失败立刻关闭已取得句柄；同一用例失败清理所有已有观察句柄 |
| G4 清理重开 Job | 正常通过路线不重开 | 只在已跟踪成员仍未退出时重开自己的随机名称；terminate/query 不继承，终止/等待后 finally 关闭，本例永不回升为通过 |

所有关闭由 OwnedHandle 记成功/失败；close_all 尝试所有对象后汇总错误，不能因第一个失败跳过其余对象。系统调用/资源释放错误保留为失败；没有宣称对任意系统故障都能保证资源回收。

## 执行审批材料（当前不可执行）

`approval.example.json` 的 approved=false，不能运行。代码送审冻结后，另由协调明确批准固定 HEAD、source_identity、4 次请求和 300 秒总窗；将真实批准引用写入私有批准文件，批准不是由将 false 手改成 true 自动产生。批准文件及输出不放仓库，输出须是 LOCALAPPDATA/CodexEvidence 下全新目录。

拟议父命令如下，仅供审查，**本轮未执行，包括 --help 都未执行**：

```powershell
& .venv/Scripts/python.exe -I -S -B research/a/review/e2_p2_windows_20260924/gate_repair/control_runner.py --approval <已批准的私有JSON> --output <全新私有目录>
```

所有子命令由同一 launcher 运行 `-I -S -B .../control_runner.py --child <用例私有目录>`。只在四例均通过时控制收据 passed=true；第一非预期结果立即停止余下受控启动，已预留/已尝试/已创建分别保留，不退款、不补投。stdout/stderr、nonce 原件、ready/ACK、句柄事件及失败都先留私有原件；后续公开副本去个人路径和完整 nonce，保留原始/共享/Git hash 映射。还没有任何这类运行工件。

## 目标理解及证据边界

本人 session `yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce` 已实际全文读取固定 `6a7c678df58613445efaf89d9a5221702955fa22` 的 AGENTS.md（含核心目标节）与 docs/a/OFFICIAL_OBJECTIVES.md。实现 HEAD 在固定送审回执给出，不用文档内自引用提交号。

官方首要目标是合法方案的 Makespan（模拟 cycles），兼顾额外 DDR 字节，P3 另报字节命中率；端到端求解 wall 是从程序启动/读图到合法方案落盘及必要收尾，在线构造、评分、回退、IPC、在线 E0 等均计入。独立结束后的官方最终复评另报。原题第 5 页脚注 1 直接修饰问题 1 的高效求解，5–10 分钟是推荐，不是官方 600 秒淘汰线、最低 5 分钟或每种核数单独获 10 分钟；P2/P3 沿用是团队效率目标。

当前 300 秒/4 个受控启动是**队内单独提案预算，仍未批准执行**，与官方时限没有等同关系。即使评价器快 20 倍，若方案更差或完整求解更慢/超队内预算，仍未完成核心目标。本门禁修复只为可靠地约束并保留测试证据，不能据此声称方案质量、求解端到端性能、E2 工程加速门槛或真机收益已通过。具体影响是保持控制测试与这些验收分开，禁止把门禁通过自动扩成 C/D/E 或 Q2 开跑。

低于 10 分钟不足以完成本队同时压低 Makespan 与 wall 的追求；后续应比同等质量所需时间、同等时间达到的官方质量，并报告资源/冷启动/尾部成本。有限次数枚举不自动符合避免暴力迭代的要求，仍需解释结构、候选有效性、复杂度、停止条件与收益。本次不是求解算法比较，不新增这些实验。

本人还实际读取固定 `b59d97233c5768526b734e4c02fe33ee6cc2eb7d` 的 AGENTS.md 免费协作及队长 Pro 权限段、docs/GITHUB_FREE_COLLABORATION.md 全文。影响：继续使用本人组织主库 Git/Issues/PR，不使用队长账号/Pro 或私有镜像授权；不启用、dispatch 或重跑 Actions，不启付费 GitHub 服务。Actions 按项目免费策略停用不代表测试通过，本交付只列本地静态证据和真实未测项。没有切换实现基线，没有运行云端 CI。

文件卫生在实际 Windows 环境检查：dot_clean 不可用；只读扫描本次新目录和方案文件所在目录未发现 AppleDouble、.DS_Store 或 __MACOSX 残留，未删除任何文件。源码没有个人绝对路径、客户端 task ID 或凭据。原两份 driver 与旧 contract 的实际字节 hash 与既有记录一致；旧运行证据的 Git diff 为零。

## 官方 API 来源

- [HANDLE_LIST 和 lpValue 生命周期](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
- [CreateJobObjectW：同名对象及最后句柄](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw)
- [IsProcessInJob：具体 Job 和 API/BOOL 两层](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob)
- [OpenJobObjectW：访问权与继承](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-openjobobjectw)
- [PID list 结构](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list)
- [ResumeThread 返回计数](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread)
- [GetTickCount64 系统启动毫秒时钟](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-gettickcount64)
