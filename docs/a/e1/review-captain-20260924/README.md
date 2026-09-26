# PR71 固定版本静态复核：可接受骨架，三个小范围修订项

2026-09-24；复核 session `nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`。

**结论：默认 E1/CLI 未被替换，显式接入和一次回退的总体控制流可接受；建议完成下列三项
局部修订后再提交下一阶段运行提案。当前不提升为原生后端/Windows/完整 E1 验收通过。**
F1 是声明中的错误分类未实现完整；F2 是公开类型契约遗漏；F3 是回归断言弱于完整类型一致要求。
没有发现需要重写评估器、改 C++ 或扩大生产写范围的理由。三个问题均来自固定源码推导，未执行反例。

## 1. 任务与上下文边界

只复核 [PR71](https://github.com/huaweibei123/huaweicup2026/pull/71) 的
`0e0cdc656ae095f0d1f7cfe11347a0b3f997d9ac`，父 `03f02e79de4b4bd6f55241385664b154f4332454`。
任务卡为 `f5342694e256de22a081369086de20253925d8da:tasks/a/E1-NATIVE-PORTABILITY-LYX.md`；
作者交付为 [Issue15#5807146700](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5807146700)。
已回读 PR 作者 lyx0217、draft、HEAD/base 及七个新增文件，完整阅读七文件。
本专项参与过原型和先前 E1/E2 研发，继承上下文，**不是盲审**；没有重新导入全部 Pro 历史。
LYX 保留 `src/eval_exact/` 正式单写权，本专项仅在自己的隔离分支写本报告与静态证据。

## 2. 需交原作者修订的发现

### F1 / P2：清单 target 类型非法被当作后端不可用

位置：[native_backend.py:85–92](https://github.com/huaweibei123/huaweicup2026/blob/0e0cdc656ae095f0d1f7cfe11347a0b3f997d9ac/src/eval_exact/native_backend.py#L85)，
回退落点 [native.py:78–79](https://github.com/huaweibei123/huaweicup2026/blob/0e0cdc656ae095f0d1f7cfe11347a0b3f997d9ac/src/eval_exact/native.py#L78)。

静态反例：将其测试用合法 manifest 的 `target.machine` 改成 `null`、数字或列表，其他字段保持。
字典键集合和 pointer_bits/byteorder 检查仍通过；与 host 字典不相等，抛
`BackendUnavailable("target-mismatch")`，随后 score 返回一次完整 E1 的成功分数。
这违反 discover 文档“malformed fail closed”和交接“清单格式错误明确报错”的分类约定；
它不会加载未知 DLL，但会把坏清单隐藏成可正常回退的外平台后端，影响错误诊断及费用原因。

最小修订：在 host 比较前验证 platform/machine 的字段类型、非空等清单约定；
格式非法抛 BackendManifestError，格式有效但不同平台继续 BackendUnavailable。
增加对应 discovery/score mock 断言：错误不调用 CDLL、不调用完整 E1；保留合法外平台回退案例。
不要求更换加载器或加入新平台支持。

### F2 / P2：ScoreResult 的整数声明未覆盖合法 E1 回退域

位置：[native.py:14–18、36–38](https://github.com/huaweibei123/huaweicup2026/blob/0e0cdc656ae095f0d1f7cfe11347a0b3f997d9ac/src/eval_exact/native.py#L14)。

`makespan: int` 与实际 `_e1_score` 直接返回 E1 值不完全一致。冻结
`evaluation_validation.py:15–18,106–111` 允许非负有限 float 等待；
`_scene_a.py:141–152,258–272,317` 的 release、now 与最终 makespan 没有整数化。
对于没有 DDR 的两 Task 同核串行合法结构，非整数 same_core_wait 可以留下非整数 makespan。
默认 score 以及明确 Unsupported 回退都会返回该值。当前实现**没有截断数值**，问题是公开
dataclass 类型承诺错误，调用方据此做类型检查/序列化或整数化会得到错误预期。

最小修订：把声明和接口说明改为真实支持的 `int | float`，保留 E1 原类型/数值；不能用 int()
迁就注解。用 mock 的完整 E1 浮点返回值检查无转换，可不增加完整评价费用；未来真实浮点
等待案例另按固定矩阵执行。原生支持域仍只声明整数等待和整数原生 makespan。

### F3 / P2：完整结果回归未检查类型和 binary64 身份

位置：[test_native_portability.py:383–389](https://github.com/huaweibei123/huaweicup2026/blob/0e0cdc656ae095f0d1f7cfe11347a0b3f997d9ac/tests/eval_exact/test_native_portability.py#L383)。

唯一真实完整 E1/E0 对比使用 `assertEqual` 比较嵌套字典；例如某个整数叶子变为等值 float，
普通 Python equality 仍可通过，`0.0` 与 `-0.0` 也无法区分。后续三条 score 断言亦只看值。
因此即使测试未来通过，也只能支持这个小输入的值相等，不能支持任务的完整类型/浮点身份回归。
这不是声称当前 full E1 已有数值差异。

最小修订：对**已经计算得到**的 expected/actual 做递归类型敏感比较，float 比较 hex 表示，
并用人工构造的值确认 comparator 会拒绝类型漂移。可参考原 `tests/eval_exact/test_batch.py:16–29`
的语义，避免为了复用而发现/执行整个旧测试套件。更换断言无需增加四次 E1/一次 E0；
如新增真实用例，则必须同步修改计数与验证提案。

## 3. 可接受的静态边界与仍未证明的内容

| 项目 | 本轮可确认 | 不能据此宣称 |
| --- | --- | --- |
| 默认及完整 E1 | 七文件均为新增；旧包导出、P1Evaluator、完整/批接口、CLI、E0/配置/C++/pool 的 Git 源码不变。新类只增加 score，evaluate 系列继承原实现 | 当前项目运行回归或完整 E1 发布已通过 |
| 入口校验 | capacity=dict → 官方参数检查 → 原 _build_tasks；原图/计划/联合环和局部编译在 loader 前。RLock 支持回退重入 | 所有合法/非法 Python 类型已逐例覆盖 |
| 一次回退 | native-disabled、BackendUnavailable、bridge.Unsupported 各控制流最多一次 _e1_score→evaluate；返回后不继续 native；E1 异常不被重试 | 从未发生局部重复准备或回退免费；无预算回调，仍应预留完整 E1×1 |
| 其他错误 | ManifestError、CandidateError、NativeExecutionError 与意外异常传播；status6 才 Unsupported，其他非零原生码不变成成功回退 | 原生异常自动具有官方输入错误文本；进程崩溃可被 Python 捕获 |
| 内部状态 | finally 清 _pending，native-only 不提交新 E1 缓存；已有缓存命中仍能更新命中计数/LRU顺序 | 缓存状态完全无变化、Compiled 已不可变，或具备新持久 handle |
| 原型桥接 | 七个保留节点 AST 相同；C++ 与原型 Python 的固定 SHA 与清单一致；packing 顺序/排序秩、同 tick 内核和 binary64 表达式未改；project_once=False | 跨平台数值等价的证明，或旧 macOS 成绩可移植到新 loader |
| 窄化与资源 | n/t/扁平邻接 offset、int64 wait/max_iter、1–128 核及时间上界检查在窄化/调用前；新增守卫拒绝不截断 | 全域形式化安全证明、非法手工 Compiled 的内存安全、RSS硬上限 |
| 加载边界 | 显式清单，无自动编译/邻库搜寻；SHA、cdecl ctypes 布局及 replay 符号检查；CDLL OSError 分类为 unavailable | 清单是真实构建证明、依赖库身份已验证、CTypes布局证明真实C布局 |

加载器导入 ctypes 本身可能加载 Python 的 `_ctypes` 扩展；“不加载动态库”应理解/表述为
不加载 **replay 后端产物**，不能推广为零系统动态库。README 已将 NumPy 运行时扩展与 replay
加载预算分开，下一阶段也应保持这一区分。调用方必须保持已审阅库及其依赖不变；该实现不
提供对不可信/并发替换产物的沙箱或原生 ABI 查询，这些限制已在交付声明，不新增安全承诺。

Windows 仍没有已审阅 DLL、真实 ABI/数值结果；原 C++ 只有 extern C，无 dllexport，
实际导出/工具链与依赖仍须另审。平台名字/64位little和白名单flags是声明检查；本轮不把
clang/gcc 字符串当实际编译器身份，不支持未审 MSVC。没有拿旧 .so 冒充 Windows 产物。

## 4. 测试可证伪性与费用逐项核算

19个方法分为：路由8、manifest5、桥接4、极小集成2。全文读完，未运行。
路由的单次回退/异常传播/清 pending，清单未知 ABI/hash/配方/符号，桥接窄化/status
及重复候选等断言有实际反证能力；native 成功路由被 mock，不能支持真实原生结果正确。
manifest 的 CDLL、桥接 replay 也是 mock；不能用其成功证明 Windows ABI。

| 真实完整评价位置 | 上界 | 说明 |
| --- | --- | --- |
| 测试385行 oracle.evaluate_scene_a | E0×1 | 极小三操作图的完整参照 |
| 测试388行 disabled.evaluate | E1×1 | 完整结果回归 |
| 测试389行 disabled.score | E1×1 | 默认关闭回退 |
| 测试394行 missing.score | E1×1 | loader 被 mock 为 unavailable，完整 E1 真实执行 |
| 测试403行 unsupported.score | E1×1 | pack 被 mock 为 Unsupported，完整 E1 真实执行 |
| 其他方法/非法输入检查 | 完整E0/E1×0 | routing evaluate、full API内部 evaluate_scene_a、CDLL/replay 均在相应 mock 范围；两非法输入在全局评分前拒绝 |

因此当前固定文件一次发现且无重跑的提案 **E0≤1、完整E1≤4** 与源码吻合；failfast可减少
实际次数，不能事后重用未明确核销额度。加载官方 Python bundle、哈希、构造器、局部编译
与 NumPy 扩展仍花时间/内存，但不是额外完整评分。后端真实 replay 库加载0、worker/编译0
也与该固定测试源码相符。一个逻辑 Python 入口不等于一个 OS 进程或零库线程。

下一步最小范围：先由 LYX 修 F1–F3，补 malformed target/浮点返回/严格比较的 mock 检查；
建议再补 CDLL 抛 OSError→unavailable 的分支检查，避免只测 mocked loader、未测加载层转换。
不必立即扩大正式图样本。然后固定新提交、解释器/依赖、外部限时/内存/进程树和新输出目录，
由调度按新提案决定执行。当前JSON批准字段false，120/130/600秒及512MiB只是提案，不能当
已有监督实现。无新增运行授权；该测试没有覆盖后续真实 native 算术和性能。

真实 native 下一阶段的三操作纯计算样本只适合 ABI/路由冒烟；若要声称 DDR/binary64/事件序
可移植，需另加很小的 DDR 竞争与同tick/整数取整反例，并核时间线而非只看 Makespan。
增加病例须重算原生请求/E0/E1上界，不把旧9-plan/64-candidate自动重跑或用于代签。

## 5. 本轮实际证据与局限

自写 [static_audit.py](static_audit.py) 只读取固定 Git blobs，解析 AST/JSON 与计算 hash；
实际命令为 `python3 -B docs/a/e1/review-captain-20260924/static_audit.py`，
产物 [static-evidence.json](static-evidence.json)。系统 Python3.14.5 用于标准库静态分析，
不是项目 Python3.12 运行验证。五份 Python 文本 AST通过（包括作者静态脚本但未执行它）、
七节点AST一致、七新增文件及父提交核对、19测试列举、JSON批准false、diff --check通过。
另核 prototype Python/C++ 原始 Git blob SHA，补读batch/_scene_a/官方参数与图校验/CLI/probe相关段。

**目标 import、运行、--help、编译、测试、worker、E0/E1/E2、算法实验均为0。**
没有执行作者测试/静态脚本，没有加载或 unpickle 原生/实验附件，没有测试或改写 Fang 驱动。
源码审查和 AST/hash 不是真实执行、平台证明或性能测量；未提出加速倍数。

## 6. 固定交接与停止

交本隔离分支的固定报告到原 Issue15，LYX继续单写修订，调度统一任务状态及镜像同步。
本专项完成静态检查点后停止；E2 helper a21f保持停写。
已知 Fang 协调在5807193465批准其48b12684固定 CLI 新窗口（15例/8潜在E0/1800秒），
这里仅转述调度给出的旁路状态，未核其实时开工；本报告不撤销或接管该窗口、不追加试验。
