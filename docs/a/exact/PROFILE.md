# E1 Problem 1 等效加速候选：范围、剖析与实测

> 状态：阶段开发证据，尚未通过发布验收。当前 Python 候选在三例开发矩阵中与 E0 的函数层 full 结果零差分；加入隔离的 Step3 schema-copy 后，最新配对几何平均加速为 1.20--1.23 倍，仍未达到 3 倍门槛。

## 1. 证据身份

本页只描述 `src/eval_exact/` 当前实现及下列已保存证据，不外推到其他问题、输入或机器。

| 项目 | 值 |
| --- | --- |
| 任务 | `a-r1-fast-eval` |
| 开发分支 | `codex/a-r1-fast-eval-lyx0217` |
| 开工基线 | `ea25b9334a1287766b4b2ebedc9875d5d341eff6` |
| 冻结官方代码 hash | `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0` |
| 官方 Problem 1 文件 SHA-256 | `2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f` |
| config SHA-256 | `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9` |
| 首轮性能证据 | `results/a/exact/r20260923-e1-matrix/` |
| schema-copy 性能证据 | `results/a/exact/r20260923-e1-schema-copy-v2/` |
| schema-copy 代码提交 | `8edccee2c85b3b46c55b0f08f3273b01d501f8b2` |
| 实测环境 | Windows 11 `10.0.26200`，Python 3.12.13，AMD64 Family 25 Model 80，16 个逻辑 CPU |

基准记录的是单进程、内存内函数调用。它排除进程启动、JSON/Trace 序列化和磁盘写入，因此不能解释为完整 CLI 加速比。

`run.json` 还记录候选实现 ID、`_official.py` 与 `problem1.py` 的 Git 交付 LF 字节 SHA-256，以及基准脚本自身的交付字节 SHA-256。基准生成的 plan JSON、计时 CSV 和 `run.json` 均固定使用 LF；每个 `plan_sha256` 直接对落盘 plan 字节计算，因而与 Git 暂存及交付字节一致。

## 2. 实现范围

E1 只实现了官方 **Problem 1 / scene A** 的 Python 快路径。`problem1.py` 在隔离加载的官方模块实例中替换 `_build_scene_a_tasks`，并只在该候选的私有 Step3 模块中将一处通用 `deepcopy(ext_graph)` 替换为受 schema guard 保护的一层复制。Step1、Step2、Step3 调度逻辑、全局校验、事件模拟和结果组装仍调用冻结官方实现；官方文件和独立 E0 oracle 的模块全局量均不修改。

第一处改写是 Task 边界构图：先在全图上建立“每个 Task 触及的 tensor”“每个 tensor 的有效生产者/消费者”“Task 内直接边”和外部 COPY_OUT 等索引，再逐 Task 只访问相关对象。第二处改写利用当前 Step2 扩展图只有 `ops/tensors/edges` 的扁平字典记录和整数 `seq_ext` 的事实，在复制同时验证容器、字段和值类型。出现新增顶层字段、嵌套可变值、非标准容器、重复可变对象或共享顶层容器时，立即回退预先保存的官方 `deepcopy`，保留别名语义。生成 ID、排序、边界 COPY、流量统计、spill 和 Step3 调用顺序按官方代码保留。加载器在每次建立运行时前复算全部官方 `code/*` 的 hash，并临时隔离 `contest_io`、三个调度模块等同名依赖，避免环境中预载模块污染差分两侧。

### 2.1 当前接口支持表

| 能力 | 当前状态 |
| --- | --- |
| 官方图 JSON、方案 JSON、config | 使用冻结官方读取/校验代码 |
| Problem 1 显式图、方案、config、输出路径 | `src.eval_exact.cli` 可运行 |
| Problem 1 结果 JSON | 用官方 `contest_io._write_json` 生成；函数层 full 值已做有限差分 |
| `--trace-output`、`--log-output` | 使用官方格式化函数；case 019 的结果/Trace/日志均与官方 CLI 逐字节相同 |
| 省略 plan/config 时采用官方默认路径 | 已复用官方 `_common_paths` 命名；尚未单独保存默认路径探针产物 |
| `-o` 短参数及全部官方默认命名 | 已实现，与官方 argparse 参数一致 |
| Problem 2 / Problem 3 | 未实现；不得调用本候选或推断支持 |
| 公共 `team_eval` / JSONL 适配层 | 未实现 |
| 官方拒绝语义 | 缺失一个映射节点的非法 plan 与官方同为退出码 1、stdout/stderr 相同且不落结果；完整非法输入矩阵尚未对照 |
| C++ / Rust 内核 | E1 当前仍为 Python；E2 的独立原生小内核见代理文档 |

因此，本实现可声明的范围是“官方 Problem 1 CLI 形状及已测成功/失败路径兼容”，不能外推为三个问题的完整接口兼容。Problem 2/3 没有用伪结果补齐；调用方应保留 E0 或等待明确的 `unsupported` 适配层。

## 3. 热点依据

首轮原版完整 CLI 的 `cProfile` 原始 `.pstats` 保存在 Git 工作区之外，未纳入本次提交。其文件名和 SHA-256 分别为：

- `case001_p1_seed2026.pstats`：`4606d9c9325d71f15759f59ad06d71628eda8cbe753de175f0fef4a6cc299d2c`；
- `case003_p1_seed2026.pstats`：`738b5ad8b78f125803c82a1ad7a894c49c7e0769bd954307d778385e1bbbabb8`。

| 原版完整 CLI 剖析 | case 001 | case 003 |
| --- | ---: | ---: |
| 总函数调用（含 primitive） | 2,968,539（2,454,958） | 65,127,269（55,284,145） |
| 总累计时间 | 1.864 s | 49.463 s |
| `evaluate_scene_a` 累计 | 1.102 s | 33.901 s |
| `_build_scene_a_tasks` 累计 | 0.627 s | 19.720 s |
| 边界扫描生成式（官方文件第 116 行） | 未进入前 20 | 25,682 次，累计 5.326 s |
| JSON `dumps` 累计 | 0.572 s | 14.790 s |

这份数据支持优先减少 Task 构图中的重复 tensor 扫描，同时也说明大例完整 CLI 的序列化占比很高。当前 E1 只改了前者，且后续配对计时排除了序列化；不能把函数内收益外推为完整 CLI 收益。原始 profile 未随仓库跟踪也是一个复核缺口。

可用下列模板重新生成原版完整 CLI profile；`<scratch>` 必须指向 Git 工作区之外的新目录，输出路径不得复用：

```powershell
uv run python -m cProfile `
  -o <scratch>/profiles/case001_p1_seed2026.pstats `
  data/raw/a/official/code/multicore_cut_evaluate_problem_1.py `
  data/raw/a/official/data/case_001.json `
  <scratch>/plans/case_001_seed2026_4c.json `
  --config data/raw/a/official/data/config.txt `
  -o <scratch>/baseline/case001_p1_result.json `
  --trace-output <scratch>/baseline/case001_p1_trace.json `
  --log-output <scratch>/baseline/case001_p1_log.txt
```

## 4. 有限差分与配对计时

正式开发矩阵使用官方 stub 生成方案：seed 2026、4 核、子图大小 4--12；每例预热 1 次、正式重复 5 次，并交替 E0/E1 执行顺序。初始、预热和每次计时调用均递归比较完整 Python 对象：类型、字典键、列表顺序、整数、浮点和其他值必须完全相等，不使用容差或字段白名单。

| case | E0 中位数 / s | E1 中位数 / s | 中位数比 | 配对速度比几何平均 | 配对 `>=0.8x` | full 差分 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `case_001.json` | 0.6594144 | 0.5576887 | 1.1824x | **1.0910x** | 80% | 0 |
| `case_019.json` | 0.4968331 | 0.4450142 | 1.1164x | **1.1193x** | 100% | 0 |
| `case_080.json` | 1.4722241 | 1.2911143 | 1.1403x | **1.1642x** | 100% | 0 |

三例的 E0/E1 Makespan 分别同为 189027、141133、294124 cycles。有限矩阵满足本轮“无未解释 full 差分”观察；case 001 有 4/5 对达到 `0.8x`，另两例为 5/5。三例均没有达到配对几何平均至少 3 倍的性能门槛，故结论只能是“正确候选/局部热点增量”，不是高速 E1 验收通过。

### 4.1 Step3 schema-copy 后续矩阵

固定提交 `8edccee2c85b3b46c55b0f08f3273b01d501f8b2` 增加候选私有 runtime 的 schema-copy。相同三例、plan、seed、核数、预热和重复设置得到：

| case | E0 中位数 / s | E1 中位数 / s | 中位数比 | 配对速度比几何平均 | 配对 `>=0.8x` | full 差分 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `case_001.json` | 0.5288300 | 0.4326500 | 1.2223x | **1.2264x** | 100% | 0 |
| `case_019.json` | 0.4930355 | 0.4184126 | 1.1783x | **1.2015x** | 100% | 0 |
| `case_080.json` | 1.3552686 | 1.1216487 | 1.2083x | **1.2189x** | 100% | 0 |

三例 Makespan 仍分别为 189027、141133、294124。另对固定开发池 64 个候选和队长复核生成规则下的 169 个微型输入复跑：64/64 的保存 E0、现算 E0 与 E1 完整结果一致；微型输入 77 个正常结果、92 个拒绝均与 E0 的完整结果或异常类型和消息一致。该集合仍是有限开发检查，不是形式等价证明或封存发布验收。

## 5. 复现

输出目录必须预先不存在：

```powershell
uv run python -m src.eval_exact.benchmark `
  --cases case_001.json case_019.json case_080.json `
  --output-dir results/a/exact/<new-run-id> `
  --seed 2026 --cores 4 --warmup 1 --repeats 5 `
  --min-subgraph-size 4 --max-subgraph-size 12
```

对单个方案运行当前内部 CLI：

```powershell
uv run python -m src.eval_exact.cli `
  data/raw/a/official/data/case_001.json `
  results/a/exact/r20260923-e1-matrix/plans/case_001.plan.json `
  --config data/raw/a/official/data/config.txt `
  --output results/a/exact/<cli-run-id>/result.json `
  --trace-output results/a/exact/<cli-run-id>/trace.json `
  --log-output results/a/exact/<cli-run-id>/result.log
```

回归测试（schema-copy 提交后本机实测 11/11 通过）：

```powershell
uv run python -m unittest discover -s tests/eval_exact -p 'test_*.py' -v
```

测试同时覆盖两组函数层 full 结果、预载同名依赖与私有 alias 隔离、混合 core 长度下不跳过任务环校验、schema-copy 的 runtime 隔离/输出别名隔离/schema 漂移与共享别名回退、基准产物 LF/哈希约束、成功 CLI 三类产物逐字节相等，以及一个非法 plan 的退出/错误/不落盘语义。它们都是有限开发证据，不等价于完整非法输入矩阵。

## 6. 未验收项

- 尚未覆盖 100 个正式 case、Problem 2/3、2--5 核、FORM 全部对抗样本、非法输入与执行环矩阵。
- 尚未保存改写后分阶段 profiler，也未完成冷启动、批量 1/16/64/256、内存峰值和完整 CLI 配对计时。
- 当前三例共享一个 seed 和一种官方 stub 方案分布；这不是冻结发布矩阵，也不是独立封存集。
- 已测一组成功结果/Trace/日志逐字节对照和一组非法 plan；默认路径、`-o`、缺配置、重复 JSON key、执行环及其他失败出口仍未形成完整矩阵。
- 未实现缓存、增量、回退计数或跨请求状态；当前性能数字不包含这些服务成本。
- E1 没有原生内核路线；E2 的 C++ 固定点小内核已运行，Rust 因本机无工具链未运行，两者均不能替代 E1 官方 full 结果验证。
- 差分测试只能证明列出的调用未发现分歧，不能证明全部输入域等效；最终结果仍须由独立 E0 验收。
