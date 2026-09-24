# a-r1-fast-eval：E1 等效加速与 E2 极速近似

负责人（2026-09-24 更新）：@lyx0217 负责 E1 工程化与 E2 交付后的独立测试；E2 核心方案、实现和开发验证改由队长评估器专项负责。
分支建议：`codex/a-r1-exact`、`codex/a-r1-proxy`，或同一任务下隔离实现目录
沟通 Issue：https://github.com/huaweibei123/huaweicup2026/issues/15
公共约定：[ROUND1](../../docs/a/ROUND1.md)，完整标准：[契约 v1 第 2、4、5、7 节](../../docs/a/contract-v1.md)。

## 当前分工覆盖首轮人员安排

用户于 2026-09-24 明确调整 E2：由 `nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`（评估器专项）开发，完成后交原队友 `lyx0217/s-89ad75751f054b6b9929e42d899246be` 独立测试。详见 [E2 开发任务卡](E2-CORE-DEVELOPMENT.md)。下文两条路线的技术要求保留，不再表示两条均由 LYX 开发。

- LYX 的 E1 / 原生精确 replay 工程化单写安排不变，范围为 `src/eval_exact/`、`tests/eval_exact/` 及本人结果/说明；固定交接见 [Issue15#5802208660](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5802208660)。
- 原 E2 固定件为 `d83d5f32a1c23f6450aa9c15fa85891c4ebddd7f`、分支 `codex/a-r1-fast-eval-lyx0217`、PR20。旧分支与未提交成果保留；原执行者停止 E2 新开发，回报实际 HEAD、未提交改动、在途实验和 Atlas 请求。不能把未回复当作已经停写。
- 新专项可以立即在独立研究/结果目录推进。`src/eval_proxy/`、`src/eval_proxy_native/` 和对应测试目录的生产写权，待调度核实旧方停写及在途情况后明确切换；切换前双方都不新增生产改动，不覆盖或清理旧工作区。
- E2 开发者交固定提交、输入池、复现入口、近似/回退边界和测试清单；LYX 随后在独立工作区测试，失败回交开发者修复，不同时共写实现。独立运行不等于盲审，已有开发上下文须如实记录；最终验收仍由队长按范围决定。
- 指标、冻结 E0、官方 I/O、资源预算和封存池要求不变。原生精确核的局部倍率不等于 E2 已达标；不为分工调整追加无预算实验或自动使用队长专属资源。

2026-09-23 更新：同时执行[补充规范](../../docs/a/EVALUATOR_AMENDMENT_20260923.md)。公开输入/输出和 CLI 沿用官方格式；E1 零差分、至少 3× E0；E2 至少 10× E1，校准 Makespan 相对误差中位数 ≤1%、P95 ≤3%，速度与误差须同版本同配置达标。E2 安排 C++/Rust 小原型对照及至少两个算法方向，E1 持续独立推进。首批原型与最终联合验收分开，未实现的完整输出不得伪造。补充规范覆盖旧契约对应条款，其余沿用。

1. **任务目标**：两条路线同时探索。E1 通过 profiling 找到实际热点，替换热点而保持声明范围内的官方可观察行为；E2 允许改变算法和近似语义，以低总成本保留值得精评的候选。成员自主决定语言、数据结构、优化方法；如使用多个 Agent，由本人现有工具与授权决定，队長不预设客户端能力。
2. **输入文件**：冻结题面、官方源码/config、100 个 case 及 `docs/a/source-manifest.json`；公共契约；FORM 分批交付的规则与公开对抗样本。先直接用未改动原版 profiling，不等 FORM 全部完成。样本包含小/中/大正式图及非平凡划分；报告确切图/方案、problem、核数和环境。
3. **输出要求**：E1 在 `src/eval_exact/`，E2 在 `src/eval_proxy/`；`results/a/exact/<run-id>/`、`results/a/proxy/<run-id>/` 保存运行记录、性能/差异 CSV、失败案例；`docs/a/exact/PROFILE.md` 和实现范围说明；`docs/a/proxy/APPROXIMATIONS.md` 写近似、偏差、检测及失效场景；论文片段 `paper/sections/a-evaluators.md`。首批交分阶段耗时和热点选择依据、E1 第一个有针对性差分的改写、E2 第一个可运行估计/排序原型。至少可通过明确命令对给定图/方案得到结果，接口待适配范围明示；不能宣称未实现的 team_eval CLI 已可用。
4. **限制条件**：E0/config 原件只读；不自行修改公共 schema、金标准、比较器、验收门槛和封存池。最终成绩经 E0 复算。先无缓存一致性，再考虑缓存/增量，防止请求间状态污染。E2 未完整检查执行就标 unchecked；rank_only 不能伪装 cycles。未知/超时/崩溃不伪装 invalid。计时包含 plan 相关构图/特征/传输/同步，冷/热/批量/CLI 分开，原生与回退 E0 分开。不租付费算力、不安装新 Skill；共享依赖改动通过小 PR 协调。
5. **验收标准**：E1 首个改写在声明的小型矩阵中，无未解释的状态/整数指标/full 结构差异；定位首个分歧并保存反例，不调容差掩盖。提交改写前后 profiler 与配对时间，未加速也如实报告。E2 报实际成本和近似边界，优先衡量同图同题同核数候选池的短名单损失，所有用于排名评价的池成员均须有 E0 真值，不能只标注入选者。资源允许时首轮完成至少一个 64 候选开发池；不足则标原型未完成质量验收，给出预算依据。补充规范中的速度、数值误差及短名单质量为最终联合门槛；首批达不到不能包装成高速低误差验收通过。E1 未成熟时 E2 可先对 E0 评估，不互相等待。收到 FORM 开发反例后纳入回归；最终封存验收由队长指定的独立会话执行。
6. **截止时间**：实际接手后约 1 小时 profiling/路线依据，约 3 小时首轮交接为建议节奏。首次回复实际 T0、预计交付时刻（Asia/Taipei）与阻塞；无另行确认的硬截止。两路线均有首批产物，不要求第一轮完成全量发布矩阵。

## 交付记录

状态：首批阶段交付，待队长独立复核；未达到 E1/E2 联合发布门槛。

| 字段 | 实际交付 |
| --- | --- |
| 目标 | E1 索引化 Problem 1 Task 边界构图；E2 静态排序与粗粒度事件估计两条路线；C++/Rust 同一合成小内核探索。 |
| 输入 | main `8ba6248f16a85324901a787676b1658e532f5c1c`；官方 code hash `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`；config SHA-256 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`；FORM PR #17 最终固定开发证据 `dab91d612bd26183e12d30848b13d5fb14e071c7`（排序夹具 blob 与此前版本相同）。 |
| 输出 | `src/eval_exact/`、`src/eval_proxy/`、对应测试；`results/a/exact/r20260923-e1-matrix/`、`results/a/proxy/r20260923-e2-dev64-gzip/`、`r20260923-e2-route-compare/`、`native-smoke/`；两份方法文档及论文片段。 |
| 限制 | 仅 Problem 1 开发范围；单图开发池不是校准/封存集；E1 未到 3x；event E2 数值误差失败；Rust 未运行；浏览器 Canvas/Board 未由本客户端实际打开。 |
| 验收观察 | E1 三例 full 对象零差分，配对几何平均 1.0910x/1.1193x/1.1642x；case 001 的 `>=0.8x` 配对占 80%，另两例为 100%；成功 CLI 结果/Trace/日志 byte-exact，非法 plan 行为一致。rank E2 64/64 有 E0、遗憾 0、Spearman 0.8568；event E2 遗憾 0、Spearman 0.8127，但误差 median 25.7591%、P95 28.8954%。最新同池内存计时为 E2 0.3559557 s、E0 full 28.7685327 s、观察比 80.8205x；两路线 route median 分别 0.3385280 s、0.3438034 s。C++/Python 31,387 字节 SHA-256 相同；Rust toolchain unavailable。 |
| 交付 | 分支 `codex/a-r1-fast-eval-lyx0217`；PR [#20](https://github.com/huaweibei123/huaweicup2026/pull/20)；Atlas 仅在 PR 可访问后提交 `review + deliverables`，pending 不记成功。 |

2026-09-23 后续 E1 增量：提交 `8edccee2c85b3b46c55b0f08f3273b01d501f8b2` 在候选私有 Step3 runtime 中加入受 schema/别名 guard 保护的扩展图复制，未知结构回退官方 `deepcopy`。固定开发池 64/64 和独立生成的 169 个微型输入未发现 full 结果或异常语义差分；新增后 E1 单测 11/11 通过。三例更新证据位于 `results/a/exact/r20260923-e1-schema-copy-v2/`，配对几何平均为 1.2264x/1.2015x/1.2189x，仍未达到 3x，任务继续保持 review。

主要复现命令：

```powershell
uv run python -m unittest discover -s tests/eval_exact -p 'test_*.py' -v
uv run python -m unittest discover -s tests/eval_proxy -p 'test_*.py' -v
uv run python -m unittest discover -s tests/eval_proxy_native -p 'test_*.py' -v
uv run python -m src.eval_proxy.compare_routes --graph data/raw/a/official/data/case_001.json --config data/raw/a/official/data/config.txt --pool-dir results/a/proxy/r20260923-e2-dev64-gzip --output results/a/proxy/<new-route-run>/summary.json --warmup 1 --repeats 3
```

完整基准命令、环境、seed、计时边界和局限见 `docs/a/exact/PROFILE.md`、`docs/a/proxy/APPROXIMATIONS.md` 与各结果目录。有限测试只表示所列样本未发现差异，不证明全部输入等效。
