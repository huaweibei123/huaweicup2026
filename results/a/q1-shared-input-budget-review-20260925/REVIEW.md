# shared_input_budget 固定版本独立审查

**结论：未发现阻塞性实现错误；没有必须先修的代码项。** 真实两键合同、先选 active 核数后仅一次 bounded 构造、窗口增广 DAG、整组件同核不变量和元数据/最终计划的一致性检查均通过本次审查。未重新评分，也未把既有三格双改善视为上述证明的替代。

目标提交：`288dd520caa5c7baaa1413e4021eb2d4221b6e66`。仅只读审查 `src/q1/shared_input_budget.py`、对应10项 tests/docs，及其冻结 bounded/tree_frontier/component_pack 依赖和相关官方结构验证源码。执行 checkout 虽已推进到归档提交，但导入源码、测试、文档和配置在执行前后与指定提交逐字节核对，哈希见 [result.json](result.json)。未修改作者工作树。

## 合同与只构造一次

- `construct:259–264` 先拒绝非法 core 域及非正整数预算，`_view:30` 使用官方原图校验；非空 compute 校验保留。原图、compute IDs 和原 op 插入次序不修改。
- 非激活分支 `:271–275` 仅调用一次 `bounded(graph,K)`。激活分支 `:279–284` 对 `a=1..K` 只计算结构元数据，选定 a 后调用一次 `bounded(graph,a)`。`_configuration` 不调用 constructor、derive 或 Step1/2/3；没有藏入 K 次官方编译或评分。
- `_refine:233–254` 每个旧 Task 第一窗沿用旧 ID，新 ID 从全体旧 ID 最大值之后递增，不会覆盖尚未遍历的旧 Task。按旧 core 顺序将其替换成窗口链，最后补空核至请求 K 条 schedule。每个 compute 仍恰好属于一个 Task；CLI 输出只有 `node_to_subgraph`、`core_schedules`，已有文件不覆盖。
- 只构造一次不等于静态元数据免费：最多K个配置的在线工作、选中方案构造与最终验证均应计入求解端到端时间。文档已有此界限。

## 窗口不会引入环或远端数据边

激活分支要求原 COPY 收缩弱组件数 `C>=K`；任何候选 active 数 `a<=K`，故 `C>=a`。冻结 `tree_frontier` 因组件足够而保持 `component_pack`，不会在选小核数后突然进入把一个组件切到不同 core 的 frontier 路由。这是元数据镜像与无跨核边证明的关键前提。

component_pack 将完整弱组件放入某 core；bounded 只在内部独立组件之间进行软切块。不同旧 Task 因而没有 compute 数据依赖。同一组件始终属于同核，即使经窗口划分也不迁核。

`_view` 的 depth 来自官方 COPY 收缩 DAG：每条收缩边 `u→v` 都有 `depth(v)>depth(u)`。`_windows` 合并的是按 depth 升序的连续层，绝不把同一层拆成顺序相冲突的小窗。因此旧 Task 内每条跨窗数据边都沿窗口链前向。跨旧 Task 只有原 core 顺序；整块位置不变。缩回旧 Task 后的增广图仍是原合法基底，不能产生新环。共享外部 tensor 只影响 COPY 复用，不会凭空产生 compute 间数据边。

代码最后还检查官方增广 Task DAG，以及每条最终数据依赖的源/目的 core 相同（`:286–294`）。因此这里读取1000-cycle cross gate配置但不累计，是因为此路线没有远端数据依赖，并非漏掉官方等待。每核相邻窗口/块的100-cycle等待按最终 Task 数计入代理。

## 预算失败与边界

- 单层超过 input budget 不强行拆分，统计 `windows_over_input_budget`。这是公开的切窗启发式预算，既不是 L1/UB 容量上限，也不是输出非法条件。
- 前部或中间没有 external input 的层不会丢节点，也不改变 depth 单调性。内部 tensor 及 COPY 桥依赖通过收缩 DAG 保留；external 是“无直接 compute producer”的统计定义，不能误称纯权重。
- 某个旧 Task 生成窗数超过 `max_phases` 时，只将该旧 Task 恢复完整一个块。没有跨旧 Task 合并，也没有保留不完整的前几窗。元数据及 `_refine` 调同一窗口逻辑，回退后重新统计超预算、窗口数和 gates。
- `max_phases`、input budget 等非法域先报错，不构造半成品；末尾 metadata drift 断言不是静默质量回退。既有 docs 没有承诺质量单调或容量安全。

## 元数据是否真正对应最终计划

逐项比对了冻结实现，当前一致：

1. `_view:88–96` 的组件 work、排序键与 `component_pack` 完全相同；`_configuration:134–142` 的 `max load / sum load / node count / core ID` 装箱 tie-break 也相同。
2. 基底超过4096 compute ops时，两边都对独立组件按 `(-len,min ID)` 排序，以1024上限 first-fit；不可分的大组件保留。不超过4096时都不软切块。
3. 元数据节点遍历顺序可以与真实基底不同，但 `_windows` 的边界只取决于 depth 层和该层输入集合，所以各窗的成员集合一致。第一窗 Task ID 不影响该集合；最终 ID 无须等于临时 metadata label。
4. 配置中的 `owner=(core,block,window)` 对应最终 Task 分区。对 tensor 的输入 COPY 数 `|consumer_tasks−producer_tasks|` 及每 producer Task 的输出条件，等价于官方 `_build_scene_a_tasks` 的逐 Task boundary 条件；高扇出、多 producer、原 COPY_OUT 均没有压成固定两倍载荷。
5. service 按每个 COPY 的 `max(1,ceil(bytes/60))` 计，0字节 COPY仍记1周期。按窗口先取各 Pipe work 最大值再按 core 相加，避免先合并互补 Pipe 而漏算窗口串行化。

**零 cycles 的特殊点：**组件装箱所用 raw cycles 刻意复刻冻结 component_pack；窗口工作代理使用 `max(1,cycles)`。二者用途不同，此版本没有因此 metadata drift。不能只把 `_view` 改成 max1 而保留旧底座 raw-cycle 排序，否则可能让元数据描述的是另一种装箱。

新增独立 oracle 直接遍历**最终 plan 的每个 Task**及原 tensor incidence，重算13类统计并逐一对照 chosen configuration：COPY字节、逐 COPY服务、external输入复制/重复、Task数、核 compute数、最大输入并集、超预算数、逐核窗口工作、compute+gate成本、最终cost、基底块数、阶段预算回退数。它不调用官方 Task编译，也不复用作者 `_configuration` 的装箱或边界统计函数。

|新增见证|最终 Task数|总 COPY字节|COPY服务|特定核对|
|---|---:|---:|---:|---|
|4100个零cycles独立节点、1 active核、共享600000B输入|5|3,000,000|50,000|实际4096/1024软块路径；有效compute工作4100|
|多个compute生产者、跨三窗、0字节原COPY_OUT|3|314|14|多producer输出次数及0字节服务|
|空输入层、COPY桥、2 active核|3|556|14|无远端数据边；单层超预算如实记录|
|同上，max_phases=1|2|428|10|仅超窗旧块回退；统计跟随最终分区|

### 唯一非阻塞维护建议

运行时 drift guard 目前只比较每核 Task 数。对当前固定底座，代码对照与上述更强合成核对没有发现差异；但相同 Task 数并不普遍证明成员、输入集合或 COPY 数一致。以后若改 component_pack 的排序、zero-cycle处理、chunk阈值或 first-fit规则，应同步更新镜像元数据并保留这个独立 plan oracle，或增加分区成员签名核对。无需为当前固定版本热改或重跑已封存成绩。

## 实际验证范围

原10项测试 + 新增3项独立测试，**13/13通过**。新增测试含4次方法调用，每次 monkeypatch 回读 `bounded_construct` 恰好一次，且 core 参数等于选中的 active 核数。原测试另覆盖两键 CLI、拒绝覆盖、回退单次调用、只有一个active核时继续切窗。

复现：在本 review 工作树执行 `python3 -B results/a/q1-shared-input-budget-review-20260925/probe.py ../q1-shared-input-release-20260925`，最后参数为只读源码 checkout。执行前后校验固定源码字节，脚本/输入源码哈希随结果保存。

本次 **0真实图构造、0 Task编译、0 E0/E1/E2**；调用了合成图 constructor，不能写成全部软件构造次数为零。未读取或重跑044/046/090真实成绩，没有新增性能/墙钟结论。
