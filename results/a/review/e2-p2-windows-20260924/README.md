# P2 Windows 合成定点测试：部分通过，按首失败停止

本轮 A/B 通过，C 在测试驱动的完整结果跨表示比较处失败；D/E 未运行。不得据此宣布 P2 全面通过、P3 通过或 Q2 正式接入。原失败驱动、原始输出、失败状态均保留；没有修补评价器、重试、补跑或新正式图评价。

## 任务卡六字段

1. **目标**：在 Windows 独立核对 E2 的新 P2 BC 库和最小合成接口，服务后续 Q2 接入审查，不代替算法质量、正式图覆盖或速度门槛。
2. **输入**：生产代码 `997813c7c83d4d18a0a8e2a19b5be37b90223e01`；分支基点 `603b0741e21c449d3db652ebd67c94f2dc014cc9` 仅改报告与清单。固定三操作 G、17 byte 直接边及 R/S/T 归属/顺序、原冻结 `tests/eval_exact/fixtures.py` spill 图、冻结 P2 config；见输入原件和 hash。无正式图、无随机采样。
3. **产物**：固定驱动、输入、完整真值/逐操作记录、全部 stage stdout/stderr、请求前预留与实际记录、Windows Job 清理、身份/hash、实际工作目录源码快照、只读失败归因和共享副本双 hash。
4. **限制**：仅合成；上限 29 record + 3 debug + 16 固定 E0 = 48 逻辑入口，潜在 E0 上限 45。逐阶段预留、未知不退账、首非预期失败停止；全流程 900 秒，准备 300 秒，600 秒后禁止新评价。构建一次，workers 不超过 2，不改被测源码，不运行整套 `verify_b/resources_b/test_scene_b`。
5. **验收**：只承认实际完成的 A/B 与 C 的路由/三指标观察；完整 API 类型比较失败，D/E 未验。Review 状态，不作整体验收。
6. **截止**：T0 `2026-09-23T23:10:28.4471625Z`；准备截止 `23:15:28.4471625Z`、评价截止 `23:20:28.4471625Z`、交付截止 `23:25:28.4471625Z`。UTC 和 Windows 单调时钟均记录。控制器在 T0+292.447699 秒停止；收尾端点见 PUBLICATION/FINAL_VERIFICATION。

授权：协调任务对本专项的明确批准，公共回执 [#15 comment 5804475779](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5804475779)。执行 session `yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce`；LYX 原独立职责保留。本测试已接触开发交付文档，不声称盲审。

## 实际结果

| 范围 | 执行 | 结论 |
| --- | --- | --- |
| BC 冷构建/真实载入 | 一次编译，ABI=1 | 通过；15.378868 秒，build Job 8 个进程，结束活跃数 0 |
| A 合法/配置/缓存/隔离/spill | 9 record、7 显式 E0、3 debug | 9/9 native；三指标类型和值一致；27 个操作起止逐项一致 |
| B 非法/异常语义 | 5 record、5 显式 E0 | 官方异常类型/消息一致，3 invalid、2 error，均 e0_fallback |
| C 缺库/ABI/native 开关 | 3 record | 3 次 e0_fallback 与已存真值三指标一致；前两项是 mock 故障注入 |
| C full | 1 record | e0_full，三指标一致；完整结果严格比较断言失败，C 整体 exit 1 |
| D pool 回收/超时/RSS | 0 | 未运行 |
| E search/full CLI | 0 | 未运行 |

A 的 makespan：R 冷/热 506，顺序 S 508，归属 T 4，带宽 30 和容量翻倍各 506，delay=0 为 6，外部图修改后仍 506；spill 图 43728 cycles，spill_added_copy_bytes=1572864。17 byte 传输在带宽 60/30 下均舍入到一个周期，因此带宽变体本次验证配置和缓存身份，不能声称覆盖了不同传输周期。R 热、delay、快照三次命中；顺序、归属、带宽、容量变化均 miss。

build/A/B/C 的 Job 均返回活跃进程 0，无外层强制回收。C full 断言发生在 pool 上下文内部，异常退出后实际进程树已清理；C 的最后一个显式重复 close 断言没有执行，不能补签为执行过。D 专项超时、RSS 和双 worker 清理仍未验。

## C 失败归因及证据边界

`run.py:130` 的 `eq(row['result'], t)` 是首个非预期失败。`t` 来自 A 阶段完整真值的 JSON 重载，而 pool 返回的是 pickle 传输的原 Python 对象。冻结官方 P2 源码 578–583 行在 `memory_peak_by_core` 与 `step3_by_core` 中以整数 `core_id` 作字典键；JSON 保存/重载将这些键变成字符串。驱动的字典键严格比较不允许这两种表示相同。

停止后仅读取已保存文件：C full result 与 A-R 真值在 JSON 表示下所有字段及类型完全一致，见 `READ_ONLY_POSTMORTEM.json`。该现象及源码支持“测试驱动的跨表示类型比较导致假失败”的归因，没有发现已保存数值差异。但序列化前的完整对象类型没有单独归档，因此不把只读规范化比较改写成运行时完整 API 类型验收通过。

后续若获新批准，应使用保留类型的真值工件或显式契约规定的 JSON 比较，单独审查新增/续测预算。本轮未修改驱动、不再评价，C 原失败和 D/E 未验保持。

## 预算与实际调用

| 口径 | 数量 |
| --- | ---: |
| 批准 record / debug / 固定 E0 | 29 / 3 / 16 |
| 已启动阶段预留 record / debug / 固定 E0 | 18 / 3 / 12 |
| 已启动阶段潜在 E0 上界（不退） | 30 |
| 返回 record | 18（native 9、e0_fallback 8、e0_full 1） |
| 实际直接 debug native | 3 |
| 实际显式合成 E0 | 12（7 成功、5 预期异常） |
| 按完整路由和源码推得自动 E0 | 9（4 成功、5 预期异常） |
| 推得 E0 总入口 | 21（11 成功、10 预期异常） |
| 逻辑评价入口合计 | 33 = 18 + 3 + 12 |
| 未返回/超时/内部进度未知 | 0 |
| 正式图 E0 / P3 | 0 / 0 |

自动 E0 数量是由返回路由和每 record 最多一次 E0 的固定源码推得，并非另外插桩的独立计数器。失败比较断言不等于一次新 E0 调用。未启动 D/E 不消耗其阶段预留，也不将未用额度挪给新用例。三次 debug 是额外原生重放，不能漏记；其真值复用 A 已有完整 E0。

## 源码与环境身份

实际运行 HEAD：`a295af6ac222f28347bc1498b797ce35c3fa8e4b`。生产文件与基点相同；运行前及停止后 36 项源/输入/依赖清单/DLL hash 一致。`as-run-source.zip` 含其中 33 个非 DLL 文件的实际工作目录字节，逐项匹配 IDENTITY；DLL 只记录 hash，不上传。

必须区分源码内容与字节身份：运行时 `run.py` 混合 CRLF/LF，Git blob 为 LF。实际驱动 SHA256 `ef0de14c1a1eaa80cea8ed7b5686cab80e4b131d7746a465c1e3517fff749f75`，Git blob SHA256 `ba39afedf5136d21a4a5a3f755f571c2faeb9d9a6e1c794e6df570b16e7ff38a`；只做 LF 规范化后完全相同。随后新增 `.gitattributes` 没有追溯重写既有 index；没有为掩盖差异改写 as-run 提交。输入 JSON 与其 Git blob 逐字节相同。参见 `AS_RUN_BYTE_CHECK.json` 和真实字节源码快照。

Windows x64；Python 3.12.14；`uv sync --locked --offline` 使用已有缓存成功安装 14 包，未联网下载新工具链。LLVM-MinGW 20260922、Clang 23.1.2，显式 compiler，`-O3 -fno-fast-math -ffp-contract=off`。新 BC DLL SHA256 `c01a4e0f6c1868945392067ef70825b7ed6e8090c3240af91d18242199f706d9`，实际导出 ABI=1，路径留在脱敏 ABI 记录。复用既有匹配 libc++/libunwind，未改系统 PATH。

已知日志限制：最初 `uv sync` 输出保留于任务终端调用，未从启动单独写入 Git 外原始 stdout 文件；不补造该原始文件。所有构建/评价 stage stdout/stderr 均从启动写入 Git 外。公开副本只替换个人路径，原始 hash 与共享 hash 均在 MANIFEST 中；原始文件不改。共享目录的 `.gitattributes` 保持字节，最后核对 Git blob。Windows 无 `dot_clean`，仅扫描本次写入范围元数据残留。

## 复现说明与未验证项

固定命令为 `.venv/Scripts/python.exe research/a/review/e2_p2_windows_20260924/run.py --private <EVIDENCE>`；本窗口已结束评价，复现需要新的明确预算和新证据目录，不能复用 gate/账本当新运行。源码中准备和评价截止保护保持原样。

这是平台/接口定点证据，不是正式调度质量、10× 性能、全域等价性或解题器端到端 wall 结论。官方 makespan cycles 与求解 wall 分开；官方脚注建议与此次硬窗口分开。P1 既有平台通过不能替代本 P2 BC 验证。P3、正式图、完整 CLI、D 组生命周期以及完整 API 类型复核均留待后续审查。
