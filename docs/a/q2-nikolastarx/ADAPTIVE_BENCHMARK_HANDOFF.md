# P2 adaptive direct：中央规模验证交接

算法负责人：`nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894`。接收者：中央成绩台 `s7c98`，由其统一安排 LYX/farmer。本文是固定候选与建议实验范围；没有启动新评分、占用成员机器或分配 Colab，也不向成员重复派单。

1. **任务目标**：测试一个可执行的统一结构算法，而非按 case 挑历史赢家。回答全 100 图 × 1–5 核是否合法、相对固定 Fang 与逐格历史对照的质量变化，以及同一执行机上的求解墙钟分布。识别路由的失败/退化，特别是单组件图。算法只按结构选择 resource-word / component-envelope / DAG-EFT，0 在线评价。
2. **输入身份**：算法固定 `6e5099a35300133419990bf1f44f621f98850c21`，入口 `src/q2_nikolastarx/adaptive_direct.py`；依赖同提交的 `baseline.py`、`direct.py`、`dag_direct.py`、`component_envelope.py`，以及 `docs/a/source-manifest.json` 所列未修改官方源码和输入。输入为 `data/raw/a/official/data/case_001.json` 至 `case_100.json`；逐文件 SHA-256 由 manifest 核验。官方代码集合 SHA-256 为 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，配置为 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。`uv sync --locked`，Python 3.12，环境/平台实际回报，勿复制本机 venv。冻结 `uv.lock` 与实际 runner 另记身份。
3. **输出要求**：逐格 plan、solver.json、E0 完整 result/trace/log、进程回执、哈希清单和标准 board feed；负结果同样归档。分别记解释器启动至方案落盘/退出的 solver 墙钟、观察器和清理边界、外部 E0 墙钟、Makespan、额外 DDR、spill、实际调用数/失败/资源。统计同一来源全 100 图的逐例 baseline/Makespan 算术均值及覆盖数；缺格不补成成功，不把混合历史赢家当本算法全量成绩。
4. **限制条件与建议预算**：单一候选、100 × 5 至多 500 次外部 E0，在线 E0/E1/E2 均为 0，每格求解进程建议 30 秒、外部 E0 60 秒、整个排定批次最多 7200 秒、单 worker、RSS 观察停止阈值 4 GiB、重试 0。这是本次执行建议，非题面硬限制。中央应先确认实际平台 runner、执行者/资源窗口并冻结协议，再派发；可按互斥 cell 清单拆分机器，合计不超过 500。不得把多个成员各跑全 500 当成同一预算。只给真实执行的平台记验证，不启动付费 GitHub 服务。
5. **验收与复用**：已经有 500/500 结构检查、27 个相关测试、六份旧 envelope 计划/detail 的逐字等价，均非正式全量 E0。旧 24-cell direct 数据固定 `81219bf923524fb60616e39b5ad2dced67aec3e2`，旧 6-cell envelope 数据固定 `1e92b165b8609e94191b1be8d1eab7c4f8aa5929`，中央都已接收；后者新增 6/eligible 6/baseline 6、0 拒收、6 格严格改善。可在新计划字节与 graph/config/E0 身份全匹配后引用原评分来减少重复 E0，需显式标 reused，不能伪造本轮进程/计时/平台验证。既有固定 Fang 对照为 `0b58c123cccf02fc993b741d79dcd8511e4dd38f`；历史参考用 `results/a/q2-nikolastarx/target-audit-20260924/` 的已冻快照，或中央另外冻结的新快照，不静默更新对照。
6. **截止与升级**：无用户硬截止，按中央资源窗口安排。普通已结束的单格算法/E0 失败保存后可继续预定下一格；版本/哈希漂移、未知调用数、控制器/观察器故障、残留子进程或 RSS 越界时停止后续派发并交中央处理。超时失败不自动重跑；重新准入必须有新明确协议与去重记录。所有运行输出用新独立目录，绝不覆盖已封存 run。

## 单格执行契约

在冻结仓库根目录，按实际平台选用 Python 路径；以下 `CASE`、`K` 和 `OUT` 是执行协议替换的占位值，输出目录须新建且互不相同：

```text
python -B -m src.q2_nikolastarx.adaptive_direct data/raw/a/official/data/case_CASE.json --config data/raw/a/official/data/config.txt --cores K --output OUT/plan.json --evidence OUT/online --wall 30
python -B data/raw/a/official/code/multicore_cut_evaluate_problem_2.py data/raw/a/official/data/case_CASE.json OUT/plan.json --config data/raw/a/official/data/config.txt -o OUT/final/result.json --trace-output OUT/final/trace.json --log-output OUT/final/official.log
```

从输出 `online/solver.json` 核实 status=ok、唯一 attempt=`adaptive_direct`、calls 全 0、plan_sha256 一致，再进入官方 E0。方案只有 `node_to_subgraph`、`core_schedules`；具体 route 放旁路证据。

已有 macOS runner 是同提交 `src/q2_nikolastarx/evaluate_matrix.py` / `evaluate_feedback.py`，支持 direct 契约、逐格持久记账、输入冻结校验和 board feed。**它的进程监视使用 POSIX ps，未在 Windows 验证，不能把源码交接当 Windows runner 准入。** 中央可复用已验证的平台适配器，或先冻结必要的适配补丁及有界进程预检；最终 runner 的完整 SHA/命令/控制器能力必须另记。算法内 `--wall` 只在构造后检查，真正超时与子进程回收须由外层 runner 执行。

## 解释与下一步

500 格静态路由为 envelope 421 / DAG 64 / resource-word 15；原件在 `results/a/q2-nikolastarx/adaptive-static-20260924/`。raw tensor priority 包络不是实际 Step2/Step3 零 spill 证书。016 两核、062 等单组件问题仍未解决，明确保留为反馈对象。后台 Pro 理论咨询尚在生成，未作为本候选证明或实验依据。算法负责人继续研究这些缺口，规模跑分由中央收口。
