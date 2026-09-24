# E2 Windows 完整 CLI 补丁：独立静态审阅

结论：**在声明的 Windows 正常子进程完成、普通 0–255 退出码范围内，未发现静态阻断。** 这是进入受控验收准备的结论，不是 Windows/POSIX 实测通过，也不是 E2 验收通过。新驱动尚未实现和冻结，不能直接启动下文矩阵。

## 1. 目标、身份与范围

- session：`yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce`，continue；[原登记](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5803038801)。本会话已见开发交接和先前失败，不自称盲审。
- [具体交接](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5806255963)，以及核心交付 `5806225452`、原修订任务 `5806158559`；实际作者均 NikolaStarx / 120649042，已读原文。
- 实际接手 UTC `2026-09-24T02:17:15.0224696+00:00`（北京时间 10:17:15）；约 30 分钟首检查点为 02:47:15 UTC。本时刻是静态任务检查点，不是实验 T0。
- 分支 `codex/e2-cli-static-review-yuanzhifang`，起点 `a21f7ef7111933d309f3d616b9a3f2e7e861129d`；仅写本目录。生产 helper 仍由核心单写；旧门禁、驱动、结果和分支不改。

## 2. 固定输入和已读范围

| 固定版本 | 本次实际读取 |
| --- | --- |
| `abdfd31f358a035e5ecca3b0482a9d0881060ffe` | `docs/a/e2/WINDOWS_FULL_CLI_REVIEW.md` 全文 |
| `a21f7ef7111933d309f3d616b9a3f2e7e861129d` | helper、WINDOWS_FULL_CLI_FIX 全文，P2/P3 两个模块入口、相对 603b 的完整两文件差异 |
| `603b0741e21c449d3db652ebd67c94f2dc014cc9` / `a96f3ff445e6e85febb9fc13e4a0f2341fe10d3f` | 旧 helper 字节及旧门禁相关代码；旧 helper 同 blob |
| `15e9e3f1c9f09c09c1d0732465a2271e6b9c25fa` | 沿用此前本人已核的 127 份证据；本次只补看失败 controller/command、graph/plan、D_rss 内存记录，没有重复 127 全审 |
| `423f1320d98900256c238908bbd3da024d31cc41` | 沿用已核发布收据及原最终 HEAD 回读，不重开原 T0 |
| 当前补丁树内冻结源码 | `_official.py` 全文、包初始化与部分 import 链、contest_io CLI/写出段、P3 配置/评价入口；只作文本/AST，不执行 |

按 team-mailbox Skill 完整抓取成功：5 话题、232 评论，index 已读。按专项允许清单导入本次 3 条任务评论和本 session 原登记；没有导入其他账号全部历史、Pro 全文、Q2/Q3 或旧预演。共同 README/TEAM/ROUND1/SYNC_UPDATE/TEAM_WORKFLOW、FAST-EVAL 任务卡已读；其中早期“本轮暂不分配”由上述后来具体复核交接限定覆盖。沿用此前实际已读的官方目标和免费协作规范（6a7c678、b59d972），本补丁不改变 Makespan/求解墙钟口径，不启用 Actions。

## 3. 静态输出与判断

| 检查 | 结论与边界 |
| --- | --- |
| 返回路径 | `subprocess.run(..., shell=False, check=False)` 之后直接 `raise SystemExit(completed.returncode)`；裸 `main(2)` / `main(3)` 不会吞掉非零整数返回值 |
| 0/1/2/7 与 0–255 | 同一无映射分支；计划测 0、1、2、7、255（上边界），不是穷举 256 码。未承诺高位 DWORD、崩溃码或解释器终结故障保真 |
| 启动失败 | `OSError` 没有被吞掉/转为成功；没有重试。假目标缺失解释器用于覆盖 CreateProcess 失败，不能用“Python 启动成功但脚本缺失”代替 |
| 参数/stdio/cwd/env | 列表保持 `sys.executable, str(path), *sys.argv[1:]`；未另设 stdio/cwd/env。没有新增 shell、解析、截断参数。运行时引号/Unicode/空参数/管道仍待测 |
| 验证和顺序 | 原 problem 校验、冻结源码校验、stderr 路线标记均在子进程启动前；真实验收不能绕过冻结验证 |
| POSIX | 原 `os.execv` 语句及其参数 AST/文本均保持；subprocess import 在 nt 分支内。没有实际 POSIX 平台验收 |
| 改动边界 | 生产差异仅 `_full_cli.py` 和交接 Markdown；P2/P3 入口、E0/config、src、native/pool、依赖无差异 |

证据见 `STATIC_REVIEW.json`。本次运行的是 Git、文件读取和标准库 AST/哈希检查；**目标模块 import/执行、假目标、探针、测试、worker、构建、E0/E1/E2 评价和云实验均为 0**。AST parse 不执行代码；没有 py_compile、runpy 或 eval/exec。

三个非阻断的验收注意项：

1. Python 的同步等待针对所创建子进程；venv launcher 链必须核其等待链和原始退出码，不能把逻辑启动数当 OS 进程数。Windows 正常等待的行为还须实际验证。[Python subprocess 文档](https://docs.python.org/3.12/library/subprocess.html)
2. `SystemExit` 遇解释器退出期间 stdio 刷新失败，状态可能变成 120；属于已排除的终结故障，不应把普通码域的主张扩成所有故障完全保真。[Python sys.exit 文档](https://docs.python.org/3.12/library/sys.html#sys.exit)
3. 等待不提供树级取消；Job 禁止 breakaway、外层持有清理权，另测取消。新增包装器持续存活需要重审资源；Job 累计/采样活跃数不是精确峰值。[Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

## 4. 限制和未验证项

没有运行补丁，不确认旧事故唯一根因。没有检测本机 POSIX/WSL 可用性或借用队长设备/账户。没有验证最终 CLI 输出、0–255、启动失败、stdio、取消、实际进程峰值、实际内存上界；高位状态、并发 CLI、一般第三方子树和任意图不在本提案内。

原窗口潜在 15 次 E0、余 2 次、原 T0、600/750 未达事实继续封存。新预算独立，缺失产物/取消/未知不退款。旧 C/D/搜索通过不等于本补丁或 P3 CLI 通过。

## 5. 后续验收标准与产物

`VALIDATION_PLAN.md` 和 `matrix.json` 提出最小串行 Windows 矩阵：7 个进程契约案例 + 8 次真实 CLI，潜在 E0 独立预留 8。普通码域五个点、真正启动失败、受控包装器终止和 Job 树清理；实际 P2/P3 valid-invalid 均 direct/adapter 配对。POSIX 单列，Windows 不代签。

本交付是具体矩阵/预算提案，**不是完整可启动驱动**：新控制器、观测与接缝须先按该方案写在新的验收目录并提交固定 SHA，静态核对之后由协调明确批准，再建立新 T0。没有以未实现命令假称可运行，也没有把当前静态授权当运行授权。

## 6. 截止、交接和状态

本阶段产物经独立 Draft PR 交付，base 为固定补丁分支；只供审阅，不合并核心 PR、不写 Atlas。实际固定交付 SHA、PR/Issue URL、发布回读和最终工作区状态写在实质回执。无实验、子任务或目标进程在途；新控制器待范围/预算审定，Q2 保持休息。
