# Windows full CLI：最小修补交接（尚未运行验证）

2026-09-24；开发 session `nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`。
本阶段仅静态补丁，不能据此将 Windows CLI、E2 或独立测试标记通过。

## 1. 目标与分工

依[原 Issue15 修订任务](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5806158559)，
修正 Windows 包装器不能可靠等待最终官方 CLI、传出其退出码的接口缺口。
核心只写共享 helper；Fang 保持 Windows 驱动、Job、门禁和结果的独立所有权。
LYX 原独立测试保留，公共状态由调度汇总。本次不再询问 Pro。

## 2. 固定输入

- 实现基线：`603b0741e21c449d3db652ebd67c94f2dc014cc9`，PR46。
- 原诊断：`abdfd31f358a035e5ecca3b0482a9d0881060ffe` 的
  [WINDOWS_FULL_CLI_REVIEW.md](https://github.com/huaweibei123/huaweicup2026/blob/abdfd31f358a035e5ecca3b0482a9d0881060ffe/docs/a/e2/WINDOWS_FULL_CLI_REVIEW.md)。
- 失败 as-run：`a96f3ff445e6e85febb9fc13e4a0f2341fe10d3f`；原件 `15e9e3f1c9f09c09c1d0732465a2271e6b9c25fa`；
  发布收据 `423f1320d98900256c238908bbd3da024d31cc41`。
- 本轮实际静态核对：603b 与 as-run 的 `_full_cli.py` Git blob 均为
  `405a93c6809a7a0c0bfd6b2ddc14a459929a4419`；不是仅沿用转述。

诊断指出确定的接口缺口和有证据支持的事故解释；没有失败时完整 PID 身份与子进程退出时间线，
不将补丁写出升级为事故唯一根因或 Windows 实机复现证明。

## 3. 输出与返回路径

分支 `codex/e2-windows-cli-20260924` 从固定 603b 创建，保留旧 PR46 和测试对象。
新 Draft PR 的 base 为 `codex/e2-p23-20260924`。修改仅本说明和 `_full_cli.py`。
补后 helper SHA-256：`fb33ab3d120479ff70dbea87a730a08b16b90af44996cf78746d7880351b091b`；
Git blob：`89c0e061f17d0a6e8a1b35a6db1eeb066314af49`。

Windows 分支使用同步 `subprocess.run(argv, shell=False, check=False)`，接着
`raise SystemExit(completed.returncode)`。保留 sys.executable、官方脚本路径及全部用户参数；
不设置 stdin/stdout/stderr、cwd 或 env，沿用 subprocess 的继承语义，没有捕获/重写输出。
原 problem 检查、冻结源码核验和 stderr 路线标记先后次序不变；subprocess 只在 Windows
分支内导入，非 Windows 的原 `os.execv` 调用逐字保留。

| 路径 | 补丁控制流与声明范围 |
| --- | --- |
| 官方子 CLI 正常结束，退出 0 | 同步 run 返回后 SystemExit(0)，不提前把启动成功当执行完成 |
| 官方子 CLI 普通非零退出 | check=False 取得返回码，直接 SystemExit；目标兼容域为普通整数 0–255，含有效/失败/argparse 的 0/1/2 与后续假目标 7；尚未实测 |
| P2/P3 模块入口 | 两者仍裸调用 main(2/3)，但 helper 抛 SystemExit 而非仅 return 整数，因此调用方没有忽略返回值的分支；两入口无需改动 |
| 参数 problem 无效或冻结哈希核验失败 | 原 ValueError/RuntimeError 等异常向上传出，尚未启动官方子 CLI；不将异常转换成功 |
| 启动官方子进程失败 | OSError 等异常向上传出，不重试、不伪造 CompletedProcess；按普通 Python 未捕获异常失败路径结束，实际平台行为待验 |
| 等待期间被取消、KeyboardInterrupt、包装器崩溃 | 不保证已取得真实子返回码或已清理所有后代；不能按普通完成路径记账，仍需外层 Job/句柄收尾及 unknown 规则 |
| 非 Windows | 原 exec 替换路径保持，成功不回到 main；失败异常仍向上传出，未新增非 Windows 子进程代理 |

不承诺所有 Windows DWORD 高位码、崩溃/强杀状态或解释器终结错误都能经 SystemExit 完整保真；
这些不在本轮普通退出码声明域内，代码没有另行做有损映射，也没有验证这些情况。
本次没有新增 timeout、内部重试、文件轮询或固定 sleep。

## 4. 限制、费用与资源

- 不改 E0、配置、真值、C++、pool、scene_b、依赖或官方格式；不迁移 src/eval_proxy，
  不复制 Fang 测试树，不接入共享并发服务。
- Windows 包装器现在在官方子 CLI 运行期间继续存活，增加重叠的解释器内存/句柄和进程占用；
  venv launcher 可能额外生成进程层，不能把一次 subprocess 调用等同一个 OS 进程。
  没有测峰值、启动成本或吞吐，没有沿用旧 cap=12 声称新树必定容纳得下。
- 同步等待只解决正常子进程完成路径；不提供独立 CLI 的通用树级取消。外层受控 Job 应继续
  禁止 breakaway，保留自身所有权，独立核 PID/父 PID/创建时间/句柄、Job ActiveProcesses 和收尾。
  未经新验收，不声明正常收尾无后代或异常清理必定成功。
- 源码路径只发起一次本问题官方 CLI 调用，无循环或重试；这不替代运行时入口/费用证据。
  旧潜在 15 次 E0 和余 2 次封存不变，不重开旧 T0，不因本补丁发放新额度。

## 5. 静态检查与后续验收矩阵

本阶段只进行文本阅读、diff、Git blob 和 SHA-256 核对；没有启动 Python、import 项目模块、
AST/编译、构建、假目标/探针、单元测试、worker 或 E0/E1/E2；没有安装依赖或启动云计算。
执行 `git diff --check`；核对上述两个基线 blob；使用 `git diff --exit-code 603b0741e21c449d3db652ebd67c94f2dc014cc9 --`
检查 P2/P3 入口、pool、scene_b、src、data/raw、pyproject.toml 和 uv.lock 无变化。
最终完整差异只应包含本说明和 helper，目录做普通 dot_clean 与只读元数据复查。
这些检查证明修改范围和文本事实，不证明语法之外的运行正确性，也没有执行语法检查。

以下由独立验收者制定新固定输入、资源/时间/评价预算后执行；这张表不是启动命令或新运行许可。

| 最小检查 | 需要的观测 |
| --- | --- |
| 静态控制流复核 | 复核固定 helper、两个入口、普通退出码域及 unchanged 路径；不导入目标模块 |
| 假目标：等待 | 先写早期标志，再等待受控释放、写最终标志并退出；包装器在目标存活时保持存活，调用方在其结束后才返回 |
| 假目标：返回码/启动失败 | 分别 0/1/2/7；记录目标、包装器、调用方原始返回码；缺失可执行文件应走启动失败，不能伪装成功 |
| 假目标：参数与 stdio | 空格/Unicode 路径和参数逐项一致；复现普通文件 stdout/stderr，另核 PIPE 消费者无死锁；保留 cwd/env/stdin |
| 假目标：取消与崩溃 | 由独立驱动操控完整 Job 树，观察所有实际 launcher/解释器/子进程句柄；记录失败时完整 PID 身份并最终清零，不固定为三个进程 |
| P2 valid/invalid | 新目录分别 direct/adapter；valid 的 JSON/Trace/log 全字节与 truth、退出码匹配；invalid 的失败码/消息/无成功产物单列 |
| P3 valid/invalid | 共享 helper 也影响 P3，独立核相同契约，不用 P2 通过代签 |
| POSIX 回归 | 核原 exec 等待/退出码和失败路径；不能仅靠分支文本未变代签运行通过 |

假目标 harness 必须明确替身接缝、核验替身及与生产 helper 的绑定；不得改冻结原件或将只用
mock subprocess 的单元检查冒充真实 Windows 进程树验证。当前没有新增可执行测试草稿，
保留独立测试者对驱动实现的所有权。完整 Windows DWORD 若后续成为要求，应另加范围和案例。

## 6. 检查点与交接停止

工作区确认于 2026-09-24T02:06:13Z，HEAD=603b074；沿用原 session 的 continue 上下文。
已读原任务 5806158559 及最新 main 的官方目标/免费协作约定：方案 Makespan 与求解墙钟分开，
5–10 分钟是效率建议而非新硬门槛，本补丁不更改算法搜索、数值指标或实验额度。
固定提交、Draft PR、实际静态检查与未验证项交原 Issue15 后停止本阶段；
等待的是后续独立验收证据，不把补丁待验当作开发受阻，也不自行继续旧窗口。
