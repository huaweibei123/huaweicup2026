# E1 原生后端：显式加载与回退首增量

本交付解决固定原型的硬编码 `.so` 加载与模糊回退边界。新增可显式启用的
`NativeP1Evaluator.score`；原 `P1Evaluator`、完整结果、批接口和官方 CLI 的源码未改。
**当前只有静态证据，未运行测试、原生代码或 E0/E1/E2；不是 Windows/E1 终验。**

## 1. 任务与固定输入

- 任务：`a-e1-native-portability-lyx`；[派发](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5806682441)、[接手](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5806713872)。
- 任务卡：`f5342694e256de22a081369086de20253925d8da:tasks/a/E1-NATIVE-PORTABILITY-LYX.md`。
- 代码基线：`03f02e79de4b4bd6f55241385664b154f4332454`，独立分支 `codex/e1-native-portability-lyx0217`。
- 公共规则：`d6ee2cdc75f2d9e0168f72109b314e11346830b5` 的 AGENTS、SESSION_PROTOCOL 与免费协作规范。
- T0：2026-09-24 11:03:13 UTC+08；首检查点 11:33:13，约 12:03:13 前交付/停止。
- 原型 Python 原件 SHA256：`6f3f9aaf278059351e87a84163f582880dcd43245f52d179a3fd40d00383998d`。
- 原型 C++ 原始 Git blob SHA256：`77b814a1fbf58bad0d07a630eab0ce5b4e5f357a74ab6dccc94f8ad6c7bb6ad6`；Windows checkout 的 CRLF 字节哈希为 `987a09e0468a6650537844b24faff8b2cc8802a9db148d5a176bc4c6ea97cd5f`。二者不混记，加载清单引用前者。

## 2. 修改及使用边界

| 文件 | 职责 |
| --- | --- |
| `src/eval_exact/native_backend.py` | 对一个显式清单做来源、平台、编译参数、产物哈希与 ABI 检查；随后才允许加载 |
| `src/eval_exact/_native_replay.py` | 固定原型的内部桥接；移除全局库/路径发现，接收调用方提供的库，保留运算顺序 |
| `src/eval_exact/native.py` | 新的显式评分入口、官方前置校验和一次完整 E1 回退 |
| `tests/eval_exact/test_native_portability.py` | 未运行的路由、清单、桥接边界及极小 E1/E0 集成测试源码 |

以下是接口说明，**本阶段没有执行**：

```python
from src.eval_exact.native import NativeP1Evaluator

engine = NativeP1Evaluator(graph)  # 默认不发现/加载原生后端
score = engine.score(plan, **config)  # 现有完整 E1；返回内部 ScoreResult
full = engine.evaluate(plan, **config)  # 保留原完整官方结果

# 下一阶段只有在产物/清单独立审阅且获得运行预算之后使用：
experimental = NativeP1Evaluator(graph, native_manifest=reviewed_manifest_path)
score = experimental.score(plan, **config)
```

`ScoreResult` 只有 `makespan`、`backend`、`fallback_reason`，不伪装完整官方 JSON，
不填造搬运量、trace 或审计字段。完整结果、完整/非完整 `evaluate_record` 和
`evaluate_batch` 都继承原 E1，显式清单也不会将它们切到原生。
未修改 `__init__.py` 的导出和 CLI；导入新加载模块也不加载 NumPy/桥接/动态库。

原生评分先按 `_scene_a` 的顺序执行 `capacity=dict`、官方参数检查、原有
`_build_tasks` 的图/计划/联合任务顺序校验，再处理后端。原型只接受内建 int
任务 ID，官方合法 int 子类在 tasks 或 normalized orders 中出现时明确回 E1。
原生只用 `PIPE_SLOTS=1`、`project_once=False`；没有改变 C++、事件、同 tick
顺序、binary64 表达式或官方冻结源码。

## 3. 回退与错误

| 情况 | 行为 |
| --- | --- |
| 未显式启用 | 直接完整 E1，reason=`native-disabled` |
| 清单/库文件缺失、目标平台不符、NumPy 缺失、OS 加载失败 | 一次完整 E1，保留可审查 reason |
| 合法输入超原型数值/核数/整数等待域，或原生 status 6（舍入环境不支持） | 一次完整 E1；E1 本身出错照常传播，不重试 |
| 清单格式、未知 ABI、来源/产物 hash、编译参数、布局或导出符号不符 | 明确错误，不把未知后端记作成功 |
| 官方非法图/计划/配置 | 在原生加载前传播原异常类型/信息，不改成 Unsupported |
| native status 1/2/3/4/5/未知码，prepared 重复键/未知 pipe，其他内部错误 | `NativeExecutionError` 或原异常传播，不吞成成功回退 |

桥接相对原型还增加 signed-int64 等待/max_iter 与 int32 扁平邻接长度/offset
守卫，避免 NumPy/ctypes 窄化。`CandidateError` 不自动映射为官方 invalid，也不回退；
正式原始输入校验在它之前，若仍触发须按适配器/输入域问题调查。

每次显式评分的最坏路径需预留 **1 次完整 E1**，严格冻结 E0 入口为 0；
回退可以重复局部准备，因此有最多两轮准备成本。没有 fallback 前预算许可钩子、
硬墙钟/内存监督或进程取消保证。native 中断/崩溃仍可能没有结果，不能退款当 0。

## 4. 产物身份、ABI 和延期边界

清单形状由 `native_backend.discover_backend` 明确校验；没有随 PR 提供一个伪造
二进制或填了虚构 hash 的“可运行清单”。调用者只提供已经单独审阅的本地产物清单。
清单要求 version、固定 source_commit/kernel_sha256、ABI、target、build、binary、
binary_sha256；target 为精确 `sys.platform`、小写 `platform.machine()`、64 位、little。
binary 只能是清单目录内的文件名；Windows `.dll`、Linux `.so`、macOS `.dylib/.so`。

首版只接受声明为 clang/gcc 的严格配方，包含 `-std=c++17 -O3 -fno-fast-math
-ffp-contract=off`，其余参数来自源码中的显式小白名单。没有自动调用编译器，也不
支持未经审阅的 MSVC、fast-math、FMA 合并或架构专用优化配方。未来 Windows 编译
仍须解决 `replay` 导出；原 C++ 只有 extern C、没有 dllexport，本次未改 C++。

ABI 为 cdecl，使用 `ctypes.CDLL`，Input/Output 分别 176/56 字节，全部字段 offset
在加载前对照固定布局；符号随后绑定明确的 Input*/Output* → int 签名。
内核没有原生 ABI/version 查询，清单是来源/构建**声明**，hash 证明字节身份，
不能证明构建诚实、数值等价或依赖库身份。CDLL 会执行库构造器，因此只有经过审阅且
保持不变的产物/依赖才可供显式启用；本次没有运行 ABI 探针或验证 Windows DLL。

每次 score 重新 pack；内部 `Compiled` 仍是原型可变容器，只在调用中使用，不公开
prepared handle、不新增持久原生缓存。原有 E1 cache 可读，native-only 准备不提交
其 `_pending`；完整 E1 回退通过既有成功路径提交。所有调用继续用原实例锁。
完整 immutable handle、失效协议、原生完整 JSON、审计模式对外接口、pool/取消和
RSS/长跑不在本增量。原型 9-plan/64-candidate 与 33.7×仍为原作者报告，未复现。

## 5. 静态证据与下一步

本机 Windows NT 10.0.26200、Codex；系统 Python 3.13.9 仅用标准库 AST/文件/hash，
没有将其当作项目 `>=3.12,<3.13` 的运行环境。项目 Python/NumPy/编译器/ABI未实测。

可复做的静态命令（从仓库根目录）：

```text
python -B docs/a/e1/native-portability-lyx-20260924/static_check.py
git diff --check
git diff --name-status 03f02e79de4b4bd6f55241385664b154f4332454
```

静态检查读取文本、解析 AST、比较原始 Git blob；不 import 被测模块，不生成字节码，
不运行测试。测试源码与下一阶段调用/启动/时间/内存提案见 `validation-plan.json`，
`execution_authorized=false`；该文件不是本轮运行许可。

本轮实际静态结果：4 份新增源码/测试 AST 解析通过，7 个保留桥接节点与
原型 AST 相同，列出的 9 个现有 E1/原型文件与基线 Git blob 一致；19 个测试
方法仅列举、没有执行。暂存差异的 `git diff --cached --check` 通过。
对本次写入目录的磁盘检查未见 AppleDouble、`.DS_Store` 或 `__MACOSX`；
凭据模式/个人绝对路径扫描无匹配。Windows 上未调用 macOS `dot_clean`。
内部 fork 的最终只读静态复核未发现阻断问题，不能替代运行或独立盲审。

实际已读：任务卡/公共协议、固定 HANDOFF/README/replay_api/probe、batch.py、
test_batch.py、_official.py、CLI；评审另核官方校验链/C ABI，子代理读相关P1_BATCH。
未通读无关 Pro 新归档，未使用603b E2平台代码。没有改他人生产范围或公共依赖。
内部 fork 实现与静态评审继承本对话上下文，已在 Issue26 登记，不称盲审。

## 6. 验收状态

交付目标为最小源码增量和未运行测试，经 Draft PR 交原 Issue；不合并。
所有 Windows/macOS/Linux 加载、原生数值、完整 JSON 差分、性能、进程树/RSS、
冷启动及超时取消均未验证。E1 最终完整 JSON 零差分与 ≥3×E0 要求不变。
本轮目标 import/执行/编译/E0/E1/E2/worker/测试/安装均为 0，Actions 保持关闭。
