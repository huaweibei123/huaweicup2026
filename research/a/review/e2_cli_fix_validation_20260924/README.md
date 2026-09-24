# Windows full CLI 驱动：静态修订检查点

## 1. 任务与状态

执行会话 `yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce`，同一 Draft PR70。依据 [静态修订授权](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5806846650)，仅修改本 validation 目录。本轮接手 UTC 2026-09-24 03:17:21.8214834，约30分钟交固定检查点后停。本版是 R1/R2/B1/R3 的待复审实现，**不是运行准入或 E2 终验**。contract 与批准模板 approved / execution_enabled / runtime_review_closed 均 false；外部批准须绑定最终提交、bundle、sources、STATIC_CHECKS 和 index 哈希。

原准备检查点 [e3607fed01cc2cf39f9ad8f5a96d5922a37f36f5](https://github.com/huaweibei123/huaweicup2026/tree/e3607fed01cc2cf39f9ad8f5a96d5922a37f36f5/research/a/review/e2_cli_fix_validation_20260924) 保留。此次清空的是已具体修订的 B1 已知静态问题，不代表协调已复审通过；检查点仍需独立审阅及新的首次运行批准。

## 2. 固定输入与边界

- 生产 helper 固定 a21f7ef7111933d309f3d616b9a3f2e7e861129d，SHA256 fb33ab3d120479ff70dbea87a730a08b16b90af44996cf78746d7880351b091b；未修改生产、E0 或旧结果。
- 静态计划固定 53c151ecaef2636bcf0eb1946c112f19f8cec739，本目录只覆盖其中逐链假设；旧计划文件不改。
- gate_helper.py 原语固定 569c65f2673d6fc2a99507f151ca04b814e1dc68，SHA256 e5af8da2e6cc4288d7066769bb246c68f51da8bc3c2d6da2f4acc45698c88621，逐字节保留。
- 15例仍为 F0/F1/F2/F7/F255/F-startfail/F-cancel，以及 P2/P3 valid/invalid 的 direct/adapter。潜在E0保留8、逻辑创建请求43（含失败尝试）、parent启动1、pool workers/formal/debug=0，均为未批准的新窗口提案。
- 旧潜在15、余2和旧T0封存；Q2休息，LYX独立范围不动，Actions不启用，无Atlas签写、子任务或目标进程在途。

## 3. 修改与静态处置

| 问题 | 本版实现与证据边界 |
| --- | --- |
| R1 隔离入口 | controller/bootstrap/seam 在本地模块导入前，以自身文件路径只加入被外层manifest锁定的driver目录，并检查common来源；三条启动命令保留 -I -B，显式增加 -X utf8。-I下的PYTHON环境变量不作为编码生效证据；非隔离的生产CLI/假目标仍继承受控环境。 |
| R2 Windows审计 | 保留原始command_line及str类型、固定expected_tokens、expected_image_token；另核对目标实际sys.argv。Windows省略executable关键字时审计raw_executable是None，单独保存类型；不把命令行拆成字符或假设该字段是映像路径。空token、空格、引号、尾反斜杠均在固定token列表。F-startfail检查缺失exe命令行与真实OSError，明确无target argv。 |
| B1 模型修订 | contract.aggregate_policy 明确替代逐逻辑链≤3假设。逐case原数值作为直接累计政策：普通fake9、startfail6、cancel12、direct6、adapter9，合计123；控制器独立≤3，根Job合计≤126。外层在case开始前取得完整PID集、累计数、FILETIME/映像及非继承观察句柄，确认launcher/实际controller均在集后才ACK。每例记录实测TotalProcesses，保留已知launcher/ready与创建时间关联；最终根Job累计数必须等于控制器实测数+各case实测数。未知内部父子边不推定，exact peak仍unknown。 |
| R3 外部进程与截止 | 删除运行期两次Git启动。共同T0之后直接读HEAD/ref、批准index指纹、workspace_files与namespace_inventories；sources与STATIC_CHECKS另由外部批准固定哈希。所有文件读取属于90秒准备段，无metadata子进程。bootstrap在结果写入前记work_finished_tick，35秒工作后最多3秒等bootstrap/Job全部退出；失败保持单个10秒清理额度，且受670秒总截止约束。 |

R2依据是本机已锁定CPython 3.12.14的Lib/subprocess.py文本：Windows将tokens经list2cmdline转换后调用审计事件，未指定executable时其值仍为None；没有导入或运行该目标代码。

单case active14 / Job2GiB / 单进程512MiB；根Job active17 / 2.25GiB；controller256MiB；available≥3GiB，均保留。累计政策由运行期监测、最终会计和下一例准入检查执行，不声称Windows存在原生累计创建次数硬限制。短命进程若漏观察、映像未知、计数不符、采样超时、句柄退出不闭合则停止，不重试或增cap。

## 4. 产物与验证

驱动为7个Python文件及launch_once.ps1，契约与批准模板进入10项bundle。sources.json保存原5485项环境/输入身份（来自上一轮纯文件hash，未因本轮改代码重测环境），新增工作区固定字节清单与相关目录即时子项清单。workspace_files覆盖本版本所有tracked文件，sources/STATIC_CHECKS为避免自引用分别由批准文件固定；目录清单覆盖tracked父目录、repo环境文件父目录及本地site-packages入口。新增未跟踪命名空间文件会导致库存不符；排除.git和__pycache__。这不是对排除缓存、未列外部目录或竞态的完整git-status替代证明。

STATIC_CHECKS记录本轮实际AST、PowerShell Parser、JSON、哈希与差异检查。**驱动/目标 import、执行、--help、假目标、探针、测试、worker、编译、E0/E1/E2、安装、云调用全部0**。允许的普通Python静态处理进程只运行内联标准库文件读写/AST；没有导入任何新驱动。一次静态文本读取曾因系统默认GBK失败，随后显式UTF-8读取，未触发目标。

本轮仍未验证：Win32结构/Reflection.Emit、隔离入口实际兼容、嵌套Job、PIPE、退出传播、取消、快进快出观察完整性、真实内存、完整预检能否在90秒完成、单次文件/OS调用迟滞及路径别名。AST通过不证明以上行为。POSIX仍未排负责人或运行窗口。

## 5. 运行与验收契约

未来另行批准后的入口形式仍是 launch_once.ps1 -ApprovalPath <仓库外批准文件> -EvidenceName <新的唯一名称>；本阶段从未调用。批准者在最终固定提交上提供具体index指纹，运行期从共同T0重新核对；任何index变化也会保守失败。启动前读取失败时不启动controller。运行窗口无Git/gh/编译器子进程，43只称矩阵Python逻辑请求；PowerShell宿主已存在，实际OS进程数另测并对账。

共享T0的准备90、执行660、清理670、证据发布目标1200、最终回执目标1500、总窗1800保持不变。后3项仍由交付流程沿同一QPC记账，驱动不自动发信/发布，不将它们误称已实现的后台计时服务。35/3/10为工作、正常退出及失败清理边界，不能在660后新开工作。

## 6. 交接与下一步

本轮固定SHA、bundle/sources/static hashes、Draft PR70和Issue回读交协调复审后停写本范围。协调复审须逐项核对R1/R2/B1/R3后再决定是否批准一个新运行窗口；模板默认false，不借时间到或队长催促自行开测。E2旧CLI问题依然等待实际验证与验收。
