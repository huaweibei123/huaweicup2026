# E2 Windows 首批独立复测

被测固定提交：`f4ee4756fc15c65ddc4256f3c73ff4efc89accfc`，PR42。测试者：`yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce`。这是公开新图与平台复现，不是盲审或封存验收；E1/E2/官方源码均未修改。

## 结论

- Windows 原生评分可运行，但所用 LLVM-MinGW 工具链必须额外部署 `libc++.dll`、`libunwind.dll`。单独执行原构建脚本成功后，DLL 依赖仍缺失，搜索全部透明回退 E1。补两个编译器运行库后实际 `route=native`，编译选项和源码不变。
- 新公开图 case006、4核、8划分×8调度、64不同方案，完整64次 E0 标注。E2 64/64 native，Makespan/全部搬运分项/跨 Task 流量值与类型零差分；中位/P95/最大相对误差均0。top8保留E0池内最好89187，遗憾0。
- 该混合池仅一次顺序计时：E1 6.567769s，E2 1.703997s，约3.8543×。包含实例与所有计划准备/评分，排除生成/解释器/文件I/O。E1仍内部构造full诊断，这不是相同原生接口对照，也未达10×，不能据此宣布联合验收通过。
- 8项现有测试在运行库齐备后 **6通过、1错误、1失败**。RSS回收失效和极短超时不稳定有独立最小反例。3轮CLI smoke均通过结果/Trace值相等、日志字节相等及`ok-invalid-ok`继续；前两轮search是fallback，第三轮成功记录为native。

## 六字段交付

1. **目标**：在本人Windows机器补充验证P1 E2固定交付，回传平台失败与一个新公开图池；不替代LYX既定测试或队长验收。
2. **输入**：上述被测SHA、冻结E0 code hash `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`、case006及原config。`scripts/a_materials.py --extract`核验114文件/100case通过。计划种子9240600，分组种子+0..7，调度种子+100..163；每块40–80操作。全输入hash见`case006-mixed/protocol.json`，计划和64份完整E0 JSON gzip均保留。
3. **输出**：本目录、`research/a/review/e2_windows_20260924/`复现脚本。`preflight/`保留无编译器/缺库阶段，`native/`保留已编译但运行库未部署的失败，`provisioned/`保留完整运行库后的测试；不覆盖失败记录。两份原生阶段命令的原始私有日志在Git外，共享日志保留路径脱敏和原始hash；preflight初期只保留脱敏日志，不宣称存在原始stderr副本。
4. **限制**：正式池顺序单进程/1worker、64新候选，功能测试按原测试定义最多2worker且不与性能运行并发。只用本人CPU，未借队长算力、不改系统PATH/锁文件/官方材料/Q2工作区。预算30分钟检查点，测试在该窗口内完成；候选池总wall 28.280163s。未做P2/P3、完整发布矩阵/封存、多次性能统计、硬RSS上限或新原生E1对照。Python测试器为计数包装公开调用，未改被测源码；两个平台问题另用无包装最小probe确认。
5. **验收证据**：`case006-mixed/summary.json`、`provisioned/unittest.json`、`platform-probe.json`、各CLI的`receipt.json`；已知Windows问题未关闭，不标done。共享附件哈希见`ARTIFACT_MANIFEST.json`，不是源码正确性证明。
6. **下一步/截止**：本检查点收束，不继续扩大E0调用。核心开发者处理下述反例及Windows运行库说明；修复后由队长安排定点回归，LYX测试职责继续保留。当前没有新硬截止。

## 平台反例

### RSS 回收配置静默不起作用

`E2BatchEvaluator(simple_graph(), workers=1, recycle_peak_rss_bytes=1)`连续两请求都返回`worker_peak_rss_bytes=null`，两个worker_pid相同，没有`recycle_after_response`。`pool.py`仅尝试`resource.getrusage`，Windows无该模块时返回None；后续条件跳过回收。这不是硬内存上限的测试，而是已提供的观测回收选项在Windows静默失效。现有`test_pool_order_error_recycling_and_cleanup`也报`KeyError: recycle_after_response`。

### 极短 timeout 检查在 Windows 不稳定

原测试`timeout_seconds=1e-12`首次有时返回ok而非timeout。无包装probe连续8请求实际为`timeout, ok, ok, timeout, timeout, ok, ok, ok`；全部已关闭，无在途worker。当前Python3.12.14的`time.monotonic`实现是GetTickCount64、分辨率0.015625s；池用它累计deadline，可在同tick内得到elapsed=0。应评估使用高分辨率时钟/明确最小可支持timeout；本证据只证明极短预算与测试不稳定，**未测得秒级超时失效，也不外推到正常60秒预算**。

最小图、计划、config、原始记录与时钟信息全在`platform-probe.json`。单独运行：

```powershell
uv run python research/a/review/e2_windows_20260924/platform_probe.py --output results/new-platform-probe.json
```

### 编译成功不等于原生库可加载

未部署运行库时DLL已存在，但`ctypes.CDLL`抛`FileNotFoundError (or one of its dependencies)`，返回明确`e1_fallback`；DLL导入表含`libc++.dll`和`libunwind.dll`。补齐这两个同版本工具链文件后，同一简单方案变成native、makespan保持104。完整对照和DLL hash在`runtime-deployment.json`。这是部署要求；未为了通过测试重写源码或改变浮点编译选项。

## 调用与成本台账

直接未修改E0调用总数 **488**，其中436成功、52预期/已记录异常。它们与E1回退分开统计：

| 阶段 | 直接E0 | 成功/异常 | E1/E2补充说明 |
|---|---:|---:|---|
| 缺编译器preflight | 1 | 1/0 | CLI的1次官方真值；RSS功能测试0次E0，8请求走E1 fallback；search CLI另3次fallback及full CLI委托E1 |
| 编译成功但未部署运行库 | 114 | 91/23 | 计数测试113次E0 + CLI1次；测试parent113次fallback、pool9次fallback/1次timeout；85个断言失败包含80个seed子测试，不是85次独立测试 |
| 部署运行库后 | 309 | 280/29 | 计数测试308次E0 + CLI1次；parent274native/33fallback/1full，pool8native/1fallback；仅6/8测试通过 |
| 新case006池 | 64 | 64/0 | 另64次E1基线、64次E2 native；没有调用最终额外E0确认，因为所有64真值已取得 |
| 部署/平台诊断 | 0 | 0/0 | 部署前后2次E2、一次终端诊断fallback；无包装平台10请求（7native、3timeout） |

超时/杀进程在途内部是否已开始fallback无法据父端记录证明，保持未知，不算成功/非法，也不补造次数。第一次缺库RSS测试8条请求数按固定测试执行路径核对；后两套测试直接E0与父端完成路由有`CALL_COUNTS`实测计数。没有重复运行64正式池，没有把失败尝试从账本删除。完整CLI由E1委托执行不称直接E0；自动fallback同理。

## 工具链与复现

Windows x64，uv locked Python3.12.14/NumPy2.5.3。便携工具链来自官方`mstorsjo/llvm-mingw` release **20260922** 的`llvm-mingw-20260922-ucrt-x86_64.zip`，190725905字节；实测SHA256与GitHub release digest一致：`e3ad77d117a4bea19a7a3b333341824d79a5a371004a10e25b8504e7b3047666`。Clang23.1.2，target x86_64-w64-windows-gnu。运行库只部署在本独立worktree的忽略二进制目录，二进制不提交。

```powershell
uv sync --locked
uv run python scripts/a_materials.py --extract
# <toolchain-bin> 替换为本人便携LLVM-MinGW目录
uv run python -m research.a.e2_search.build_native --compiler <toolchain-bin>/x86_64-w64-mingw32-clang++.exe
uv run python research/a/review/e2_windows_20260924/deploy_runtime.py --bin <toolchain-bin> --output results/new-runtime.json
uv run python research/a/review/e2_windows_20260924/counted_suite.py
uv run python -m research.a.e2_search.cli_probe --output results/new-cli
uv run python research/a/review/e2_windows_20260924/independent_pool.py --output results/new-case006
```

初次缺库环境用于重现部署问题；若运行库已存在，`deploy_runtime.py`拒绝覆盖它们。数据与计时结果不得由重复运行覆盖。现有8项测试也可不包装地使用原`unittest discover`命令；计数包装器仅供此报告的调用台账，timing不取自测试包装器。
