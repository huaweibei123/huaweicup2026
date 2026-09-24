# P2 Windows 续测方案与专用驱动（待批准，未执行）

状态：本交付仅代码和静态审查。新增 E0/E2/debug/CLI 评价均为 **0**，没有 DLL 加载、构建、安装或新 T0。PR52 的 `a38dc6fea7f4d2f85f00bb7cdf1e5c9488aec2d7`、失败驱动和原始结果保持原样。

本专项仍由 `yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce` 执行，协调会话审核并明确批准新调用。Q1/Q2 机制试验、P3、正式图和正式接入均不在本方案内。

## 任务卡六字段

1. **目标**：修正后续测试的完整对象类型契约验证方式，补 C-full 这一项以及上轮未执行的 D/E；不重跑 A/B、缺库注入、错误 ABI 注入或 native_enabled=False。
2. **输入**：生产代码固定 `997813c7c83d4d18a0a8e2a19b5be37b90223e01`；新分支从原交付 `a38dc6f` 分出。只用原合成 G/17 byte 边/R 和配置，逐字节 pin 原 inputs/IDENTITY/A-R 真值/B-empty 异常等六文件。完整 SHA256 见新 `contract.json`。
3. **产物**：专用 `continuation/run_continuation.py` 与机器可读契约、本方案；未来若批准，另交原始类型对象、类型树、规范 JSON、请求前账本、Job/CLI 原件及双 hash。当前不生成测试结果。
4. **限制**：拟 12 record + 5 固定 E0 = 17 逻辑入口，潜在合成 E0 硬上限 17；debug=0、正式=0。零重编译、零安装。精确固定矩阵，未知不退，首非预期失败停止。
5. **验收**：C 的 Python 完整类型和值相同、两处 core key 确认为 int；并列 JSON 契约通过；D/E 各自满足下列断言且实际进程树清理。保留旧 C 失败，不把新结果回填为旧运行通过。最终保持 review，交协调判定。
6. **拟截止**：新批准后另开 **600 秒**完整窗口；T0 在任何源/hash/环境准备之前落盘；90 秒内完成预检并开始 C；300 秒前终止评价并保留清理尾部，余下 300 秒用于证据和报告/提交/PR/最后核对。尚未开始该窗口。

## 每项调用与预算

| 阶段 | 固定用例 | record | 固定 E0 | record 的潜在 E0 | E0 总上界 |
| --- | --- | ---: | ---: | ---: | ---: |
| preflight | 已有 BC 实际加载、ABI=1 | 0 | 0 | 0 | 0 |
| C_full | 新完整官方真值一次 + pool full 一次 | 1 | 1 | 1 | 2 |
| D_order | 双 worker、每 worker 一请求回收；[R,{},R,R] | 4 | 0 | 4 | 4 |
| D_timeout | 极短 timeout 一次 + 同 pool 恢复正常一次 | 2 | 0 | 2 | 2 |
| D_rss | 阈值 1 byte 的两次 R 回收 | 2 | 0 | 2 | 2 |
| E_search | 冻结 search CLI 一次，三行 [R,{},R] | 3 | 0 | 3 | 3 |
| E_full_valid | 官方 CLI 与 full adapter 各一次 R | 0 | 2 | 0 | 2 |
| E_full_invalid | 官方 CLI 与 full adapter 各一次 {} | 0 | 2 | 0 | 2 |
| **合计** | 无 debug，无正式图 | **12** | **5** | **12** | **17** |

“固定 E0”包括 C 的显式 Python E0 一次、直接官方 CLI 两次、adapter full CLI 两次；不把 adapter CLI 漏记为普通 IO。record 的 12 个槽包括 C full 必走的一次 E0，其余原生请求也按一次潜在 fallback 预留；没有重复计费。实际成功路径的 E0 数不是上界，超时进度仍须记未知。

调用链维持原固定证明：每个 `evaluate_record` 最多转入一次匹配 P2 `evaluate_scene_b`；pool 每消费一个 plan 发一个请求；search CLI 每行一个请求；full CLI 用 execv 跳到官方 P2，一次入口。驱动只有 C 的一个显式 oracle 调用点，没有 debug、比较辅助函数内的隐式 oracle、重试或遍历新增输入。

D/E 成功记录复用原 `A-R.truth.json` 的三个指标；{} 复用已核 B-empty 的 status/type/message/route/problem。所有复用工件先核固定 hash 和对应 G/R/config。C 唯一新增显式完整 E0 是为取得保存前的真实 Python 类型：旧 JSON 真值无法恢复完整原类型，不能用推测重建键类型冒充新原件。

## C-full 的双契约

1. 将新显式 E0 完整返回值立即保存为 pickle protocol 5、可读的带类型 JSON 树、规范 JSON，完成 flush/fsync；本驱动不会 unpickle 文件。
2. pool full 原对象返回后，在任何类型/数值比较之前保存同样三份工件。即使之后断言失败，原键类型仍可复核。类型树的字典键单独编码，区分 int/str/bool；list/tuple 保留区别；float 用有限值的 hex 表示。仅忽略字典插入顺序，不放宽数值和类型。
3. 分别记录两处 `memory_peak_by_core` / `step3_by_core` 的每个键及其类型，要求 core 集合正好 {0,1} 且所有键的 type 恰为 int；再比较两个完整类型树。
4. 另做两个原对象的规范 JSON 全字段对照，并和旧 JSON 真值比较。JSON 契约允许 JSON 标准的整数键转字符串；它与 Python 类型契约分别记录，不能用 JSON 相同替代完整类型相同。

本轮固定输入的两种比较必须同时通过。原失败驱动既不修改也不再调用；新的复核结果不追溯改写旧 C 的失败状态。

## D/E 断言与退出行为

- D_order：返回索引 0/1/2/3、预期 ok/invalid/ok/ok，各成功行三指标逐类型一致，{} 异常匹配旧完整记录；固定 pool.py 按两条分块且 slot_index 固定，逐行记录 index→slot(index%2)、返回PID与slot PID相等、任务计数=1、max_tasks=1且RSS策略为None；核同槽 0→2、1→3 均换PID、前一个Process对象已closed，特别保留{}也令slot1计数达到阈值的证据。原max_tasks机制没有recycle_reason返回字段（该字段仅RSS分支有），不能伪造；归因明确来自源码分支与slot观测。保存整个PID集合，要求同块两PID不同，不强制跨块四PID全异；Windows可能复用PID，若同槽PID相同则只能判未证实并停止，不补跑。每行落盘后立即验证，发现意外结果就关闭生成器和 pool，不消费后续批次；同一双 worker 批次已在途的请求仍计入原预留。
- D_timeout：一次 `1e-12` timeout，随后把同 pool 的正常请求时限设为 30 秒，仅一次恢复请求；timeout 的内部进度记未知，不记零 E0。超时本身是预列路径，状态或恢复失配则停止。
- D_rss：worker_peak_rss_bytes 正数、明确 `peak_rss_threshold` 原因、两次请求不同 PID。每行即时验证。1 byte 是回收触发阈值，不是硬 RSS 限额。
- E_search：显式 `--problem 2 --workers 1 --timeout 30`；退出 1、三行索引/状态/问题路由正确，错误后继续，成功指标及 `.run.json` 的 P2 engine/worker 信息匹配。冻结 CLI 的三行作为一次已预留调用批次；返回后检查，不能在其中插入新测试逻辑。CLI 的 worker startup 使用源码默认 30 秒，整个 CLI 子进程另受 30 秒外层限制；这里不冒称 CLI startup=15。
- E_full_valid：每次返回后立即校验完整官方 JSON，官方 CLI 合同明确追加 `input_graph` / `input_plan` 两个文件名字段，期待结果为旧完整真值加这两个精确字段；不能直接和缺字段的 API JSON 比较。两次均成功后核 JSON/trace/log 三文件字节相同。adapter 路由 stderr 单列。
- E_full_invalid：两次 exit=1，stderr 包含已核官方错误消息且不产出成功 JSON/trace/log；不把正常报错当评价失败后重试。官方和 adapter 的 stderr 不要求逐字节相同。

## DLL 与环境复用条件

拟在当前 Windows 专项 worktree 内执行，新分支 `codex/e2-p2-continuation-plan-yuanzhifang`；仅新增原批准 review/results 目录内的 continuation 子项。生产代码、旧驱动、PR52 原件和别人的 worktree 不变。

预检逐项核原 IDENTITY 中全部生产源码、C++、uv.lock/pyproject/config 和三个 DLL 的工作目录 hash，要求 Python 完整版本字符串及 NumPy 2.5.3 匹配；不安装、不 uv sync、不编译。BC SHA256 必须为 `c01a4e0f6c1868945392067ef70825b7ed6e8090c3240af91d18242199f706d9`，依赖 DLL 也匹配原 hash。随后只在已归属 Job 的 preflight 子进程内实际加载固定路径库并核 ABI=1。

任一文件缺失/变化、runtime 变化、ABI/真实加载路径不匹配，立即停，不能回退重编译/安装/改 PATH。原旧驱动的 CRLF/Git 差异不作为此次生产文件校验对象，保留其原报告；新 continuation 目录所有文件必须与批准 HEAD 的 Git blob **逐字节相同**，提前设置 `-text` 防止再出现此差异。

## 时间、预留与进程树约束

本次代码审查不建 T0。未来只有协调明确批准后才在 Git 外创建独立 approval 文件，其中需包含 `schema=p2-windows-continuation-v1`、`execute_approved=true`、准确 `authorized_commit`、批准来源 reference 与完整 CAPS；这只是执行程序的防误启动条件，不代替本人/协调的真实授权。仓库不会提交一份能自动运行的批准文件。

命令形态（当前不得执行）：

```text
.venv/Scripts/python.exe research/a/review/e2_p2_windows_20260924/continuation/run_continuation.py --private <全新Git外证据目录> --approval <另行批准文件>
```

新目录必须不存在且不位于 Git workspace；不复用旧 gate/T0/账本。开始后先记 UTC 和 GetTickCount64，再验证批准 HEAD、干净工作区、固定基点 ancestry 和新驱动字节。所有 save JSON 先在同目录独占创建临时文件，写完flush/fsync后os.replace原子替换；exclusive初建使用Windows不覆盖目标的os.rename，因此T0/gate不会半写即出现，既有文件也不能被初建覆盖。受控终止最多遗留.pending临时文件，正式账本仍是上一份完整版本；保留残留供审，不由缺失回执推成零调用。每阶段先原子落盘全阶段预留，每次实际入口再原子落盘子账本，调用只发生在预留成功返回以后。未返回、异常退出、CLI timeout、预列极短 timeout 均保留预留，不能用已知返回数冲减潜在 E0。

每阶段单独 Windows kill-on-close Job，子进程先等待私有 gate，归属 Job 后才 import E0/E2 或加载库。包括 pool worker、资源追踪进程、CLI 与 execv 后代。一般阶段含启动最多120秒；C_full整阶段单独收紧为30秒，外层等待再预留10秒清理，因此C的直接官方入口和pool full共享最多约20秒执行段，每个官方入口均被更保守地限制在30秒以内。它不是只有约110秒兜底的同进程裸调用：C子进程（含direct E0）被外层Job的20秒执行截止控制，不增加oracle调用或拆出额外测试。所有阶段同时受T0+300和清理尾部约束；API正常请求30秒、startup15秒、workers≤2、编译缓存16MiB/worker；C阶段上界会先于这些宽松内部超时终止。系统终止或清理未完成仍记真实失败/未知，不宣称操作系统硬实时保证。

断言/序列化异常时，pool 在 finally 中执行 close/再次close并记录 slots；外层在任何 BaseException（含中断/子进程超时）后查询 Job、必要时终止全部后代、最多 5 秒等待退出并复核 active=0。强制清理、未能查询/归零或异常退出都使阶段失败，不冒称自然退出。之后停全部阶段，保留可能未交付的请求，不修源码、不重试、不自动开第二窗口。

600 秒包括全过程准备、执行、原始/公开证据整理、报告、提交/推送/PR和最后 hash 核对。程序负责评价阶段的时限；300–600 秒交付收尾由执行任务遵守，不能声称已对后续交付命令实现自动 kill。超出前置预算则交部分准备/未执行结论，不能重置 T0。

## 本次静态验证与未来交付

本次只对新文件做 AST 语法解析、常量预算合计和代码/来源审读；没有 import 或执行新驱动，没有加载 DLL，没有 py_compile/native 编译。六份复用证据已读取并计算固定 hash。无法以静态检查声称 Job、类型工件、CLI 或结果已运行成功。

未来交付需保存完整对象 pickle/类型树/规范 JSON、原始 stdout/stderr、每请求预留及结果/未知、实际加载路径和 hash、源码字节快照、Job清理、全过程时间。公开前只脱敏个人路径，保持原件和双 hash；校验最终 Git blob。依旧区分平台定点测试、正式方案质量和求解端到端 wall；测试通过也不自行批准 Q2 接入或 P2 终验。
