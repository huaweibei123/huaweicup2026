# Stage J：完整链源核错峰的三次证伪

执行会话：yuanzhifang30-sudo/s-0e91469d5b284a0aaf7aca42c456233c（continue，新独立写范围）。Pro R3 最终回答消息 `c15ac558-dd1d-4631-ae9b-5865b933f683` 是研究假说来源，完整网页原文由父 P1 会话归档；本卡不把模型计算提升为官方成绩。

1. **任务目标**：针对严格 24 轮、每轮 12 条四节点 PIPE_V 链与 11 ADD 二元归约的图，作 051/k3/control、051/k3/paced、051/k4/paced 三格固定证伪。k3 的两格是同链到核分配、同图/配置的因果配对；k4 只能与已有旧方案作迁移对比。本入口不按 case ID 构造，case 051 仅在 runner 中固定实验样本。
2. **输入文件**：只读外部 `GRAPH_DIR/case_051.json`，仓库固定 config、未修改官方 E0。来源 manifest 必须证明图、配置与官方代码哈希；构造和 runner 分别固定完整源码提交。原图不复制或修改。
3. **输出要求**：每格独立两字段方案、诊断、原始完整 E0 result/trace/log、solver/E0 stdout/stderr、run.json；批次 manifest、receipt 与控制/错峰链到核相等检查。外层完整冷 solver 墙钟与外部 E0 墙钟分列，不拿构造函数时间代替。失败与超时保存原件和调用账。
4. **限制条件**：control 每轮每核完整 chain bin 一个 Task，尾部 11 ADD 单独在 core0；paced 仅从第二轮开始，将 core0 的 4 条或 3 条完整链拆为最前 1 条和其余一组两个 Task，分别 phase0/1，其他核 phase0，尾 phase2。链内部不切，原有链到核分配不变。严格结构守卫不适用即报 Unsupported，不回退别的算法。最多 3 冷 solver、3 外部 E0、0 E1/E2、0 重试；2 cell worker，每 solver 30 秒、E0 60 秒、全批 180 秒。Windows Job 仅清理本批进程树，身份/监督故障停止后续派发。执行需父 P1 监督会话在固定预算和同机协调下发 START，实际执行会话传自身 session 地址；这不是重新请求用户实验授权。
5. **验收标准**：准备期仅源码、语法、只读来源预检及少量合成结构测试；0 真实图 solver/Task 编译/E0/E1。正式运行后核链完整、官方 `derive_multicore_plan`/`validate_task_order`、Task 与 core 联合边严格按 `(stage,phase)` 增、两字段计划、三格官方原件与容量/依赖合法性。任何失败或退化保留。Pro 有理数模型 k3 12168→11621、k4 10619→30566/3，只忽略小 COPY/MEM，不是 E0 上下界或改善保证；k2/k5 模型反而退化，本批不测。预计控制 k3 96 Task、paced k3 119、paced k4 143；原始 288 个 32KiB COPY 预计不变、稳态可能增加 23×2B 根 COPY_IN，均待 E0 核查。源核拖慢可吞没门控收益，按 `min(Δ,S-d)` 仅作简化模型提醒。
6. **截止时间**：本次先交可执行冻结三试和测试证据；真实 START 与结果验收另由父 P1 监督会话安排。

准备期命令：`python -m unittest discover -s tests/q1_yuanzhifang -v`、`python -m src.q1_yuanzhifang.benchmark_j --graphs GRAPH_DIR --preflight`。获得固定 START 后：`python -m src.q1_yuanzhifang.benchmark_j --graphs GRAPH_DIR --start-token STAGE-J-20260925-START --producer-session LOGIN/s-UUID`。

Job 监督工具从本线先前 Stage I 固定 `7993bafe22cbdbcd9ebc12b15dfecd4ef651563b:src/q1_yuanzhifang/benchmark_i.py` 提取，在此仅复用 Windows Job 进程管理，不引入 Stage I 算法或成绩。H 严格守卫来源为 `b93c3135d6678afa1814e12349e111c02e4f6d78:src/q1_yuanzhifang/star_frontier.py`。父工作树 Python 解释器仅是本地测试依赖，不写入源码路径。
