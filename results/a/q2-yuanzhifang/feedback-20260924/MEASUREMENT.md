# 本轮 P2 测量与成绩台导出

执行子 agent 只维护 `src/q2/feedback/measure.py`、`export_board.py` 及本目录测量说明；构造、算法判断、任务通信与提交由父会话 `yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24` 统一负责。此执行子任务不另建远程身份，不写中央成绩台或 Atlas，不自行调用旧预算。

已按本工作区 base `45f647b` 阅读 AGENTS、README、TEAM、SESSION_PROTOCOL、ROUND1、SYNC_UPDATE、Q2-CORE-SEARCH、OFFICIAL_OBJECTIVES 和成绩台入口/统一交付协议/schema/example；Team Mailbox Skill 已读，完整抓取由父会话集中完成，本子任务未重复抓取或发外部消息。该阅读声明不表示已读账号全部历史或所有 Pro 原文。

## 运行方式

固定算法、runner、E0 SHA 和批次 spec 由父会话冻结后执行：

```powershell
.venv/Scripts/python.exe -X utf8 -B -m src.q2.feedback.measure --spec <仓库相对spec路径> --check-only
.venv/Scripts/python.exe -X utf8 -B -m src.q2.feedback.measure --spec <同一spec路径>
.venv/Scripts/python.exe -X utf8 -B -m src.q2.feedback.export_board --batch <spec中的output目录>
```

`--check-only` 只核 spec、实际源码与 Git 字节、官方源码/config/选中图哈希，0 solver/E0/E1/E2。普通运行拒绝已经存在的输出目录，无自动续跑、重试或新批次预算重置。导出生成新的带 UTC 时间 feed 与独立预检回执，调用现有 `protocol.py --submission`，不联网、不写中央库、不执行评价器。

固定比较顺序：008、095、084、044、080；每图依次 component、affine_eighth、resource_word、pipe_window；全部 4 核、1 个 worker。spec 预注册 resource_word 对 044/080 不支持；只有对应单元返回 2 且 stdout 明确为 `status=unsupported` 才记录零 E0 并继续。其他非零退出、异常、超时或原件不一致首停，不将不支持当成功或非法。

父会话限定本轮最多 20 solver / 20 E0，预期 2 个不支持故最多 18 E0；每个 solver 和每个独立 E0 各 30 秒，整批预算窗口 600 秒，预留末 15 秒收尾。派发前把相应调用和时间上限原子写入 ledger 并 fsync，确认完整单元及收尾储备足够后才运行。启动失败记录未实际启动并撤销该次实际调用计数；崩溃造成的在途预留保持保守计费，禁止重试。实际停止原因与未启动单元可从 spec/ledger 对照。

## 时间、资源与证据

- 首要质量指标是未修改官方 E0 的 Makespan（模拟 cycles），同时保存官方 scheduled/added/spill 字节。真实求解墙钟、独立 E0 墙钟和批次开销分开；不把 E0 吞吐或事后最优组合当作完整 solver 提速。
- solver 墙钟从新 Python 子进程启动前至退出，包含读图、COPY 收缩/索引、构造、官方结构检查、最终两字段 plan 写出。外层包括观察进程及派发后 ledger fsync 的保守开销，并非纯 CPU 时间。每次新进程属进程冷启动；没有清空 OS/文件缓存，不声称磁盘冷启动。
- E0 在 solver 退出后单独启动官方 problem_2 CLI；其 imports、graph/plan/config 读取、评价、完整 result/trace/log 写入与退出都计入独立评价秒数，`solver_includes_evaluation=false`。
- 固定 spec/Git/原件哈希预检在批次预算 T0 前进行，单列 ledger.preparation 的 UTC、墙钟与范围；不称为计入 solver 的在线图预处理。批次窗口另包含记录、压缩、派发间哈希核对等成本，不把这些隐去或冒称 solver 内核时间。
- 执行时读取真实 OS、CPU、RAM、Python 和 uv.lock 哈希。CPU-only，workers=1，配置 OMP/OPENBLAS/MKL threads=1；此数字是执行配置，不是 OS 实际线程数测量。未监控严格 peak RSS，字段为 null 并解释；没有声称受硬 RAM 上限保护。
- 原始 result/trace 进行可逆 gzip（mtime=0），验证解压一致再保留压缩原件，收据同时记录 raw/stored 哈希和大小；原始 stdout/stderr/官方文本日志保存为 `.txt`，避开全局 `.log` 忽略规则。本目录 `.gitattributes` 保留全部证据字节。
- 成绩台 feed 成功行引用 plan/result/run 及 trace/log/ledger；失败与不支持继续留存。复用同冻结身份的官方单核 100 例原件，不新跑分母。feed 保留各方法独立 run，不声称事后比较是在线选择器。
- 本轮本机进程不创建付费云计算、GitHub Actions 或后台服务；模型账户用量不由实验 runner 测量。依赖安装、开发结构扫描/测试成本由父会话独立记录在冻结 spec 的 offline_costs。

官方 5–10 分钟是问题 1 脚注的效率建议，团队沿用到 P2，并非 Makespan、600 秒淘汰线或至少运行 5 分钟。本轮 600 秒只是明确实验预算。有限固定比较不自动证明算法有效；需看同条件质量—耗时与退化，局部开发样本不代表全 100 图、1–5 核完成。

预检通过只证明格式与现有原件一致；Git 交付、实际接收、页面可见、独立复跑及算法验收各自记录，由父会话统一对外沟通。

## 实现检查（2026-09-24，正式批次前）

两个入口 `--help` 与 AST 语法解析通过。临时目录及 mock Popen 的 5 项检查通过：正常退出、非零退出、超时 kill/wait、启动失败不记为实际调用、失败对象内未知字段原因。前四项均检查派发前已持久保存 reservation/call、完成后 run/ledger 一致；没有运行真实 solver 或 E0。`git diff --check` 通过。正式 source SHA 尚须父会话冻结后再用 `--check-only` 核对；成功结果和提交后 Git 原件哈希/成绩台准入需正式批次完成才可验证，不由上述单元检查代替。
