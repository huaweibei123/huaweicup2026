# Q1 阶段复评原件归档（farmeruncle123 / Windows）

对应任务 `a-q1-stage-replay-farmer`（Issue #14，队长指令 5808778440 / 5809238857）。
本目录由 Git Data API（blobs→tree→commit→ref）从 `65d6c0e6facee2ec8ce9694c30dd805de99abf7e` 的 tree/parent 发布，**只含本目录**，不改代码/FORM/E0。

## 复评结果（两例全部通过，14/14 指标精确匹配）

| case | 输入计划（SHA-256） | 退出码 | 官方复评墙钟 | makespan | orig | sched | added | part | spill | cross |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 002 | `e83b72bfce840b1fb4529069ccac4bafd05ebd5b4eb473082ff20845a8f3acc8` | 0 | 0.7136 s | 90582 | 1224192 | 2360832 | 1136640 | 1136640 | 0 | 563712 |
| 044 | `ed987c6abf0764f9f64d0f99fd9eec52fbd3729f13d82f2404a9fad8a4e3dbd7` | 0 | 0.5919 s | 116227 | 975456 | 3823488 | 2848032 | 2771232 | 76800 | 161408 |

- 官方复评命令：`python -B data/raw/a/official/code/multicore_cut_evaluate_problem_1.py <graph> <plan> --config data/raw/a/official/data/config.txt -o <result> --trace-output <trace> --log-output <log>`（参数数组、`shell=False`、timeout=30s，见 `run_replay.py`）。
- 墙钟 0.7136/0.5919 s 是**复评墙钟**（CLI 启动到写盘，`time.perf_counter()` 单调钟原值），**不是方案生成时间**，不与 Mac 原搜索时间相除。
- 5 个搬运字段位于 result 的 `data_movement_bytes` 子对象（顶层无这些键）。

## 输入核验（全部通过）

- 官方 code 集合：按 `docs/a/source-manifest.json` @ `4dff90ef` 的定义（`path+TAB+sha256+LF` 按 path 排序拼接后 SHA256）逐文件核对 10 个 `code/*` 文件并重算聚合 = `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0` **精确匹配**。
- `data/config.txt` = `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`；`case_002.json` = `578fceeb9f66a3c083b9f27d8464cf75c1e7602cbc7290920c02aa1aef7ca352`；`case_044.json` = `9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e`。
- 计划件来源（原字节）：`results/a/q1-search-20260924/case002-order-preserving-v2/best_plan.json` 与 `.../case044/best_plan.json` @ `4dff90ef699fd51845cf482951e8477066f5f566`。
- 方案合法性：两方案顶层只含 `node_to_subgraph`/`core_schedules`、4 核、恰覆盖全部非 COPY ops（002: 1798 / 044: 1364）、每子图在 `core_schedules` 恰出现一次；结果 `scene="A"`、`num_cores=4`。

## 文件清单与 SHA-256（原字节；`*.run.public.json` 为派生副本，单独标注）

| 文件 | SHA-256 | 说明 |
|---|---|---|
| case002-result.json | `cbecb39060ed89653b0a14d7c4fa5b8c6bb55ff7f860ff8ba5f2837cd0c92ae0` | 官方 result 原字节 |
| case002-trace.json | `626e47d2c7bb0f5bf87a0b2b7a42ea8f29413187a24d565765ae057515927428` | Perfetto Trace 原字节 |
| case002.log | `fdce91448916fcb36159d58410ea82fe9dcff7af358e6eddbfb79e73de9b5867` | 文本日志原字节 |
| case002-run.json | `361277e4aa241c17635b50fbab69238605f16522489728f75088aaea93e46b15` | 运行记录**原件**（含解释器绝对路径，仅本地保留） |
| case002-run.public.json | `900939ecd6a3eee4549a1972257df995e87d72a453af345afbcadfbab7834f59` | **派生副本**：cmd[0] 解释器绝对路径映射为 `<python-executable>` |
| case044-result.json | `5e567b1d0cbdf6dc4cf14150f4b11d9f6002df41d11191dbef9ed45a28a080e1` | 官方 result 原字节 |
| case044-trace.json | `f78e62a060425f615a68d4b38e934f9fa8fd5e23483abcc7e9b516dc2b24f903` | Perfetto Trace 原字节 |
| case044.log | `1e73ddca358003b1366c1e09e55b845ae711cf04d2bcd87bd2e4bd017c45a96f` | 文本日志原字节 |
| case044-run.json | `8fba303505b68741a212b0be98a1d13a6d4bd9c7cf79c64b4d926b3c11100580` | 运行记录**原件**（含解释器绝对路径，仅本地保留） |
| case044-run.public.json | `c427cd72b07fd8a0ab9b914efeda1d528f07e9ec482ff7ebecd603a314586a12` | **派生副本**：同上映射 |
| case_002_multicore_res.json | `e83b72bfce840b1fb4529069ccac4bafd05ebd5b4eb473082ff20845a8f3acc8` | 002 计划**原字节** |
| case_044_multicore_res.json | `ed987c6abf0764f9f64d0f99fd9eec52fbd3729f13d82f2404a9fad8a4e3dbd7` | 044 计划**原字节** |
| run_replay.py | 见 git blob | 最小标准库 subprocess 包装 |

## 时间记录（勘误口径）

- `run.json` 只记录 `wall_seconds`（`time.perf_counter()` 单调钟原值）；**未记录 UTC 起止 ⇒ 起/止 UTC 记为 unknown**，不推算、不补造。
- 本归档相关评论的 GitHub API 发布时间（权威）：接手回信 **06:19:20Z**（5808841944）、四条表 03:11:27Z+勘误 03:27:44Z 属前一任务、复评交付 **06:41:54Z**（5809129149）。此前正文“T0=06:25:00Z”“06:2xZ”**表述不当，撤回**；“远低于 30 分钟”的模糊说法**撤回**，时限以可证据化的发布起止为准。

## 边界

- 两例 makespan/搬运值为 **Windows 跨机复现**，不宣称全 JSON 零差分、端到端求解速度、E1/E2 达标、100 图/全平台通过。
- 源摘要/源说明不在此搬运，用固定链接：`docs/a/Q1_SEARCH.md`、`docs/a/source-manifest.json`、两份 `summary.json` 均 @ `4dff90ef699fd51845cf482951e8477066f5f566`。
- FORM/PR17 验收状态不受本归档影响。
