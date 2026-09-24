# Windows CLI 入口：三处最小静态修订

## 1. 目标、授权与实际接手

本版只静态处理互操作声明、即时错误捕获、失败清理计数；**不是203根因结论、运行批准或E2终验**。队长指令：[5807884960](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5807884960)（NikolaStarx / 120649042）；协调诊断：[5807750597](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5807750597)（yuanzhifang30-sudo / 281850557），均全文读取并核对实际作者。

执行会话：yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce。实际接手UTC **2026-09-24T04:54:44.8333134Z**；约30分钟内交固定检查点后停。起始HEAD5ff92f36851b89ebb9278b2fdff6dc762bc0060e，工作树干净；PR70远端仍48b12684，无未提交内容需要搬移、未发现代码写范围冲突。由原作者单写launch_once.ps1，协调只复核。没有本阶段启动的作业；旧窗口的root Active/进程数缺口仍unknown，没有额外探针补证。

## 2. 固定基线与保留边界

独立分支codex/e2-interop-static-yuanzhifang，从48b12684d1273515f34ddcb2c347690cffea566f建立；Draft PR base为核实后的codex/e2-cli-driver-prep-yuanzhifang。保留PR74/5ff92f36失败证据与全部Git历史，无force-push或重写。旧48b准备说明可在[固定版本](https://github.com/huaweibei123/huaweicup2026/tree/48b12684d1273515f34ddcb2c347690cffea566f/research/a/review/e2_cli_fix_validation_20260924)复核，不把旧静态检查重新算成本阶段实测。

仅修改本目录launch_once.ps1及必要sources/STATIC_CHECKS/本说明。controller、bootstrap、seam、fixture、win_support、gate原语、生产helper a21f、矩阵/输入、contract与批准模板均不改。模板approved/execution_enabled/runtime_review_closed继续false，旧外部批准也不适用于新commit/hash。48b唯一窗口及8潜在额度、旧15/余2/旧T0继续封存。

## 3. 三点对应与实现全文

完整实现入口为同目录[launch_once.ps1](launch_once.ps1)，不另造监督器或进程层。

| 要求 | 静态实现 |
| --- | --- |
| 单一声明路径 | 15项原生方法均只经DefineMethod + 一次完整DllImportAttribute；不调用DefinePInvokeMethod。六个具名字段为EntryPoint=原生名、CharSet.Unicode、CallingConvention.Winapi、SetLastError=true、ExactSpelling=true、PreserveSig=true。不存在第二条P/Invoke map定义路径。 |
| 同一托管包装捕获 | 三个Captured方法沿已有Reflection.Emit生成短IL。顺序是加载参数→原生Call→Stloc结果→Call GetLastPInvokeError→Stloc错误，捕获后直接写入调用前已分配的全新类型数组槽，返回void。包装器在原生调用前校验carrier、数组类型与下标并保留托管byref；原生调用后不再Newarr/Box/Unbox。调用方保有carrier，catch据保存值恢复Job或PROCESS_INFORMATION句柄；部分预分配失败尚未产生资源，直接跳过恢复。原生返回与错误读取之间没有PowerShell绑定、日志、分配或另一原生调用。CreateJob/Object碰撞和CreateProcess结果均用此保存值，不在PowerShell调用边界后重新取错误。 |
| Assign前失败计数 | 只有非零Job句柄且同包装捕获error=0才标为本次独占创建；error183仅关闭本次打开的句柄、不终止/查询碰撞Job，其他非零错误也不能确认独占。48字节会计buffer移到Job创建前分配。失败清理在独占Job/有效buffer条件下查询，不再要求Assigned；同包装保存Query结果/错误、真实Active/Total和QPC。 |

CreateProcess返回成功时先接管PROCESS_INFORMATION中的进程/线程句柄，再记录与传播结果；CREATE_SUSPENDED|CREATE_NO_WINDOW、非继承句柄、NULL环境、先Assign再唯一Resume的顺序保持。新增error=0独占条件是保守准入，不能将未知成功状态当成自己的Job。

捕获范围严格区分：**CreateJobObjectW、CreateProcessW，以及失败清理使用的QueryInformationJobObjectCaptured**具有保存的(result,error)；正常路径的Query与其余原生调用仍沿原调用/失败传播，只判断既有返回值，没有经验证的即时error。E2-Check在未提供捕获值时明确报native error not captured；CloseHandle失败记录operation/error=null/error_capture=not_wrapped，仍进入close_errors并使最终失败，绝不把迟读缓存当原生错误。没有声称全体15项调用均已即时捕获。

失败查询受原min(670,Tfailure+10)边界限制，循环进入前检查截止，不新增清理额度。每次查询先将当前结果/计数置unknown；BOOL失败保留捕获error、计数null，托管异常保留exception/unknown且不覆盖最初失败。成功才读取buffer。cleanup_root_query是当前查询记录；cleanup_root_last_success保留此前真实成功快照，root_cumulative_before_cleanup仅保留清理前已观察值，不混为最终清理计数。无有效独占Job/buffer或查询前已超时则记录跳过原因，不填0。若最后一次成功样本Active>0，随后Sleep跨过截止，该带QPC样本仍保留；它不是截止时已清零的证明。只有实际成功查询到Active=0才具有对应时刻的清零证据。

## 4. 本阶段验证与未证事项

只作文本审阅、PowerShell Parser/AST、JSON/hash和diff；没有dot-source脚本、调用Add-E2Native/CreateType、执行生成的IL或反射实际运行元数据。**驱动/目标import、执行、--help、编译、控制/目标探针、测试、worker、E0/E1/E2全部0**。没有扫描698项workspace或5485项environment库存，也没有重做PR74脱敏。

sources仅更新launch_once.ps1的driver hash、改变文件的workspace hash和派生bundle；其余项从48b保留，JSON清单相等不等于重新核验磁盘库存。STATIC_CHECKS记录本轮检查与此前检查的固定出处。只有这份PS源的静态解析是新的，不把旧7份Python AST当成本轮执行。

实际生效DllImport元数据、IL生成/装载/调用、BOOL和IntPtr封送、GetLastPInvokeError对、Windows API行为、碰撞与失败清理、实际内存/峰值/耗时均未验证。203真实原因与旧窗口缺失Active=0继续unknown；静态提案不补旧证据。无新增C#编译器/Add-Type、新外部启动器或通用追踪框架。

## 5. 保留约束与验收

资源、输入及顺序不变：15例/8潜在E0/43矩阵Python逻辑请求、parent1、pool/formal/debug0；case active14/Job2GiB/process512MiB，root active17/2.25GiB，controller256MiB、available≥3GiB；逐case6/9/12、总123/controller3/root126。上述均保持契约值，不是本阶段用量。

共同运行T0的90/660/670/1200/1500/1800、每例35/3/10、首个意外失败停止且不重试，均未改。Q2、LYX/E1、POSIX、其他算法与Actions不扩展，无Atlas签写或doing/done声明。此次静态任务的接手时钟独立标注，不重置任何旧运行时钟。

本阶段交付以固定增量可审查、来源一致、越界改动为0和明确未证范围为准，不以Parser成功代替运行验收。

## 6. 最小下一证据建议与停止

交协调复审本增量后停。若队长今后另行明确授权，先限定核对实际生成的六项声明字段/位数，以及一个固定最小启动或失败路径的BOOL/error对、独占Job计数与句柄退出证据；原始输出也应按要求留存。具体范围/次数/资源须另定，本说明不授权元数据探针或整套15例重跑，不复用旧额度。进入控制器后才有条件讨论CLI功能验证。
