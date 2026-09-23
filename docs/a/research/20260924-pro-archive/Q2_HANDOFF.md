# A/B 并行核心研发：给协调会话的交接建议

可由两人并行：当前算法会话继续 Q1/A；建议新成员 yuanzhifang30-sudo 独立负责 Q2/B 构造与有预算搜索。此文提供技术拆分和材料，正式任务、分支、邮箱和 Atlas 路由由队长下发；本文不自动认领或转授账户权限。

## 可复用与必须分开的部分

| 层 | 可复用 | B 必须单独处理 |
|---|---|---|
| 输入/输出 | 冻结原图、非 COPY 算子全集、张量身份/大小/位置、官方两字段 plan JSON、同一固定配置文件 | 按 Q2 入口解释 plan，不沿用 Q1 独立 Task 图作为实际执行图 |
| 图分析 | COPY 收缩后的依赖、弱分量、非分叉链、张量消费支撑、must-link/SCC 的商图性质 | 商图无环不是完整执行合法性；还需局部优先级、FIFO/内存依赖与跨核 COPY 联合检查 |
| 构造 | 分组、核归属、多候选组合、官方确认和预算/失败记录方式 | B 每核一 Task；子图顺序可以影响局部资源词及 COPY 位置，同核不同子图可复用数据 |
| 成本 | 真实 E0 作为真值、搬运量不充分、spill 条件计费与 backing/incarnation 状态 | B 的跨核 COPY delay=500；不能使用 A 每子图 Task 门控及100/1000等待，也不能把同核通信按 A 的跨 Task 规则计算 |
| 精确复用 | 版本/输入顺序/容量/带宽守卫、返回对象隔离等原则 | PR30 的 P1Evaluator 仅用于 Q1；第三路 W 也只在固定编译上下文、完整字面词等守卫下适用，不能泛化为任意 B 方案缓存 |

A 的 cover contraction 无环数学工具可参考，但其 Task 出口释放成本不是 B 的收益模型。A 当前内存压力和分核搜索是否进一步改善，不是 B 启动的硬依赖。

## 建议给新成员的核心任务

**目标：用官方 Q2 CLI 构造可提交且可复跑的 B 搜索器，而不是先重写共享 evaluator。**

第一阶段固定几个核归属基线，比较粗子图、细分子图优先级、阶段收尾/同质资源词；记录每个候选的 Task 数、搬运分项、spill、FIFO/关键 trace 与 makespan。先在下面两个小反例上确认语义，再在公开开发例 002、008、044 做有限预算搜索；这些图已有 Pro 暴露，不作封存集。具体时间/候选预算由任务卡冻结，可从单 worker、每例最多32次候选和独立 E0 截止起步。

成功标准：从原始图独立输出官方 plan；不改算子/配置/E0；所有报告成绩可追溯至本轮实际 Q2 CLI 输出；至少包含顺序有益、顺序无益/退化、内存压力或超时的保留记录。无收益也如实交付，不能强行包装。固定归属下的构造消融与不同归属间的改善分开说明，不只与随机 stub 比。

建议写范围：`src/q2/`、`tests/q2/`、`results/a/q2-yuanzhifang/` 和独立 B 方法文档。不要修改 `src/q1/`、`tests/q1/`、`src/eval_exact/`、`tests/eval_exact/`、`data/raw/`、配置或共享契约；共享文档由队长维护。需要公共图工具时先提出输入/输出与确定性约定，暂时通过冻结官方 helper 或独立薄封装复用，不让两人同时改公共模块。

## 全部已发布于组织主库的材料

成员使用 `huaweibei123/huaweicup2026`，不需要也不应尝试队长的 Vioano/Colab 账户。以下都是组织主库固定提交可取；私聊正文已经归档，下载 ZIP 的实际 payload 也已归档。

| 固定 SHA | 用途与路径 |
|---|---|
| `cd5ef2b8a9f3518579167bf8a9271d6a76403b30` | main 权限边界：`AGENTS.md`、`docs/a/CAPTAIN_RESOURCES.md`；队长可能再发更新任务卡 |
| `3a4505d4101e23d54580d15560da3820e02d05da`，PR31 | 研究全包：`docs/a/research/20260924-pro-archive/README.md`、`results/a/pro-research-20260924/`；官方源与 `docs/a/contract-v1.md`、`EVALUATOR_AMENDMENT_20260923.md` 都可读取 |
| `e1575a1de5e3b921aef350e920720f0584fb1719`，PR28 历史固定审查点 | `results/a/review/q1-form-65d6c0e/REVIEW.md`、`src/review/q1_form_semantic_probes.py`、`probes-v2/`；三项勘误与真实L1/backing多次换入反例 |
| `5bfe53a29c1ba05167239f51ea937e602f7f85b4`，PR30 | P1批量接口的参考设计、测试和边界，不是 B 已可用的加速器 |
| `d2e60539417f92803e9796dcd68b6e21173fafdf` | A 有预算搜索、五例结果、去重修订：`src/q1/search.py`、`docs/a/Q1_SEARCH.md`、`results/a/q1-search-20260924/` |

这些提交有的仍在未合并分支。新成员应按队长给定基线建自己的 worktree；分支尚未合并 main 不等于材料不可读，也不必把 A 搜索实现整体 cherry-pick 到 B。需要哪些研究文件可从固定提交提取，保留来源与哈希。

最短阅读顺序：当前任务卡和会话协议 → contract/EVALUATOR_AMENDMENT → 独立 REVIEW 与三路勘误摘要 → 官方 Q2 `_build_scene_b_tasks`、`_prioritize_task_seq`、Step2/Step3 → Pro2/Pro4 构造报告及源码 → Pro3 的等价边界和反例。无需先读完四路全部长对话。

## Pro 的可用入口和不能跳过的反例

以下路径相对于 `3a4505d` 的 `results/a/pro-research-20260924/`：

- Pro2：`reports/pro2-r2-prototype/RESEARCH_MEMO_ROUND2.md`；`source/pro2-r2-prototype/construct.py`、`coarsen.py`、`resource_word.py`。重点是同质资源词、阶段编排、输入束和失败边界。must-link/SCC 只证明商图层。
- Pro4：`reports/pro4-followup/RESEARCH_REPORT.md`；`source/pro4-followup/construct.py`、`resource_word.py`、`memory_certificate.py`。阶段收尾是候选；无 spill 证书是严格限定 singleton 域的充分条件，不是必要条件或全局合法/最优保证。该回复没有完成要求的逐项勘误影响审计。
- Pro3：`reports/pro3-r2/REPORT.md`；`source/pro3-r2/word_quotient.py`、`hol_probe.py`、`fork_probe.py`、`float_counterexample_strict.py`。避免把纯计算词、实数服务等价或总搬运相同升级成 E0 等价。
- Pro1：`reports/pro1-r3/RESEARCH_MEMO.md`、`source/pro1-r3/packet_construct.py`、`window_refine.py`。链包与构造分核可借鉴；3×3 响应仅是限定纯计算模型，同核 resident 集不是容量状态或通用缓存。

第三路完整反例位于 `pro3-r2.tar.xz` 的 `route3_round2/results/counterexamples/`：

| 子目录 | 最小阅读/复跑输入 | 作用 |
|---|---|---|
| `head_blocking/` | `graph.json`、`plan_0.json`、`plan_1.json` | 同切分/归属，仅改子图顺序会改变 FIFO 队头阻塞；作者Q2报告15511→10511，需新成员本机复跑 |
| `fork/` | `graph.json`、`plan0.json`、`plan1.json` | 粗细分桶可能改变 COPY_OUT 位置与远端释放，不能只保留计算操作词 |
| `float_epochs_with_input/` | `graph.json`、`plan.json`、`S_check.json` | 合并共享 DDR 的浮点结算事件可差1cycle；不得先做实数等价再声称 E1 精确 |

L1/backing 反例在 `e1575a1` 的 `results/a/review/q1-form-65d6c0e/probes-v2/spill.graph.json`、`spill.plan.json`、`spill.step2.json`。这是经 Q1 路径得到的语义反例；若要验 B 的等价/缓存，需要另造 B 可达的对应输入，不能给原证据改标签。

## 可运行的最短 Q2 入口

先按仓库规则 `uv sync --locked`、`uv run python -B scripts/a_materials.py --extract`。下面示例使用 PR31 已发布的官方随机 plan；命令参数已按 Q2 `--help` 核对，**本交接没有将该命令声称为本机 B 实验成绩**。输出目录每次新建：

```sh
mkdir -p results/a/q2-yuanzhifang
mkdir results/a/q2-yuanzhifang/baseline-001
uv run python -B data/raw/a/official/code/multicore_cut_evaluate_problem_2.py data/raw/a/official/data/case_002.json results/a/q1-prototype-20260924/case002-structural-v1/official_stub/plan.json --config data/raw/a/official/data/config.txt -o results/a/q2-yuanzhifang/baseline-001/result.json --trace-output results/a/q2-yuanzhifang/baseline-001/trace.json --log-output results/a/q2-yuanzhifang/baseline-001/summary.log
```

要复跑小反例，只提取第三路包中的对应目录，把 CLI 的 graph/plan 路径替换为该目录的文件；每个 plan 用单独输出目录。先比较各自本轮 E0 结果，再对照作者数字，避免把下载完整性当复现。

## 交叉复核与依赖

B 交付 graph SHA、config SHA、官方代码哈希、plan/full/trace/log、生成脚本、预算、源码固定提交、环境和已知失败；A 会话可抽查 B 的少量新计划与机制解释，B 成员可反向抽查 A 的已发布计划。提交者自测、对接抽查和独立终验分开记录。

不共享可变搜索状态、worker、缓存或私有环境；相同 helper 的改动先由双方提议再由队长指定单写者。B 的起步硬依赖只有冻结 E0/数据/合同和独立工作区，不依赖 A 后续优化、P2高速 evaluator、Colab 或新 Pro 回答。

尚缺的只有已明确标注的旧295份历史完整结果，以及未做的独立复现/理论审计；本轮新增交接所需材料没有只留在私聊的必要文件。作者原型依赖、执行路径与源码应先审查，不能把下载的研究脚本直接当生产模块。
