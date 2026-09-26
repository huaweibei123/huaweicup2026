# Windows 完整 CLI 失败：零运行源码诊断

2026-09-24；`nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`。

**结论：已定位一个确定的可移植性缺口；它是本次现象的强解释，但尚未完成运行时唯一归因。**
`_full_cli.py`用Windows `os.execv`承担“保持被等待进程与最终退出码”的职责，这个保证不成立。
建议最小修订为Windows保留包装器并同步等待官方子CLI，明确传出子进程退出码；非Windows
保留现有exec路径。只等待文件出现不能修复这个契约。本次仅给修订范围，不改生产源码或驱动。

## 固定输入与实际已读

- 执行源码：`a96f3ff445e6e85febb9fc13e4a0f2341fe10d3f`。
- 完整证据：`15e9e3f1c9f09c09c1d0732465a2271e6b9c25fa`；含发布收据HEAD为
  `423f1320d98900256c238908bbd3da024d31cc41`。
- 已全文读执行/协调评论5805819352、5805830016、5805850291与证据README；直接读
  E_full_valid.child/controller、adapter command/stdout/stderr、payload traceback、official.log。
  源码读_full_cli、P2/P3模块入口、payload.py全文、controller的controlled/parent部分，
  冻结contest_io写文件/退出段、冻结P2主入口。未unpickle，也未重新校验全部127原件。
- 调度指定零运行：本次没有源码import、测试/探针、E0/E1/E2、worker、构建、依赖安装。
  官方资料只读；网络返回的源码只作为文本读取，没有执行。

[原报告](https://github.com/huaweibei123/huaweicup2026/blob/15e9e3f1c9f09c09c1d0732465a2271e6b9c25fa/results/a/review/e2-p2-windows-20260924/gated-cde-run-20260924/README.md)
保留六阶段已通过范围；E_full_valid失败、E_full_invalid未运行，不能提升为E2终验。
潜在15次E0保留，余额2封存；600/750秒交付目标未达，不能改写为全通过。

## 事实、代码机制与未知分别记录

| 类别 | 核对结果 |
| --- | --- |
| 直接原件 | payload记录官方直调rc=0，完整结果与truth一致；adapter也观察rc=0，随后读取adapter JSON报FileNotFoundError；adapter stdout空、stderr只有路线标记 |
| 控制器原件 | stage退出1；cleanup前ActiveProcesses=3，TerminateJobObject后0，cleanup_errors空 |
| 可确定代码 | payload.cli用subprocess.run并重定向到普通文件，等待创建的进程；_full_cli校验源码、打印路线后os.execv(sys.executable,官方脚本参数)；模块入口只调用main(2/3) |
| 强解释 | Windows exec转交启动新进程并结束旧调用进程，外层等待对象先结束；官方后继仍可能未写完，被随后stage失败清理终止 |
| 仍未知 | 失败时那3个PID身份、完整父子衔接、后继何时进入E0/写文件、最终真实退出码；不能把门禁ready时3PID列表当失败时名单，也不能认定全是官方子进程 |

证据不能区分后继尚在启动/评价/输出，或还存在参数解析、路径、解释器launcher等问题。
尤其CRT参数转交对含空格路径还有独立注意事项，私有路径已脱敏，不能推断本次是否命中。
不声明后继“只需多等几秒就一定成功”，也不把adapter rc0或路线标记当完整E0已完成。

## 为什么这个实现保证确实不足

1. [CPython v3.12.14 posixmodule.c](https://github.com/python/cpython/blob/v3.12.14/Modules/posixmodule.c#L6624)
   的os_execv_impl在HAVE_WEXECV分支调用_wexecv；本轮直接读取该固定源码文本。
2. [微软exec说明](https://learn.microsoft.com/en-us/cpp/c-runtime-library/exec-wexec-functions?view=msvc-170)
   明确底层使用CreateProcess创建新进程；
   [spawn模式说明](https://learn.microsoft.com/en-us/cpp/c-runtime-library/spawn-wspawn-functions?view=msvc-170)
   区分销毁调用进程的OVERLAY（exec同效果）与等待完成的WAIT。这不等价POSIX同PID映像替换。
3. [CPython v3.12.14 subprocess.py](https://github.com/python/cpython/blob/v3.12.14/Lib/subprocess.py#L1580)
   的Windows_wait等待self._handle并从同一handle取退出码，没有按原PID自动追踪exec后继。
   [Python 3.12 subprocess契约](https://docs.python.org/3.12/library/subprocess.html#subprocess.Popen.wait)
   承诺等待这个子进程；不承诺等待任意后代。此例stdout/stderr是文件，不能靠PIPE被后代保持
   开启而间接拖延返回来获得正确的退出码契约。
4. 冻结contest_io先写JSON、Trace、log，最后返回0；P2主入口以SystemExit传出返回值。
   因此需要等待并观察最终官方CLI的结束，包装器成功转交本身不足以说明这些同步写出已完成。

由上述源/文档可确认缺少保证；将它用于解释本次故障是有证据支持的推断，而非已记录的
完整进程时间线。本机没有检查Fang实际Python/CRT二进制实现或做Windows复现。

## 最小生产修订范围（提案，未实现）

1. `_full_cli.py`增加Windows同步代理路径：继续核对固定官方源码；保留绝对sys.executable、
   固定官方脚本和参数列表，shell=False；继承stdin/stdout/stderr、cwd和现有环境语义。
   启动后保持包装器存活，等待官方子进程，传出其退出码；不能返回“已启动成功”。
   不捕获全部错误改为0，不丢掉stderr，不加入自动重试，不改变冻结官方脚本/数值/C++/pool。
2. P2/P3入口现在是裸main(2/3)。若helper改为返回整数，两个入口必须改为显式SystemExit；
   或helper内部明确抛出SystemExit。两者择一，避免只return rc而模块正常退出0。
   保留POSIX现exec行为，不把Linux负signal码与Windows DWORD混为一谈。0/1/argparse 2及
   其他非零码必须验证；若声称完整32位Windows退出码透传，还要验证高位/符号转换，不能
   未经检查就承诺任意sys.exit转换完全保真。
3. CLI子树超时/取消与包装器正常等待是两个责任。subprocess.run或kill单进程不证明后代
   已退出；保留既有外层Job所有权、禁止breakaway，并以Job及进程句柄完成清理。
   [微软Job说明](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)给出子进程
   关联规则及例外。单改同步等待不自动提供脱离受控环境的通用树级取消保证。
   这轮先保留明确受控运行边界；独立CLI若要新增树级生命周期管理，需单独设计，不能夹带宣称完成。
4. 启动策略变更使包装器更久存活，需重新登记active进程/线程/资源上界和新源码身份。
   Windows venv launcher可能增加进程层；不能拿“新增一次subprocess”算成恰好一个OS进程。
   单请求仍至多转交一次本问题完整E0，但这只是新实现待审上界，不能沿旧hash自动验收。

同进程runpy/导入官方CLI也是可选路线，但涉及sys.path/sys.argv/__main__/模块缓存隔离、
解释器选项与全局状态；当前不优先选择，以免把小型生命周期修补扩大为新的加载语义审计。
直接换CRT spawn WAIT也仍需处理参数引用等边界；Python参数列表的同步subprocess更易维护。

## 独立验收建议（未执行，也不是新预算）

由核心在明确修订范围后交固定版本；Fang保留自己的独立驱动和新结果目录。旧失败原件、
账本、T0不回写；不能在已封存窗口继续E_full_invalid。建议先假目标后官方目标：

| 检查 | 必须观察 | 不足以通过的替代品 |
| --- | --- | --- |
| 等待完整生命周期 | 本地可审阅的假目标先写早期标志、保持存活，再写末尾/退出；包装器在真实目标结束前仍存活，外层等待最后才返回 | 第一个文件存在或sleep固定秒数 |
| 非零退出码 | 假目标延迟返回指定非零码；分别记录原始子码、包装器码、调用方码，验证一致；再验证0/1/2及声明的码域 | 只测成功0或把异常统一改1 |
| 参数/输出转交 | 含空格/Unicode的临时输入输出路径；argv逐项记录；保留普通文件stdio情形，另测PIPE使用方无死锁；不改官方输出字节 | 仅在无空格路径和capture_output下恰好通过 |
| P2完整CLI | 新批准后独立直调与adapter在独占新目录运行；子结束时JSON/Trace/log均已关闭可读、全部字节及truth匹配；invalid的退出/消息/无成功产物单列 | adapter rc0、仅Makespan或最终过一会出现文件 |
| 子树与取消 | 记录每个实际launcher/解释器/官方子进程的PID、父PID、创建时刻/句柄；正常完成无强清理，预列取消后整个Job归零且句柄退出 | 启动时PID列表替代失败时完整名单、只kill包装器 |
| 共享P3与POSIX | 同helper影响P3，不能用P2结果代签；另审其最小有效/无效路径，POSIX原分支有独立回归 | 此前P23 API测试等同CLI验收 |

异常时在清理预算允许内保存完整Job PID名单/身份与原始退出码，若采样失败记录缺口，不能
为了采集延误强制清理；进程数不固定为3。OS累计数、峰值、逻辑启动数、E0次数继续分开。
预留每次直调/adapter完整E0；启动/取消不确定仍计unknown，不按无文件退款。运行、清理、
原件整理、发布/回读的时间目标仍分项明确；本提案没有自行批准这些运行。

## 交接结论

请调度先确认生产修改写范围和独立验收分工。本专项建议核心修共享CLI转交，Fang审驱动及
实际Windows结果；不接管其进程门禁。暂不需要为已能定位的接口语义再占用Pro咨询。
本文件为固定源码/原证据/官方文档的诊断，所有运行验证仍待后续明确任务。
