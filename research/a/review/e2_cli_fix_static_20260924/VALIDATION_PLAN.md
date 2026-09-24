# 新验收提案（未批准、未启动）

本文件只规定新的最小矩阵、接缝、控制器实现要求和预算。生产固定 `a21f7ef7111933d309f3d616b9a3f2e7e861129d`；helper SHA-256 `fb33ab3d120479ff70dbea87a730a08b16b90af44996cf78746d7880351b091b`。任何实现偏离本计划、hash 变化、运行不足或失败均先停止，不现场改参重试。

当前阶段仅交提案；协调已明确本阶段不要求可启动驱动。下文的驱动开发本身也需协调另行确定独立准备阶段，不能因本文自行开始；实际执行还需对固定驱动另行批准。

## A. 固定输入与真实 helper 接缝

1. 新验收目录只保存必要 controller/bootstrap/fixture/seam/矩阵，不复制旧测试树。可引用旧 `gate_helper.py` 的固定 Git blob、SHA `e5af8da2e6cc4288d7066769bb246c68f51da8bc3c2d6da2f4acc45698c88621`，从 Git 导出单文件到独立 runtime 后逐字节核对；旧文件不改。新控制器设置自己的 Job 限额和观测 API，不能导入旧 runtime 的 cap=12/旧预算。新驱动须另交固定版本及完整来源清单。
2. 假目标接缝必须加载**原字节的真实 helper 模块**，其 `main.__code__.co_filename`、文件 hash 和函数 AST 与生产一致。正常 import 链可能导入官方模块定义；这属于已明确计划的新模块初始化，不等于 E0 评价。此刻尚未 import 任何目标。
3. 加载后仅把 helper 全局 `OFFICIAL_CODE_DIR` 指向一个全新假目标目录；保留真实 `verify_official_code` 函数及其原始定义模块/全局绑定，仍验证真正冻结目录；不 mock subprocess、不改 main、不改 `os.name`、不替换真值。假目录有约定名称 `multicore_cut_evaluate_problem_2.py` / `_3.py`，两份假目标字节 hash 均锁定。记录接缝前后白名单差异，断言只有目标目录这一项。
4. F-startfail 额外仅把 helper 使用的 `sys.executable` 指向全新目录内确认不存在的 `.exe`，不创建该文件；捕获并记录 OSError 后重新抛出，外层看到非零。不存在的 `.py` 不算 CreateProcess 启动失败。改 sys.executable 会影响共享 sys 对象，仅允许该专用进程，不在控制器全局修改。任何模块/路径校验失败都在启动前停止，不能作为本案例预期失败。
5. 实际 CLI 完全不使用接缝：direct 调用冻结脚本；adapter 调用固定 P2/P3 `-m` 入口。二者均保留冻结校验。每次各自独立 Job、独占新输出目录，完成清理后才下一项；不同时跑 direct/adapter。
6. graph/valid-plan 仅导出旧证据的两个 JSON 原字节到新输入目录，保持文件名 `E_full_valid.graph.json` / `E_full_valid.plan.json`，不导出旧执行树；invalid-plan 为 `{}`。配置使用冻结 `data/raw/a/official/data/config.txt` 原字节。P2 旧完整结果可以作额外既有真值；P3 以本轮直调为配对基准，不能声称已有独立 P3 金标准。
7. 预先锁定现有 venv launcher、其实际基础解释器/venv 配置/相关重定向器和依赖 manifest；未核完整启动链则不得启动真实阶段。共同环境设 `PYTHONDONTWRITEBYTECODE=1` 防止 helper 的子 CLI（不继承 -B 选项）向冻结目录写 pycache；该设置对 direct/adapter 一致，不更改生产代码。root/cwd/环境其余变化逐项列出，拒绝未固定 PYTHONPATH/PYTHONHOME 污染；不能以隐式环境清理改变被测契约。

## B. 最小矩阵及判据

矩阵数据见 `matrix.json`；以下是未来驱动必须实现的精确动作，并非当前启动指令。

| 次序 | 案例 | 子码/stdio | 覆盖与通过条件 |
| --- | --- | --- | --- |
| 1 | F0 | 0 / 普通文件 | 空格 Unicode 的 cwd/目标目录，argv 含空串、引号、末尾反斜线；stdin 为固定二进制文件；环境 sentinel。目标写 early 后等待具名事件；外层保留 wrapper/target 句柄，确认二者等待超时仍存活，再置事件；目标写 final 后退出，之后 wrapper 才退出。argv/cwd/env/stdin 摘要完全符合原输入 |
| 2 | F1 | 1 / PIPE | stdout/stderr 各 256 KiB 固定字节，stdin 为 4 KiB 二进制；bootstrap 同时供给和排空（communicate 或有界线程，不开额外进程），原始字节/EOF/返回码一致，不靠先 wait 后读。单流上限 1 MiB，超限失败 |
| 3 | F2 | 2 / 文件 | 假目标 argparse 明确拒绝固定参数，验证 helper/包装器/调用方普通状态 2；这是进程契约，不代替真实官方 invalid |
| 4 | F7 | 7 / 文件 | 调用真实 helper 的 problem=3，受控事件释放后目标返回 7；目标/包装器/调用方原始状态一致 |
| 5 | F255 | 255 / 文件 | 普通整数码上边界；不推广成高位 DWORD/崩溃保真 |
| 6 | F-startfail | 未创建目标 / 文件 | 已通过身份与冻结校验之后，唯一 CreateProcess 尝试遇 OSError，无目标 PID、无 final；外层非零。没有重试，没有 E0 |
| 7 | F-cancel | 受控终止 / 文件 | 假目标生成且仅生成一个持有事件的孙进程。全部 ready 后记录身份/句柄；控制器终止 wrapper（模拟中断/崩溃），记录原始状态与仍活跃成员，再 TerminateJobObject。整个 Job 归零且所有已持有句柄 signaled；本项的预定强清理是预期，不声称 helper 自己清树 |
| 8–9 | P2-valid direct / adapter | 0 / 文件 | 复用三节点图、合法方案、固定配置；等待返回时 JSON/Trace/log 已关闭可读，三文件字节逐一一致。P2 可与旧官方完整结果额外对照 |
| 10–11 | P2-invalid direct / adapter | 1 / 文件 | `{}` 方案；相同错误正文、无成功产物；所有原件保留。分别预留一次潜在 E0，不能把提前拒绝当退款 |
| 12–13 | P3-valid direct / adapter | 0 / 文件 | 相同小图/合法方案及 P3 冻结 cache 配置；完整三文件逐字节匹配直调，不拿 P2 结果代签 |
| 14–15 | P3-invalid direct / adapter | 1 / 文件 | 同 invalid 方案，错误/产物/清理与 P2 对应标准；独立两次预留 |

F0/F7 的事件释放以身份和存活观测为条件，不用“sleep 后文件恰好出现”判通过。每个假目标自身有不超过 10 秒的等待截止，控制器的阶段截止更早管理正常情况；取消案例失败时也不靠目标自行超时证明清理。首次**意外**失败立即封存后续；上述预定 1/2/7/255、启动失败、取消是各自判据而非整体提前停止条件。

产物比较：JSON/Trace/log 全字节；stdout 最后一行显式包含不同的输出路径，只允许按已记录参数精确替换该一个输出路径，不笼统删行或任意标准化。adapter stderr 比直调恰多一个固定 `[E2 ROUTE] Pn ...` 行，逐字验证并只移除这一个前缀行；其余错误文本/字节完全比较。另存原始输出，所有规范化有独立映射。输出缺失直接失败，禁止轮询等待补洞或复用旧产物。

实际命令 token 模板（未来控制器替换已锁定绝对路径；shell=False）：

```text
direct:  [PY, '-B', ROOT/data/raw/a/official/code/multicore_cut_evaluate_problem_N.py,
          GRAPH, PLAN, '--config', CONFIG, '--output', CASE/result.json,
          '--trace-output', CASE/trace.json, '--log-output', CASE/official.log]
adapter: [PY, '-B', '-m', 'research.a.e2_search.multicore_cut_evaluate_problem_N',
          GRAPH, PLAN, '--config', CONFIG, '--output', CASE/result.json,
          '--trace-output', CASE/trace.json, '--log-output', CASE/official.log]
```

## C. 数量账本（均为提案上限，不是实际观测）

Windows 全部串行、15 个新 Job、单控制器、0 pool/worker。每个 Job 有一个 bootstrap，再创建该项 direct 或 wrapper；不复用旧 pool。每次创建前持久预留，失败也不返还创建请求额度。

`matrix.json` 每行列出唯一目录、Job 内逻辑角色/创建请求/条件 OS 层数、Job 外共享控制器引用、输入/配置/配对真值和独立 E0 槽。控制器只在全局计一次；同一 launcher 链不重复列为新的逻辑请求。发布用 Git/gh 和宿主 PowerShell 单独记录进程类别，不把 43 宣称整个桌面会话所有进程的硬限。

| 类别 | 请求上限 | 解释 |
| --- | ---: | --- |
| 外层控制器 | 1 | 新窗口唯一父入口，外层 PowerShell 本身另外记录为宿主，不能算消失 |
| Job bootstrap | 15 | 每项一次 |
| bootstrap 发起案例程序 | 15 | 7 fake seam + 4 direct + 4 adapter |
| helper 发起子目标 | 11 | 7 fake（含 1 次预定创建失败）+ 4 真实 official |
| 假目标孙进程 | 1 | 仅 F-cancel |
| 合计逻辑创建请求 | **43** | 包含 1 次失败尝试；不含 Git/GitHub 等发布工具，也不等于 OS 数 |
| 实际 CLI 潜在 E0 | **8** | P2 valid direct=1/adapter=1；P2 invalid=1/1；P3 valid=1/1；P3 invalid=1/1 |
| 假目标 E0 评价 | **0** | 正常模块初始化不调用 evaluator；出现意外评价立即失败 |

每个真实 CLI 槽至多一次官方评价路径；direct 和 adapter 的同一链不再额外重复计价。已确认完成/明确 invalid/未知分别记，实际函数进入次数若无插桩就保持 unknown，不以 route/rc/产物代替。潜在预留 8 不随缺文件/启动失败/取消减少。没有新的 API oracle、正式 case、搜索、P1、native replay、额外 fallback、调试评价或重复执行。旧潜在 15 和余 2 不并入新账。

## D. Job、进程、内存与失败证据

- 控制器在案例 Job 外；bootstrap 以 CREATE_SUSPENDED 创建，赋新随机独占 Job 后仅 ResumeThread 一次。维持无 breakaway、kill-on-close、三 stdio 白名单、Job/observer 不可继承、exact Job 双重 API/BOOL 校验、完整 ready PID 集与 ACK。旧 helper 只引用固定原语，新的限额写在新控制器，不回写旧门禁。
- **拟设 active cap=14，而非沿用旧 12。** 上一轮相同 venv 的一个入口实际出现 3 个 Job OS 进程，不能把逻辑 Python 调用当一个进程。预算模型按每逻辑启动最多 3 层：普通 fake/真实 adapter 同时 bootstrap+wrapper+target=9；取消多一个孙进程链=12；留 2 个诊断余量但不主动创建它们。14 是硬停止政策，不是已证明新包装链上界。启动链多于 3、异常额外子树或达到限额都失败，不提高 cap/不重试。直接 CLI 模型为 6。
- 模型累计成功程序链 42（43 请求含 1 创建失败），按 3 层给**条件式** OS 预算 126，含控制器最多 3；各案例 Job 合计 123。宿主 PowerShell、Git/gh 发布进程另表，不能塞入 Job 峰值或以 126 当实测。每 Job 内累计上限 12，所有 Job 总计 123 的 admission 检查不等于 OS 累计硬限；新控制器必须停止任何账本违约。
- 拟设每 Job 私有提交内存硬限 2 GiB、每进程 512 MiB；控制器预算 256 MiB；启动前可用物理内存须至少 3 GiB。旧 D_rss worker 的 PeakWorkingSet 约 38 MB 仅是量级参考，不能换算成新树 private commit 的证明。12 层模型即使每个估计 128 MiB 为 1.5 GiB，加 0.5 GiB 余量形成 2 GiB 政策；这不是测出的上界。Job/process memory 设置必须回读；任何限额失败立即清理且费用 unknown，不增内存重试。
- 记录 Job 累计 TotalProcesses、每次完整 PID 枚举的 ActiveProcesses、采样最大值、配置硬上限、PeakJobMemoryUsed 与每个可观测进程 PeakWorkingSet，名称不能混用。IOCP 提示不保证完整；采样峰值只作下界，精确实际峰值无法证明则为 null，不把 14 或累计 123 当峰值。
- 成员出现即尝试 OpenProcess(SYNCHRONIZE|QUERY_LIMITED_INFORMATION)，留非继承句柄，记录 PID、创建 FILETIME、映像、父 PID/来源、QPC 观测时刻。通过工具快照/进程事件获得父 PID，记录 PID 复用风险，以创建时间和句柄绑定；不能把原门禁 ready 名单当失败时名单。单项上限 12 层模型且 cap14，枚举最多14；原始 DWORD 退出码十进制+十六进制保存，STILL_ACTIVE 259 仅在 wait 未 signaled 时视为存活。
- 意外失败/预定取消前在最多 100 ms 内取失败时完整 Job PID 列表并补开句柄/身份；失败则明确记录缺口，不延迟清理。TerminateJobObject 后保留句柄直到 signaled，Job active=0 后逐个关句柄、登记每次返回值/last-error；整个清理上限 10 秒。正常案例发生强制清理为失败；F-cancel 预定清理除外。遗漏身份/退出码不得填猜测值，必需观测缺失记 incomplete，交协调判断而非自动通过。
- Job 所有权只在控制器；控制器崩溃由 kill-on-close 兜底，外层具名 Job 清理权限和控制器 watchdog 要在新驱动中落实，不能仅依赖 kill 单个父 PID。无真实评价取消案例，树清理用假目标一次覆盖。

## E. 新窗口时间、发布和失败边界

原 16.99 秒运行、881.48 秒发布回读说明证据网络/复核是独立成本；不以短运行估计整个交付。提议整个新窗口 **1800 秒**，只有具体驱动固定且协调批准后生效：

| 相对新外层 T0 | 预算/动作 |
| --- | --- |
| 0–90 s | 一次准备、固定 hash/环境/剩余内存、approval 与账本；不得建依赖或编译。超时不启动案例 |
| 至 660 s | 15 项各最多 35 s 工作 + 3 s 正常收尾，串行最坏 570 s；所有目标工作不得超过全局660 s |
| 至 670 s | 意外失败或总截止保留最多10 s强制清理；下一项只在完整35+3+全局清理余量充足时准入；不足则stop，不缩预算试跑 |
| 至 1200 s | raw/shared 脱敏、全清单、一次批量 Git 字节校验、固定证据 push、Issue/PR 第一轮发布目标 |
| 至 1500 s | 收据 commit/push、PR HEAD 和 Issue 作者/正文实际回读目标 |
| 1500–1800 s | 网络与最后核对余量；不用于追加测试，最多一次收据提交，不无限递归固化回读 |

90/660/670/1200/1500/1800 **均是同一外层单调 T0 起算的累计截止/目标**；35/3/10 是相应阶段耗时上限，不在每例重置全局时钟。清理失败时停止所有后续例，结果标记 cleanup_incomplete，保留尚未退出成员身份和原始 API 错误；不把清理失败升级为继续执行权限。发布回读另记实际时刻，不用本机 commit 时间充当远端 HEAD/评论已回读。

最外层先记 UTC 原文（保留小数精度）和 QPC/frequency，之后才读取 approval/准备/git/启动父入口；所有清理/哈希/发布/回读都沿同一单调时钟。任何目标均首意外失败停止、不可重试、不可变更参数、新建 case 数最多15。600/750 旧目标不沿用，新目标失守和最终硬限失守分别记录。硬截止到达仅允许必要安全清理，发布未完成需如实标记并停止范围扩展，不重置 T0。

为避免上次遗漏日志，新目录预置仅本范围的 `.gitattributes`/显式 tracked manifest；Git ignore 检查逐项比对，指定 `.log` 用路径级 force-add；先 staged-tree 或 cat-file 批量验证全部 bytes，再发布固定证据 SHA。原始路径/nonce/Job 名在私人目录；共享替换规则和 raw/shared/Git 哈希映射同时交付。Windows 无 dot_clean 则记录不可用并做限定目录只读 `._*`、`.DS_Store`、`__MACOSX` 扫描，不模拟 macOS 清理成功。

## F. POSIX 独立窗口与启动前待办

本机尚无已验证的 Linux/macOS/WSL 平台；不启动安装/探测或使用队长身份。POSIX 状态 **not-run/platform-unverified**，负责人待协调指定，额度不包含在 Windows8次E0中。由有本人授权的真实 POSIX 执行者另行确认平台，锁相同 helper，提出单独预算：假目标 PID 的 exec 身份、0/7/255/启动失败及 signal 路径、普通文件/PIPE 参数继承，P2/P3 valid-invalid 各 direct/adapter 的 8 个独立潜在 E0。POSIX 子树取消工具和信号语义另审，不搬用 Windows Job 结论。

当前可执行步骤的设计已经明确，但 controller/fixture/seam 尚未实现，**运行审批前的必要交付**为：新代码固定 SHA + 清单/环境与解释器链身份 + AST/文本审阅结果 + 矩阵实际命令 token/预算一致性检查。由协调审定这些具体产物后批准一次新窗口；此文和机器可读矩阵均不能自动授权启动。
