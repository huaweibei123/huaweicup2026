# M 元数据专用入口：静态准备

本提交只准备源码，**没有运行 M，没有 metadata.json 实测产物，也没有新的执行许可**。运行状态为 **blocked：固定执行端、外部截止与终止责任尚未闭合**。M 即使将来通过，也只证明其观察范围内的声明/包装 IL，不证明 ABI 调用、203 根因、控制器准入或 E2 验收。

## 1. 任务目标与授权

负责人 `yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce`，沿用[原登记](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5803038801)，上下文 `continue`。只为独立复核隔离出声明证据入口，不另造监督器。

- [队长决定 5812301803](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5812301803)：实际作者 NikolaStarx / 120649042；明确允许准备、不执行。
- [M/S 提案 5808615198](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5808615198)：实际作者 yuanzhifang30-sudo / 281850557；本提交仅承接 M，S 的归属与回收另议。
- [本 session 实质接手及目标理解](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5812405472)：上述两条已全文读取并核作者，非空 ACK。

本地新增分支 `codex/e2-metadata-prep-yuanzhifang`；PR base `codex/e2-interop-static-yuanzhifang`。创建前工作树干净，本地及远端 base 均为 `6f91055d37bd94d4d0b9f7789ccb36baf0d44f88`。旧提交、结果和其他工作树保留。

## 2. 输入、固定来源与摘取差异

来源：[6f 的 launch_once.ps1 第 95–177 行](https://github.com/huaweibei123/huaweicup2026/blob/6f91055d37bd94d4d0b9f7789ccb36baf0d44f88/research/a/review/e2_cli_fix_validation_20260924/launch_once.ps1#L95)，从 `$e2Assembly =` 到 `$e2Native = $e2Type.CreateType()`，包括其行末换行。

| 对象 | SHA-256 / 范围 |
| --- | --- |
| 原文件完整字节 | `fd24c63a6c701213d86ecaecbf735d36c5a48652033eeadb952a6412ea25809b` |
| 直接摘取区块 | 5,852 字节，`8b854e90cdde6f8dc4239032015896f6f50d18a8910099e36741833d7ef793f6` |
| 新文件摘取区 | 两条 `EXACT 6f` 标记之间；与上述区块逐字节相同，零文本差异 |

15 个原生声明、6 项显式 DllImport 字段、3 个 Captured 包装、局部槽和 Emit 顺序完全保留；未重命名程序集/模块/类型/方法，未修改声明签名。区块在新脚本的 `try` 中，外围增加模式/输出路径校验、独立期望表、只读反射采集和结果写入。没有点源、导入或运行旧 driver，也没有摘取它后续的 Job、进程创建、Assign、Resume、清理或 controller 调用代码。

`M_SOURCES.json` 是本次静态来源/检查清单，不是未来元数据结果；不含任何伪造的 CLR/IL 实测。原 `launch_once.ps1`、`sources.json`、`STATIC_CHECKS.json`、helper/controller/fixture/矩阵/contract/批准模板均未修改。没有重扫 698/5485/233 库存。

## 3. 输出与未来精确入口

源码为同目录 `interop_admission_probe.ps1`。唯一模式为大小写精确的 `Metadata`；要求命名参数，未知参数由高级参数绑定拒绝。没有默认模式、S、自动切换、重试、编译器、函数指针、JIT 预热、原生调用或额外外壳。

**以下只是未来需另批的 argv，不是本次已执行命令：**

```text
<已固定身份的 pwsh.exe>
  -NoLogo -NoProfile -NonInteractive
  -File research/a/review/e2_cli_fix_validation_20260924/interop_admission_probe.ps1
  -Mode Metadata
  -OutputDirectory <本次批准的新私有目录>
```

工作目录是固定交付提交的仓库根目录；由既有执行端直接启动这一可执行文件一次。`pwsh.exe` 的绝对定位、版本/字节哈希、提交与 probe 哈希、唯一输出目录及批准记录须在执行前固定；当前未填写为假定可用的执行批准。不能增加一层 PowerShell、shell、launcher 或监督进程来实现此命令。未给 Mode 或不是精确 Metadata 时，在类型生成前拒绝；输出目录已存在则拒绝。共享文档不写个人绝对路径。

未来只有一个 `metadata.json`，用 CreateNew 写入，不覆盖已有文件。字段分为：

- `expected`：独立手写的 15 项期望签名、六字段、实现标志；不驱动摘取区的 Emit。3 包装期望序列由独立语义模板展开，未从实际 IL 或 MethodBuilder 抄回。
- `actual_environment` / `actual_type` / `actual_native` / `actual_wrappers`：实际 PowerShell/CLR、进程与 OS 位数/架构，生成类型的 MethodInfo、DllImport、返回/参数类型、方法/实现标志，及 3 包装的原始 IL Base64、局部变量、InitLocals、异常区域、最大栈和逐条解码指令。指令保留字节偏移、token 与实际目标程序集；比较使用解析后的目标签名和顺序，不比较不同构建间不稳定的 token 数字。
- `checks`：分别序列化期望与实际后比较；`gaps`/`first_error` 保存缺口。`metadata_matches_expected_only` 只表示这次采集的元数据对照一致；`mismatch` 或 `gap` 返回 2。正常结束返回 0 仍不代表获批/ABI 正确/E2 完成。

IL 解码只接收本区块用到的有限指令集；短/长参数及局部变量指令统一成索引语义。对所有指令逐项比较，故原生 Call → 保存返回 → GetLastPInvokeError → 保存 error 以及之后的 Stobj/Ret，前后插入或删掉指令都会不匹配。类型 token 必须来自核心类型程序集；Call 目标区分本次生成类型和真实 Marshal 类型。未知 opcode、取不到 MethodBody/IL 或解析 token 失败，保留已取得的原始字节和明确缺口，然后结束本次固定元数据采集，不调用包装器、不换探针。单次固定采集最多检查 15 个声明和 3 个包装，没有运行时修复或重试。

输出 UTF-8 字节若超过 1 MiB，只保存小型 `gap` 记录，明确完整观察未保存，不伪装完整成果。文件系统拒绝写入、外部强制终止等情况可能没有完整 JSON；执行端必须记录这种缺证据失败，不能以“未发现不符”当通过。脚本不获取进程地址/函数指针，不调用任何声明的 Win32 API，生成的 Captured 方法也不被执行。

## 4. 限制、预算提案与当前阻塞

| 未来 M 的单次提案 | 边界 |
| --- | --- |
| 控制请求 / OS 实例 | 请求 1；控制 OS 实例 ≤1；目标、case、worker、evaluator 均 0 |
| 控制内存 / 总墙钟 | private 256 MiB；从外部发起控制实例前的共同 T0 到证据收尾/退出 ≤30 秒 |
| 证据 | `metadata.json` ≤1 MiB；缺失/超限/未正常收尾单列 |
| 官方/队内评价器 | E0/E1/E2 调用 0；这不表示控制启动没有资源成本 |

这些是待批准的限制，不是脚本已实现的 OS 硬限制。脚本只记录输出路径准备之后的阶段 UTC/QPC 和元数据采集结束时刻，既不含控制进程启动，也不含最后 JSON 序列化/写盘/退出；外层共同 T0 必须覆盖全程。脚本时间字段不替代外部总墙钟、实际控制 OS 计数或内存证据。

**当前运行 blocked**：尚无本次固定执行端及其外部截止、256 MiB 约束/观察、超时终止与退出回读责任记录。同步反射/运行时调用或文件写入卡住时，同线程 QPC 检查不能保证硬截止；本文件没有增加这样的伪保证。执行前队长需另行闭合上述责任、固定命令与身份并明确运行许可；做不到就继续 blocked，不为凑预算新造执行框架。S 及 Create 成功至 Assign 之间未归属目标回收不在此提交范围。

原 48b 窗口、8 潜在额度、旧 15/余 2、旧 T0 继续封存；不重试旧窗口，不修改批准模板开关。Atlas 的 E2 状态由队长维护，本 session 不签写。

## 5. 可判定验收条件与实际静态检查

未来 M 需独立满足以下三项；本次均不声称已运行满足：

1. 实际环境为 Windows x64，IntPtr.Size=8；声明方法集合恰为固定 15 原生方法 + 3 包装，15 项实际 DllImport 的库/六字段、签名、方法与实现标志均与独立期望一致。缺少或多出方法也不通过。
2. 3 包装返回 void、参数为原签名加 object[]，4 个未 pinned 局部类型与索引、无异常区域、InitLocals，以及全部解码 IL 语义顺序吻合；原始 IL 可读且 token 可解析。未知、不支持或不符均以缺口/差异保存，不能以未执行 API 代替这一核对。
3. 外部证据把批准身份、唯一控制请求、实际 OS 实例、共同 T0/退出及资源约束与该 JSON 绑定；运行未越界、证据完整。脚本 JSON 自报计数或返回 0 本身不满足此项。

本次实际检查只包括：文本/来源字节对比、独立期望行与 6f 的 15 声明逐项对照、PowerShell Parser/AST、局部文件 JSON/hash、diff 与文件卫生。静态检查具体值和工具版本记录在 `M_SOURCES.json`。没有执行新脚本或其函数，没有生成类型、反射实际生成元数据、编译、`--help`、测试或启动控制/目标/worker/evaluator；没有 E0/E1/E2 调用。

尚未验证：脚本真实绑定/序列化/错误处理、动态类型生成、伪自定义 DllImport 读取、MethodBody/ResolveToken 支持情况、IL 解码器自身在该运行时的行为、ABI 和原生调用、内存/耗时/退出。Parser/AST 通过不能把这些转为已证。Actions 按免费策略停用；本次未启用、触发或重跑。

反射 API 语义参考 Microsoft Learn：[GetMethodBody](https://learn.microsoft.com/en-us/dotnet/api/system.reflection.methodbase.getmethodbody?view=net-10.0)、[ResolveMethod](https://learn.microsoft.com/en-us/dotnet/api/system.reflection.module.resolvemethod?view=net-10.0)。文档接口存在不保证本机动态模块支持；不支持即记缺口。

## 6. 时间、官方目标与交接

实际静态准备 T0：`2026-09-24T10:28:25.0151469Z`，QPC `555134914644`，frequency `10000000`。本次约 30 分钟检查点：`2026-09-24T10:58:25.0151469Z`；不重置时钟，提交固定小增量后停。最终固定提交、Draft PR 和实际检查/回读时刻回填原 Issue 15。

已读公共资料版本 `5c8c8011e5985fdd6abb1ddfde0a267bd7e2ebb1` 的 `docs/a/OFFICIAL_OBJECTIVES.md` 与 `docs/GITHUB_FREE_COLLABORATION.md`，实现基线仍为 6f。本项目首要是合法方案经未改 E0 得到更低 Makespan（模拟 cycles），另报 DDR 字节/P3 字节命中率；完整求解端到端墙钟另列，不能混成一个加速比。5～10 分钟来自第 5 页脚注 1、直接修饰 P1，是推荐而非淘汰线/最低运行时间；限制次数不自动使暴力迭代符合题意。E1/E2 工程门槛仍在，但评估器快 20 倍不能抵消方案质量下降或完整求解超预算。团队还要比较同质量更快、同时间更优的质量—耗时 Pareto、冷启动/尾延迟及资源；“已低于 10 分钟”不是效率研发完成。

本任务只服务于后续可信验证的入口定位，不产生方案质量、求解提速或硬件收益证据，不因目标更正扩预算或启动暂停任务。未导入 Q2/其他专项历史、未接手其写范围。协调者只复核这个新增入口及其与 6f 的一致性，后续是否运行由队长另定。
