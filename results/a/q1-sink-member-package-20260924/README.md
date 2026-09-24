# P1 sink-peel：成员八格固定候选包（准备完成，尚未执行）

本包仅交成绩台研发接收与分配 owner `s-7c98…` 安排 LYX / farmer 等实际执行者。
准备者没有启动任何求解或E0，也没有向成员发信。源码字节核对、参考原件复制和
合成子进程控制测试不构成真实图评分。执行人须先取得 owner 的明确批次/资源窗口。

## 固定任务六字段

1. **目标**：检验粗 sink-exclusive suffix waves 对另外8个已静态识别激活的
   单连通真实图是否改善官方P1 Makespan；完整保留变差/失败。收益不以波数或零spill代替。
2. **输入**：`manifest.json` 固定图`005,047,064,069,075,082,085,086`，全部k4。
   原ZIP/config/10份官方源码只读，运行前后逐字节哈希核对；所选图在ZIP中的字节也逐个核对。
   算法 `src/q1/sink_peel.py` 固定`d89a6cbf1e292f2abc36b4fef89590d16ccb1ab2`，
   及其 bounded_tasks/tree_frontier/component_pack 与该提交原字节一致。
3. **产物**：每格独立plan/result/trace/official.log/诊断/stdout/stderr/run.json，
   批次batch/preflight/postflight、完整失败/未执行行、board-feed.json与comparison.json。
   成功result/trace仅无损gzip，失败/部分文件原样保留；每个字节引用有SHA256。
4. **边界**：最多8次完整solver+8次独立E0；1worker顺序执行；每solver30秒/E060秒，
   整批600秒调度/执行deadline（包括源码核对与ZIP准备）。剩余总预算不足时单进程期限缩短；
   停止后的直接子进程kill/wait最多10秒宽限和最终字节复查可使收尾稍超600秒。
   0重试/E1/E2/GPU/Colab；不可改参数、加核数或追加候选。第一次单格失败/超时、
   源码不符或监督错误停止派发，其余明确not_run。
5. **验收**：所有原件及调用账真实完整，直接子进程已回收；比较Makespan、额外DDR/spill、
   Task/波数、完整求解墙钟和独立E0墙钟。schema/原件准入与独立复跑、算法科学验收分开。
   未实际运行不能预填eligible或把预制manifest当成绩feed。
6. **截止/交接**：由owner安排成员执行窗口；本准备任务到固定包交付结束。
   实际执行固定此包提交，不从浮动main或“latest”运行。执行完成交owner统一接收。

参数固定：max_rounds64/max_sinks64；fallback factor4/trigger4096/chunk1024。
每个solver调用内部包含一次完整bounded04构造，该成本已计入同一进程端到端墙钟。
无在线评分、模型训练或针对当前图的隐藏预计算。ZIP物化/源码校验属于批次准备，另计；
图JSON读取、构造、结构验证、计划/诊断落盘、Python启动及退出均属于solver wall。

## Windows / macOS / Linux 最小命令

成员在保存自己工作后，使用 owner 提供的本包完整提交建立独立worktree，不覆盖原任务。
下面命令在新工作区根执行；`FULL_PACKAGE_SHA`、session、runtime、run-id和并发说明必须替换成实际值。
`FULL_PACKAGE_SHA` 是本包最终提交，运行器要求HEAD精确匹配。
Windows建新worktree可用`git -c core.autocrlf=false worktree add <新目录> FULL_PACKAGE_SHA`，
只为本次检出保留LF原字节，不修改全局Git配置。自动CRLF换行会被哈希预检拒绝；
不得通过改官方源码或更新哈希来绕过。

```text
uv sync --locked
uv run python -B src/q1_benchmarks/sink_member_batch.py preflight
uv run python -B src/q1_benchmarks/sink_member_batch.py run --run-id MEMBER-YYYYMMDDTHHMMZ-sink8 --expected-runner-commit FULL_PACKAGE_SHA --producer-session login/s-32hexuuid --runtime-id member-windows-py312 --concurrency-context "actual owner-agreed resource window and other workloads" --execute-authorized
uv run python -B src/q1_benchmarks/sink_member_batch.py export --run-id MEMBER-YYYYMMDDTHHMMZ-sink8
```

没有授权窗口仅运行preflight；它不import算法或评估器。`run`不能重用已有run目录。
`--execute-authorized`用于防误触，不替代owner的派发授权。发生中断先保留目录与进程状态，
向owner交现有账，不能删目录重跑或增加retry。批次未正常收尾时export拒绝，交owner判断恢复证据。

本runner没有`os.killpg`或Unix信号依赖，使用`Popen.wait(timeout)`、`kill()`、`wait()`
回收**直接子进程**，这些API在Windows可用。静态检查固定solver/官方源码没有启动子进程的代码；
不承诺任意未来子进程树清理。每次启动的完整Python命令与真实UTC/墙钟、exit_code、PID、
cleanup_confirmed记录在run.json。原始stdout/stderr不改写，若失败traceback含个人路径，
发布前由生产者保全原件并显式衍生脱敏副本，不应悄悄覆盖原始证据。

准备期仅在macOS / Python3.12.13测过合成控制器：成功退出、非零退出、超时kill+wait、
启动失败4项。没有真实图构造/E0；**没有实际Windows执行验证**，也未预先声称8格会成功。
Windows成员可先运行`self-test`验证本机控制器，再按已授权窗口执行；self-test仅4个合成小进程。
CPU/RAM/平台/Python/锁文件哈希会现场记录；未采样线程数和peak RSS明确null。
本包没有硬内存限额或资源独占保证，资源窗口由owner安排；不得把1worker当整机无其他任务。

## 开跑前可用RAM与人工停止口径

建议只在 **可用RAM至少4GiB（4294967296 bytes）** 且owner认可的空闲窗口开跑；
它是人工资源准入建议，不是solver所需峰值证明、OS硬内存上限、自动监控或实时保护。
本runner仅记录总RAM，没有可用RAM自动检测或每格前暂停，不能把`ram_bytes`当可用量，
也不能声称已落实逐格强制4GiB守卫。负责执行的成员应保持人工监看；没有观察条件时暂不开跑。

观察点为：调用`run`之前；执行期间持续查看平台内存工具；每收到一格完成JSON时记录快照；
发生内存压力/其他任务抢占时立即再次观察。runner连续派格，格后观察可能晚于下一格启动，
不能把它追认为“下一格前检查通过”。没有实际看见的观察点写`unobserved`、数值写null。

平台口径示例：

- Windows：任务管理器“性能→内存→可用”可人工观察；若需精确字节，PowerShell用
  `([uint64](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory) * 1024`，
  记录原值和方法（该CIM字段按KiB换算）。不以Installed/Total RAM替代。
- Linux：`free -b`的`available`列，或`/proc/meminfo`的`MemAvailable`×1024；记录实际命令及原值。
- macOS：记录`vm_stat`页大小与free/inactive/speculative页数，以及`memory_pressure`观察。
  页大小乘这些页数之和仅为可回收余量代理，不等于OS保证可分配字节；须标`reclaimable_proxy`，
  不把pressure百分比或总RAM冒充可靠可用字节。由owner明确认可该代理口径后才用作4GiB门槛；
  无法取得/确认实际余量时记unknown并暂不开跑。

成员把真实UTC、case/阶段、available_bytes或proxy_bytes、方法/单位、observed/unobserved、
决定与触发原因写入本run的`resource-observations.json`（本包未预填任何成员值）。
建议初始记录在本人的准备目录，开跑生成run目录后复制原记录，不提前创建runner会拒绝复用的run目录。
这些是独立资源观察附件，不改官方result或伪造peak RSS；可在现有notes说明实际观察范围。

开跑前低于4GiB/余量未知：不调用`run`，保留资源记录并交owner重新排窗，不能增加重试预算。
运行期间实际观察到低于4GiB、显著压力或资源冲突：立即在runner前台发送一次Ctrl-C，等待其收尾，
核对`cleanup_confirmed`、当前格failure、后续`not_run`与batch终态；不继续下一批或更换run-id重跑。
本人工策略无法保证采样间无瞬时峰值，也不能保证已经进入下一格前成功中断。

代码静态核对：`direct_process`在等待直接子进程时捕获包括KeyboardInterrupt的BaseException，
finally执行kill+wait；返回失败后`run`记录实际调用与failure，停止后续并保留not_run。
这仅说明该受控路径，**本次没有实跑真实图中断测试**。若中断发生在启动前、压缩/写收据期间、
连续Ctrl-C、关窗/强杀或系统错误中，不承诺完整终态/可直接export。特别是batch缺finished_at、
cleanup不明、run状态与调用账不一致或有supervisor_failure时，保留整个目录和原始收据交owner处理，
不要把部分结果标成功，也不要手工填0或补造not_run来凑feed。恢复失败证据不授权重跑。

## 现有证据与分母复用

`reference-index.json`及`references/`已复制并核对同图bounded04与官方单核结果原始压缩字节，
来源固定`ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9`，不需要成员重新跑参考值。
真实k4构造与官方singlecore分母不同，不以任意旧P1 k1方案冒充分母。

048/071已经测过，**不在8格执行矩阵**。本分支祖先含原计划/result/run；manifest引用固定
`869393453dc1e0e3ae7c119c0ba3f1d66a35f315`下两格原件，Makespan分别116460/12078。
未来可把同源码/参数的这2格与8个新attempt作10图研究汇总，但须保留不同机器、批次和计时差异；
不能算作10个新评估，不能冒充全100图结果，更不能混入其它算法历史best。

## 成绩台交付

导出路径：`results/a/q1-sink-member-runs/<run-id>/board-feed.json`。
导出器填写真实成员session、机器、固定runner/solver来源、参数/预算、每次启动调用数、
未知项原因及官方单核原件引用；不会调用solver或任何评价器。所有相对原件均在同一最终Git提交。

**生产方须自己完成导出和预检**，接收owner只负责接收/复核，不承接常规整理。
已通过只读GitHub查询及源码读取确认 [PR113](https://github.com/huaweibei123/huaweicup2026/pull/113)
的实际head为`bb7d04369112f164034664c52107127cb87e35a6`，状态merged。
这项PR主要修改网页更新机制；这里固定使用的是**该提交里实际存在的完整协议工具**，
不宣称PR113新改了submission schema。工具入口是`src/benchmark_board/protocol.py`，
它还读取同checkout的core/app、schema、source-manifest和calibrations，不能只复制一个py文件。

生产者在自己的仓库创建一次独立只读工具worktree；以下从算法/结果工作区根执行：

```text
git fetch origin codex/benchmark-browser-updates-20260924
git -c core.autocrlf=false worktree add --detach ../q1-board-preflight-pr113 bb7d04369112f164034664c52107127cb87e35a6
```

先提交本run的feed及全部引用原件，取得实际`FULL_RESULT_SHA`；然后由**同一生产者**运行：

```text
uv run python -B ../q1-board-preflight-pr113/src/benchmark_board/protocol.py results/a/q1-sink-member-runs/RUN_ID/board-feed.json --repo . --commit FULL_RESULT_SHA --submission
```

`RUN_ID`和`FULL_RESULT_SHA`替换为本次真实值，工具worktree保持固定bb7d0436。
`--commit`读取该结果提交的feed/原件；`--repo .`指向生产者结果仓库，不指向工具worktree。
另保留stdout、退出码、工具SHA、结果SHA和实际命令为预检收据，再提交收据。
应检查`valid`、`eligible`和`reported_or_failed`，不能仅凭退出码0称所有格可入榜。
预检只读、零solver/evaluator，不连接网络、不写中央账本；不得为补齐格式重跑科学实验。
工具fetch或预检失败由生产方修复并交实际错误，不转交接收端代做、不偷偷换浮动版本。

字段兼容核对：现runner仍导出`schema_version=1/submission_version=1`及既有完整provenance、
空值原因、identity/artifacts/baseline；本补充没有新增feed字段或改算法参数/预算。
README/manifest内的内存观察与预检说明属于交接元数据，未变成不存在的自动保护功能。
此时8格仍未执行，没有新feed可预检；上述字段是静态接口核对，不冒称真实新feed已准入。

成员要显式保全被`.gitignore`忽略的`official.log`（只force-add本次明确日志）；提交后逐项
核验feed引用可`git show <结果SHA>:<path>`读取且哈希相同。报告包含失败和not_run，不能只上交好格。

静态预检在`7ac0e72418c21008e4b0e76e08726c2f191a1e85`完成：29个声明/官方文件身份、8个ZIP图字节及16份参考原件一致。收据见`static-preflight.json`。随后仅归档收据与执行说明；没有新增求解或评价。

补充修订：只更正文档/manifest的人工资源观察和生产端固定预检职责。执行时`--expected-runner-commit`必须使用包含本补充的**新包完整SHA**，不能继续填旧c45fc47b。算法/runner字节与原8格/8+8调用预算未变，0真实solver/E0/E1/E2。
