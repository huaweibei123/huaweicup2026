# Windows CLI 单次验证：控制器创建失败，窗口封存

**结论：本次验证失败，15例均未准入，不能判断生产CLI修复是否有效，也不能据此验收E2。** 固定驱动在创建悬挂控制器处报告 `Create suspended controller failed: 203`，4.7239312秒后停止。203仅为原样记录的错误值，根因未知；本轮没有修改代码、重试入口或追加探针。

负责人：@yuanzhifang30-sudo；session：`yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce`。
结果分支：`codex/e2-cli-window-48b1268-results-yuanzhifang`。

## 1. 任务目标

在既定15例矩阵中验证Windows full CLI的等待/退出传播、命令行和IO、启动失败、取消清理，以及P2/P3有效/无效输入的direct/adapter输出一致性。本次只到外层启动阶段，未得到这些功能的运行结论。

批准：[5807193465](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5807193465)。入口前元数据类型误比较的停止记录：[5807241056](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5807241056)；明确允许完成批准材料后使用原唯一入口的裁定：[5807272182](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5807272182)。这个纠正不是新增窗口或额度，也不是入口重试。

## 2. 固定输入与源代码

- driver：48b12684d1273515f34ddcb2c347690cffea566f / Draft PR70；本结果分支从该提交建立，源文件未改。
- production helper：a21f7ef7111933d309f3d616b9a3f2e7e861129d；plan：53c151ecaef2636bcf0eb1946c112f19f8cec739；小合成输入与官方配置沿固定计划。
- driver bundle：afbaa8d7b13e735f35702caf70e382310550989bcc5f027a0762c12cd51534ef。
- sources：7905a556a405013bea6aa59d0986cdd2dd6452ee0ee401726a88dc8d78ee8880；STATIC_CHECKS：72b34138602f4c078299aad5035894f7574f535e19430a753e21252265f5a4fe。
- 批准index：8171b596168e3edf83305b75135eb7b14a3315ea50eca1361f5e59005a8d6f31；外层原记录一致。运行前未用git刷新index。建立结果分支发生在入口结束、既存清理记录核对之后。
- 只有仓库外批准JSON三开关true；固定仓库模板false。全部limits原值复制，批准JSON解析及字段核对通过。

## 3. 输出与实际结果

真实脚本T0为 `2026-09-24T03:55:48.8614204+00:00`，QPC `319618095358`，频率 `10000000`。驱动结束QPC `319665334670`、UTC `03:55:53.5890635`，耗时4.7239312秒；宿主finally记录4.7439562秒。**这些是运行阶段结束时间，不是整窗交付完成时间。** 后续归档/发布继续沿同一QPC/T0计时，见archive_clock及后续publication_receipt。

| 观察项 | 结论 |
| --- | --- |
| 固定入口调用 | 1次，同一已有PowerShell宿主直接dot-source固定脚本，未加额外启动器 |
| controller创建请求 | 1次；记录错误203；没有取得controller句柄，未完成assign/resume/独立准入 |
| 成功OS进程数、controller PID/FILETIME | unknown；无成功创建/退出观察原件，不用请求数或空列表推成实测0 |
| case准入记录 | 0；无cases、ledger、controller boot/ACK或final.accounting；15例全部未准入/未验证 |
| 环境检查 | 外层698项工作区等固定身份检查后进入CreateProcess；controller的5485项环境预检尚未完成 |
| 根Job | 已创建；TerminateJobObject记录true，close_errors=[]；缺少累计OS数和最终ActiveProcesses记录 |
| 完整清理证明 | 不成立；终止返回true不能单独证明Active=0，不追加控制进程/探针补证 |
| 宿主工具退出码 | 0；与驱动status=stopped并存，不作为通过依据 |
| E0费用/进入次数 | 允许上限8保持封存；实际函数进入次数unknown，确认完成0，不退款、不另行复用额度 |

不把拟议active/内存/累计进程上限记作实测峰值。原始控制目录和运行目录共13个源文件全部映射：9个逐字节相同，4个必要脱敏派生。manifest逐文件列原/公开SHA256、长度、变换类别；redaction_policy说明字节替换，cleartext映射留在仓库外。没有删行、归一化换行或把脱敏文件称原字节。原件CRLF及transcript尾部空格会触发默认diff空白提示，因此不改证据字节；自编说明用默认空白检查，证据区允许原CRLF/尾空白并另做逐字节hash核对。

保留外部批准、批准/裁定/入口前错误、完整PowerShell transcript、outer全部字段、宿主finally及工具返回记录。工具只给合并Unicode输出，已保留其原始返回文本；**没有分别捕获原生stdout/stderr字节流**，不能伪造两个空流或称流分离完整。case stdout/stderr/JSON/Trace/log因未准入而不存在，逐项缺口见summary。

## 4. 限制与停止条件

批准上限仍为15例/8潜在E0/43矩阵Python逻辑请求、controller父启动1，case active14/Job2GiB/单进程512MiB，root active17/2.25GiB，controller监测256MiB，可用物理内存至少3GiB。逐case累计6/9/12、sum≤123、controller≤3、root≤126为政策，不是本次观测值。

入口首次实际失败后停止，无修后重跑、--help、额外目标/探针/worker/构建/安装/云执行。归档阶段的Python/Git/gh用于证据交付，其时间纳入原T0；43只表示矩阵逻辑请求，不声称涵盖整窗发布工具的所有OS创建。旧潜在15/余2/旧T0封存；Q2、LYX、POSIX、其他算法和Actions均未扩展，无Atlas签写。

## 5. 验收与未验证项

该产物只验收“首个失败后的如实封存和交付”，不验收功能修复。读取既存outer/host记录完成有限清理核对，但缺失Active=0/完整身份的部分维持unknown。未验证15例全部行为、实际OS用量、controller准入、内部父子关系、PIPE、取消、退出传播、官方输出一致性、吞吐与评分效果。不能生成论文性能数字或改善结论。

实际入口命令记录（只作追溯，禁止据此再次执行）：

```powershell
. ./research/a/review/e2_cli_fix_validation_20260924/launch_once.ps1 -ApprovalPath <PRIVATE_CONTROL>/approved-once.json -EvidenceName e2-cli-window-48b1268-20260924
```

入口前错误是批准材料JSON DateTime与字符串比较造成的误拦截；当时entry=0/T0=null，经明确裁定后才进行了本次唯一入口，历史文件中的0属于此前状态，不与实际entry=1混淆。

## 6. 截止与交接

共同T0下：准备90秒（03:57:18.861Z）、工作660秒（04:06:48.861Z）、清理670秒（04:06:58.861Z）、公开证据目标1200秒（04:15:48.861Z）、最终回执目标1500秒（04:20:48.861Z）、总窗1800秒（04:25:48.861Z）。每例35/正常收尾3/失败清理10未得到本次case级验证。

交付独立Draft结果PR，固定结果HEAD与同钟发布时间回原Issue。最终远端回读时间会写入交接记录，不能把archive_clock当最终交付时间。交付后停，等待协调核对与队长决定；不自行启动下一窗口。

公开结果：[Draft PR74](https://github.com/huaweibei123/huaweicup2026/pull/74)。首个完整证据提交e3bf41638b8c790776d6f7f483d2e697126da382，于UTC04:06:45.8831302回读远端head/base/Draft/正文一致；QPC326188334683，距原T0为657.0239325秒，满足T+1200公开目标。最终回执继续用原钟，不把此首轮回读提前称最终结束。

交付脱敏修正：协调在e3bf416/7ceb237历史中发现entry-tool-result.json的嵌套output字符串仍有临时Job标识（两层JSON转义，四反斜杠）。仅公开派生件追加一次level2精确字节替换，原件不变；manifest记录新增变换，9原字节/4派生计数保持。递归解码公开JSON中的有效嵌套JSON字符串作只读检查，未重新序列化原证据。旧Git对象仍含临时本地标识，追加修正不等于删除历史；它不是凭据或token。657.0239325秒只表示初包发布，完整脱敏修正的最终回读仍沿同一T0报告。
