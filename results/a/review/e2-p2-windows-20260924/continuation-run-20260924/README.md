# P2 续测：启动门禁失败，零评价，按首失败停止

固定驱动 `bf9be734426262839eba744e4172f2b0972e5047` 仅运行一次。预检在 `run_continuation.py:164` 的 `gate.pid == os.getpid()` 校验处报 `RuntimeError: wrong child gate`，尚未到达驱动中的 E2 import 或 BC 加载。C-full/D/E 全部未启动。本轮新增 E0/E2/debug/正式图均为 0，不改写 PR52 原 C 失败，也不增加 P2 通过范围。

## 任务卡六字段

1. **目标**：按已审核 PR55 仅复核 C-full 原生类型及此前未运行 D/E；不重跑 A/B、故障注入、P3 或正式图。
2. **输入**：生产 `997813c7c83d4d18a0a8e2a19b5be37b90223e01`、原交付 `a38dc6fea7f4d2f85f00bb7cdf1e5c9488aec2d7`；精确新驱动 `bf9be734426262839eba744e4172f2b0972e5047`。原合成 G/R/config、六个旧工件 hash、已有三 DLL 和锁定环境。准备成功复核 34 项源/环境/DLL hash；没有构建或安装。
3. **产物**：18 项原始/共享证据的双 hash、完整 outer/preflight stdout/stderr、门禁/原子账本、Job 清理、批准/T0、五文件真实源码字节快照及只读 launcher 元数据/源码摘录。
4. **限制**：批准上限 12 record +5 fixed E0，潜在 E0 17、debug/正式 0；全窗口 600 秒，准备/C-full 起点 90 秒，评价截止 300 秒，C-full 整阶段 30 秒。未使用任何剩余额度。首次非预期失败停止，无补丁、重跑、新窗口或启动器试验。
5. **验收**：此次只有身份准备、失败保存和 Job 清理得到实际证据；真实 BC 载入、C/D/E 均未验证。仍为 review；不是 P2 终验或 Q2 接入批准。
6. **截止**：T0 由驱动创建为 `2026-09-23T23:55:23.127083Z`、GetTickCount64=17536046；准备截止 `23:56:53.127083Z`、评价截止次日 `00:00:23.127083Z`、总交付截止 `00:05:23.127083Z`。控制器 T0+4.940204 秒停止；收尾时点另列 PUBLICATION 和最终回读回执。

执行 session：`yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce`。明确授权 [#15 comment 5804899809](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5804899809) 与类型澄清 [5804816099](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5804816099) 均在执行前全文读取。批准 JSON 在 Git 外生成，T0 完全由固定驱动生成，没有手工提前计时或复用旧目录。

## 已观察到的失败链

- 主进程把 `Popen.pid=37868` 写入原子门禁文件；子脚本读取后发现与自己的 `os.getpid()` 不等，抛出 `wrong child gate`。
- 这条断言先于批准复查、`sys.path.insert`、E2 import 和 `_native_b.get_lib()`。没有 ABI.json，也没有任一评价阶段的 child 记录。零评价结论来自控制流位置和零预留账本，不来自“没有成功结果”的猜测。
- preflight 子树返回 1；Job 共观察到 2 个进程，前后活跃数均 0，未强制回收；阶段 0.6967823 秒。主控制器记 `execution_state=stopped`，没有继续下一阶段。
- 原失败驱动未保存实际脚本 PID 的数值或启动前后的祖先快照。因此只报告“不相等”，不能事后编造第二个 PID 或声称已直接观测到父子映射。

## Launcher 归因：只读证据与边界

本机 `.venv/Scripts/python.exe` 的文件版本 OriginalFilename 为 `py.exe`；它与随同一 CPython 3.12.14 安装的 `Lib/venv/scripts/nt/python.exe` 大小和 SHA256 完全相同：277808 bytes，`81bac8328c3df7c80a0915ea0baf01996355ebcc00ab6f8dbfefb4e60935e2bc`。

本地 `Lib/venv/__init__.py:282–299` 说明 Windows 环境的 Python 副本使用 venvlauncher；源码摘录和完整文件 hash 已保存。结合 gate 比较失败和 Job 的两个进程，支持“Popen 获得启动器 PID，而脚本运行在实际解释器后代进程，驱动错误地要求二者 PID 相同”的归因。这是源代码/文件元数据支持的推断，尚无单独的进程祖先回归证明。

只读取文件版本、字节/hash 和 Python 标准库源码；没有运行新的 launcher 探针，没有绕过门禁、改驱动或重启评价。此处失败不构成 E2 核心/BC DLL 的运行失败证据。

## 调用与清理

| 口径 | 结果 |
| --- | ---: |
| 批准 record / fixed E0 / 潜在 E0 | 12 / 5 / 17 |
| 已预留 record / fixed E0 / 潜在 E0 | 0 / 0 / 0 |
| 实际 record / 显式 E0 / 自动 E0 | 0 / 0 / 0 |
| debug / 正式图 / 未知评价 | 0 / 0 / 0 |
| DLL 载入 / 编译 / 安装 | 均未执行 |
| Job 总进程 / 活跃前 / 活跃后 | 2 / 0 / 0 |
| 强制清理 / 驱动重试 | 0 / 0 |

只有 preflight 被启动，且该阶段本来就预留零评价。没有调用过新完整 oracle，没有 C typed/pickle 产物。原子账本最后版本保留失败；未把未运行 C/D/E 或剩余预算当成通过或重新授权。

## 源、证据与交付

`AS_RUN_SOURCE.json` 与 `as-run-source.zip` 保存五文件实际字节，均与批准 Git blob 逐字节相同。本次新驱动 hash `de2eab3d229826a67d5553f735f3b88ef63f09f1519af45309b39acaae0f61eb`；contract hash `8c07684fd26ea95fd0983d3219f148bc855583ad74e24ff9e2f156e3b3366aed`。

原始材料保留在工作区外。所有 controller/preflight stdout/stderr 从启动即写至私有文件；公开文本只替换个人路径，3 项发生替换，其余原样。MANIFEST 同时给出原始/共享 hash；5 文件 zip 未改变字节。停止后 34 项既有源/环境/DLL hash 再次匹配。最后校验公开文件与 Git blob，并扫描本次目录 `.DS_Store/._*/__MACOSX`；Windows 未运行 dot_clean。

唯一执行命令：

```text
.venv/Scripts/python.exe research/a/review/e2_p2_windows_20260924/continuation/run_continuation.py --private <全新Git外证据目录> --approval <本次批准JSON>
```

本轮已停止，命令不是再次执行授权。此前 A/B、P1 与其他队友的测试职责和证据保持原样。

## 后续边界

下一步只可另备静态门禁修复方案，验证真实执行子进程属于指定 Job，并结合随机门禁标识或等效边界；不能删除门禁或允许任意 PID。严格无 E0/无 DLL 的最小启动器控制回归也须协调另批。本次不实现/执行新控制回归，不做 P2/C/D/E 补跑，不写 Atlas，不标 done。
