# P1 Stage F：星式切链单例证伪

负责人：@yuanzhifang30-sudo；实测 session `yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117`。
分支：`codex/q1-wave-benchmark-yuanzhifang-20260924`。沟通：[Issue #98](https://github.com/huaweibei123/huaweicup2026/issues/98)，由父研究会话汇总外发。

1. **任务目标**：仅真实 051/k5，对固定结构守卫星式构造做一次最小 E0 证伪；比较已有 Stage C 051/k5 的 253856 周期，不重跑旧方法。方案质量看官方 Makespan 与额外 DDR；求解效率单列完整冷进程墙钟，外部 E0 另列。R=166540 为抽象模型值，不是 E0 预测或结果。
2. **输入文件**：作者完整固定 `916a19e57c041ca5dc4aa1f3748e23726464b762`，`src/q1_yuanzhifang/star_frontier.py` 及 construct/fork_frontier/diagnose 依赖；冻结十个官方源；官方 `case_051.json` SHA-256 `884e8b12ac1f7a9b569958909680e8c2f6055966a59c9f929ffd5cee48aae43b`；固定 config SHA-256 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。旧 C 原件固定 `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a`；全部是暴露过的研发数据，无盲测声明。
3. **输出要求**：仅写 `benchmark_f.py`、`export_f.py`、本任务卡及 `results/a/q1-yuanzhifang/stage-f-20260925/`。独立 `run/` 保存 protocol/events/调用账本、官方两字段 plan、diagnostics、完整 result/trace/log 与所有 stdout/stderr/run；大 JSON 无损 gzip。导出比较 CSV、静态重复输入/分区/溢出 DDR 分析及 `board-submission-v1`。所有原件固定同一 Git 提交后做成绩台预检，不直接写中央服务。
4. **限制条件**：新预算严格最多 1 冷 solver + 1 未修改外部 E0；1 worker，solver 30 秒、E0 90 秒、全批 180 秒、0 retry/E1/E2。首例须留 125 秒预算；冷进程计启动、导入、读图/配置、结构守卫、构造、结构合法检查、诊断和方案写出至退出。solver 不调用内部评分或 Task 编译。外部 E0 承担实际依赖/核序/容量最终检查。solver 输出必须确认为 star/263 Tasks/R166540，否则身份异常停批，不评分。源/输入/监督/磁盘异常停批，所有失败保留，不修改作者或官方文件；不得追加用例、重跑旧单核或将旧批剩余额度挪用。
5. **验收标准**：准备期 0 solver/E0、0 全图扫描；十源码与输入原字节哈希、作者依赖固定 Git 字节、已有 C 同身份原件通过预检；runner 提交后交父审阅，明确 START 和协调窗口才执行。所有计划字段合法，成功必须有完整 E0 原件。报告实际 T0/T1、calls、两种 wall、Makespan/DDR、全部失败与负结果；重复输入统计只描述静态 Task 边界加载，不能冒充 DDR 排队因果。网站格式通过、原件一致、独立复跑与科学验收分别说明。
6. **截止时间**：北京时间 2026-09-25 按父会话协调窗口执行；当前 E4 在途，其后 P2 C 优先。本卡只准备单格，未获明确 START 不启动评分，不占他人窗口。

## 复现入口与状态

默认只读预检：`python -X utf8 -B src/q1_yuanzhifang/benchmark_f.py --graphs GRAPH_DIR`。
授权 START 后：在同命令追加 `--execute --window-token PARENT_START_REFERENCE`。
导出：`python -X utf8 -B src/q1_yuanzhifang/export_f.py --graphs GRAPH_DIR --output results/a/q1-yuanzhifang/stage-f-20260925/board-feed-UTC-stage-f.json`。
预检：`python -X utf8 -B src/benchmark_board/protocol.py FEED --submission`，另按同工具固定 Git 参数验证提交原件。

复用本 session 已 `uv sync --locked` 的独立环境，锁文件哈希在运行环境记录；不重复安装、不新增训练或预计算。已有父单元测试/守卫和 Pro 理论咨询属于研发成本，不能算冷 solver 性能。官方 5–10 分钟为效率建议，不是 600 秒淘汰线；本轮 30/90/180 秒是自行冻结的实验预算，不是原题门槛。

准备状态：尚未启动真实求解或评分；实际源码校验与预算记录见该批 `preparation-checks.json`。结果、PR 和是否上台均待实际交付，不能由本任务卡代签。

## 实际交付追加（原准备记录保留）

父随后明确共享资源 START；P1 E4已结束，P2可最多2worker共享，本批固定1worker。实际runner `2b79198675838415baee96ccca64e81067ff6781`，作者不变。批次T0/T1为 `2026-09-24T17:16:28.123478Z` / `17:16:31.674371Z`；1solver+1E0均ok、0retry/E1/E2。E0=325520，比C退化28.2302%；cold solver=1.2007275s，独立E0=2.0575621s。新增6160476B分区搬运，spill0；本固定分区的DDR字节必要界259985已超过C完整253856，不追加评分。

原件、标准feed、预检和完整限制见 `results/a/q1-yuanzhifang/stage-f-20260925/README.md` 及 `REPORT.md`。当前仅本地生产方预检通过，维护接收/上台/独立复跑没有代签。
