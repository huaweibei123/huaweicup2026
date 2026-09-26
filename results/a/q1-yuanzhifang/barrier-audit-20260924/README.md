# P1 全屏障下界独立审计（零评分）

## 1. 任务与结论

专项 session `yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117`，沿 Issue #98 的父任务工作；本审计未发 Issue、未向中央成绩台提交。审阅作者固定 `f16746ff2ab112ae8e802711e90d74829c419eb9` 的 `barrier_bound.py` / `BARRIER_BOUND.md`，不修改作者代码或证明。

在冻结 P1 语义下，未发现窗口推导的明显漏洞。复算 100 图 × 1–5 核共 500 个下界；已有 A/B/C/D 的 60 条成功多核记录和 100 条官方单核记录全部满足 `lower_bound <= E0 Makespan`。A/B/C/D 共 61 次尝试中的唯一失败，即 C 阶段 016 的 bounded baseline E0 超时，继续作为非数值失败保留。没有补跑或虚构该成绩。

有限反例搜索包含 80,640 个两 Pipe、两核的操作级放松调度，未发现违反。这里的枚举是理论审计，不是方案求解器；它和既有成绩一致性都不能替代一般证明，也不证明下界可达。

## 2. 输入、来源与身份

- 作者源码、构造依赖与证明固定于 `f16746ff2ab112ae8e802711e90d74829c419eb9`；十个官方源码逐文件验原始字节及 manifest 哈希。官方组合 hash 为 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。
- 100 图和固定 config 均从已核官方数据只读读取；配置原始 SHA-256 为 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。最终续接直接调用冻结官方 `read_scene_a_config`，跨核等待确认为 1000。
- 既有多核 feed 的 Git 原件提交分别为 A `9b07b791cbbb950410d56d2c8c02407fde013982`、B `0441891f60b07a456a0f21ed74a024987edd8cd9`、C `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a`、D `a7f51f2d5ca7d735899addd8bc14900045484fc3`。单核 run/result 取自作者固定提交中的既有 `official-singlecore-20260924`。
- 校验四个 feed、计划身份、结果的 scene/core/Makespan、artifact SHA-256、gzip 解压原始 SHA-256。`verification.json` 收录 563 次 artifact 引用检查，去重后 506 个固定提交/路径；四个 feed 自身另列。
- 清单和 100 个单核 `run.json` 的本地副本有 Git autocrlf 转换；读取权威 Git blob，逐项记录本地与 Git hash，并严格证明差异仅 CRLF。没有对官方源码、graph、config、plan 或 result 字节作归一化。

## 3. 独立推导审阅

完整推导见 [review.md](review.md)。关键结论是：只要保留计算路径确实存在，端点异核必经至少一次真实跨核 Task 边，故至少有一次 δ 延迟。任意 Task 跨越屏障不破坏此必要条件。全分量可比较屏障把工作划入实际互不重叠的区间；同一核同一 Pipe 的段内工作不得超过其可用窗口。

两端屏障异核的容量不超过同核情况，因此未知分配仍可用 `W <= D + (k-1) max(D-2δ,0)`。单端改为 δ；无端点改为 kD。不同 Pipe 取最大、不同弱分量取最大，空段不增等待。不能把任意 fork 阶段当成屏障，不能收缩已删除 COPY 桥后套用此证明。

## 4. 结果与对后续构造的意义

| 图 | k=1 | k=2 | k=3 | k=4 | k=5 |
|---|---:|---:|---:|---:|---:|
| 051 | 607080 | 327196 | 233909 | 187266 | 159280 |
| 024 | 2554795 | 1378554 | 986507 | 790484 | 672870 |

多核最小余量为 A/001 的 784 周期（58984 − 58200），单核最小余量为 029 的 70 周期（37555 − 37485）。051 的 C 构造在 k=2/3/4/5 下的上界/下界分别为 1.0940、1.2450、1.3580、1.5938。k=5 平台没有被此必要下界解释为不可避免；也不能由该差距推出全部周期都能改善。后续应继续结合 C 轨迹中重复边界输入、DDR 排队和原子支路负载去设计，不能直接把下界当目标调度或收益预测。

## 5. 实际执行、失败与资源

全程单进程串行，新增 solver/E0/E1/E2/Task compiler 调用均为 0。此前全100复算等到 P2 实际 T1 `2026-09-24T16:25:57.614282Z` 后才开始。共有两个预检失败、一个全量计算之后的证据读取失败；详见 [preparation-failures.json](preparation-failures.json)，均为自有审计代码的输入处理错误，不是作者定理反例。

首次完整计算的固定代码为 `29eaa4e3fdae2997976a34ecce5cf531ca2cee2c`。异常前未把进程 T0/T1 持久化，不能声称有精确完整墙钟。可核实的文件系统时间为输出目录创建 `16:32:54.6184945Z`、合成检查落盘 `16:32:55.2221165Z`、500 界完成写入 `16:33:29.7218343Z`；这约 35.10334 秒只是该区间的时间，不包括之后证据读取，也不是冷进程端到端。至 `16:34:08.7890179Z` 已观察确认审计进程退出并向父释放窗口，该时刻不是精确退出时间。

固定 `e1d7034535bc27cdd5bbb588c87f70ca11c9b739` 只续接已有两份原字节产物并验证 hash，未重跑 500 界或合成枚举。证据续接 T0 `16:35:51.257171Z`、T1 `16:35:59.381101Z`、内部墙钟 8.1240165 秒；这是审计记录整合耗时，不是算法求解速度。另两次预检的工具已报用时为 2.595 秒与 5.898111 秒；未记录的编辑/排查耗时未估造，也未将失败成本隐藏成一条无中断成功运行。

Windows 的 `dot_clean` 不可用；交付前只扫描本目录的 `._*`、`.DS_Store`、`__MACOSX`。依赖使用本 session 已 `uv sync --locked` 的环境。不存在独占硬件性能声明。

## 6. 交付与复现

- [full/verification.json](full/verification.json)：来源、哈希、调用账本与比较结果。
- [full/comparisons.csv](full/comparisons.csv) / [full/comparisons.json](full/comparisons.json)：160 条逐例比较；[full/failed-attempts.json](full/failed-attempts.json) 保存超时。
- [full/bounds-100x5.json.gz](full/bounds-100x5.json.gz)：500 界的完整紧凑报告，含每个完整可重算下界 JSON 的 hash；无损封装见 [packaging.json](packaging.json)。未压缩中间文件保留本地、仅该路径被本目录 `.gitignore` 排除。
- [full/synthetic-checks.json](full/synthetic-checks.json)：3690 个逆容量算术检查、1600 个端核容量比较、边界案例及 80640 个放松调度。

在不含本输出目录的新隔离 checkout 使用固定 `e1d7034535bc27cdd5bbb588c87f70ca11c9b739` 复现（GRAPH_DIR 指向已核官方 data 目录）：

```text
uv sync --locked
python -X utf8 -B src/q1_yuanzhifang/audit_barrier.py --full --graphs GRAPH_DIR
```

该命令拒绝覆盖输出；会重新进行零评分理论复算，仍应协调本机资源。历史续接命令加 `--resume-existing`，严格要求仅存在原始 `bounds-100x5.json` 与 `synthetic-checks.json` 且 hash 相符。已封存目录不应再次执行此模式。此批不产生 board feed，不能当作新增方案成绩。
