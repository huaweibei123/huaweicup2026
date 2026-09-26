# v8 局部图后伪代码取材：冻结源码事实映射

仅供 Gemini 核对并重写正文；这里不是论文伪代码成稿，也不修改 v7。行号是各固定提交中相应源码文件的行号。v7 已有完整算法框：P1 `04-p1.md:131–146`、P2 `05-p2.md:128–144`、P3 `06-p3.md:184–209`。局部图后宜只解释图内机制，避免再复制全流程框。

## P1：分支 X/Y/J 局部图 `fig-p1-cuts`（v7 `04-p1.md:52–54`）

固定提交 `834d8c957538ee069c66aadac9509552a4cc69d7`。真实入口是 `src/q1/branch_refine.py::solve`（51–162）；构造器实际叫 `src/q1/branch_aid.py::construct`（316–480），**不是** `candidate` 函数。图内 X 是导出至 helper 的支路，Y 留在 donor，J 是仍留 donor 的汇合及后继；原 donor Task ID 被 Y 复用，J/X 各获新 ID（`branch_aid.py:424–431`）。`K=1` 先完整调用父流程，再由 `branch_refine.solve:75–78` 返回父方案；构造器内也有单核无 helper 的守卫（354–355）。

可供局部图旁压缩的事实步骤（14 条；按取材范围选用，不照搬全部）：

1. `branch_refine.solve` 先取得 `structural_refine.solve` 的父方案及诊断（55–60）。
2. 核数非 2–5、父方案哈希不符或父目标不可用时，返回父方案（75–88）。
3. 构造器验证父方案任务顺序、Task 余量；收缩 COPY 得算子依赖（332–355）。
4. `_wave_domain` 计算 Task DAG 高度并要求每核任务高度严格递增（`branch_aid.py:44–70`）。
5. 每波次提取已有任务；内部 packet 必须有唯一汇点且直接边与 COPY 收缩边一致（359–376）。
6. 按 `max(1, cycles)` 统计 Pipe 工作量，选总量最大的主导 Pipe（36–41、377–385）。
7. donor 当且仅当该 Pipe 的 `K × 本核工作量 > 全波次总工作量`；helper 用严格小于，并且两者必须在该波次已有 Task（386–391）。
8. `_witness` 在 donor 的桥树中找两条桥边输入的 join；选择出口前驱，构成 X、J、Y（190–241）。
9. 校验 X、Y、J 覆盖原 Task，且跨组内部边只准 X→J 或 Y→J（216–239）。
10. 对可导出 X 按工作量排序；逐个选择迁入后峰值、总负载、核号字典序最小的 helper（393–417）。
11. 仅全机 Pipe 峰值严格下降且新增 Task 不越 320 上限的波次入选（418–438）。
12. helper 在同波次先执行所收 X、再执行自身原 Task；donor 保留 Y 后接 J；检查覆盖、扩展 DAG 无环及任务顺序（440–467）。
13. `construct` 只返回未经评测的结构候选；不在此函数调用 E1/E0（316–321、472–480）。
14. wrapper 对非重复合法候选最多增加一次 E1 评分，仅目标二元组严格字典序优于父方案才采纳，否则回退父方案；请求已发而 worker 身份未知时调用数记为区间 `[0,1]`（`branch_refine.py:90–153`）。

v7 纠错：`04-p1.md:71` 的“显著超过核心平均工作量”暗示额外幅度阈值；源码只有严格 `>` 平均值，没有 1.2× 等显著性系数。`04-p1.md:46` 写“空闲核心”会误导：helper 必须在当前波次已有原 Task，完全空闲核不进入候选。`04-p1.md:135–145` 原框已覆盖父流程和评测，不宜在局部图后复写。图中 X/Y/J、Core 0/1 的 case_026 映射出自 v7 图件规划；本次只证实角色与执行顺序，未以固定源码复核这些具体算子号。

## P2：二核心局部超图割与 Load Guard 图 `fig:p2-local-cut`（v7 `05-p2.md:124`）

固定提交 `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`。局部图对应 `src/q2_nikolastarx/binary_hypercut.py::binary_hypercut`（144–195）和 `::load_guarded_cut`（198–259）；组装区域、Pipe caps 和接纳条件在 `gap_hyperrefine.py::refine`（46–145）。全流程去重、字节门槛、在线比选对应 `adaptive_hypergap_guarded.py::build`（14–108），不能把局部最小割当成最终 Makespan 优化器。超边集合宜写 `\mathcal E`，某边已固定触及的核心集合宜写 `F_e` 或 `fixed_cores(e)`，最大流数值宜写 `f_max`；`binary_hypercut.py:188–195` 中返回的 `flow` 是数值，`cost = offset + flow`。

可供局部图旁压缩的事实步骤（15 条）：

1. `refine` 要求 1–16 的 `region_width`、单算子 Task、每条 chain 原属单核（46–65）。
2. 建超图成本模型、原始 COPY 字节状态和每链 Pipe 工作量（66–83）。
3. 对每 Pipe 取所有核心初始负载峰值，并作为两核同值 caps（81–83）。
4. 依核心对与链顺序截取最多 16 条链；区外引脚核心变成 `fixed_cores`（87–108）。
5. 若区域初始连接成本已达连接下界，直接跳过该区域（109–116）。
6. `binary_hypercut` 校验单元与超边，计算有限弧容量和，令无限弧容量为 `finite_sum+1`（144–163）。
7. 对每边累加 `weight × (|fixed_cores|−1)` 作为 `offset`（164–168）。
8. 未固定触及 a 时建“任一 pin 在 a”辅助弧；未固定触及 b 时建对应 b 辅助弧（169–182）。
9. 对已锚定单元加无限容量源/汇弧，求最大流并由源侧可达性取 a/b 标签（183–191）。
10. 直接计算连接成本，核对 `cost == offset + flow`（192–195）。
11. `load_guarded_cut` 先核验原指派满足调用者提供的每 Pipe caps（198–240）。
12. 每轮求最小割；若无超 cap，返回标签、成本、负载及实际流调用次数（241–251）。
13. 若超 cap，取首个违规核/Pipe，选正工作量迁入链中该 Pipe 工作量最大的链，锚回初始核；最多 `|units|+1` 轮（242–259）。
14. 区域割成本不严格降低时不应用；严格降低时移动整链，并核对 COPY 字节差与割成本差一致（`gap_hyperrefine.py:118–138`）。
15. 整体 `build` 仅在细化前后原始 COPY 字节严格降低时尝试 retime 成 hypergap；保留原 gap，比对按序去重的完整方案，至多 3 个 oracle 请求，评分失败回 baseline（`adaptive_hypergap_guarded.py:41–108`）。

v7 纠错：`05-p2.md:102–110` 同时以 `F` 表示已固定核心**集合**和最大流**标量**，虽然括号解释了区别，图后相邻伪代码仍应改成两个不重名符号。`05-p2.md:135` 的“提取最多 16 条链”若被理解为全次求解总共只有一块区域则错误：源码对每核对、每个链顺序窗口各取最多 16 条（`gap_hyperrefine.py:87–94`）。局部受保护割最多 `w+1` 次流调用，并非整体在线 oracle 预算；后者在 `build:85–108` 最多 3 请求。

## P3：森林排序与候选决策图 `fig:p3-forest-decision`（v7 `06-p3.md:218`）

固定提交 `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`。排序/重建真实函数是 `src/q3/forest_memory_order.py::_original_tree`（11–137）、`::construct`（140–209）；候选裁决是真实 `src/q3/forest_solve.py::evaluate_candidates`（12–65）。连续 minimax 分割是**父层** `src/q3/pipeline_solve.py::evaluate_candidates:17–64` 的 `shared_pipeline.construct` 调用（23），其中 `K=1` 在 20–21 跳过；不能归到森林排序触发条件或在局部图后展开为森林步骤。

可供局部图旁压缩的事实步骤（14 条）：

1. `forest_solve.evaluate_candidates` 先调用 `witness_solve.evaluate_candidates` 取得 winner、calls、records（12–16）。
2. 若父层已用满 3 次 E0 请求，记录跳过并返回（17–20）。
3. `construct` 要求 1–5 核、至少两个分量、无 fanout、至少一个 join（`forest_memory_order.py:140–146`）。
4. `_original_tree` 核查各树、输出张量和边界结构；不支持则由父层捕获并保留 winner（11–137；`forest_solve.py:22–27`）。
5. `index.assignment(cores)` 决定分量归属，排序阶段不重新分核（`forest_memory_order.py:147–149`）。
6. 沿 `index.order` 自底向上算子节点处理，每节点子树按 `peak−retained` 降序、算子 ID 升序排序（151–157）。
7. 按当前子树次序递推 `frontier=max(frontier, live+peak[child])`，累积 `live+=retained[child]`（158–162）。
8. 当前输出尺寸写入 retained，peak 取 frontier 与 `live+own_output` 最大值（163–165）。
9. 对各树按上述子节点顺序做 DFS 后序，并检查覆盖（167–180）。
10. 每核各分量按最小算子 ID 排序后拼接；singleton Task ID 沿 `index.order` 赋值（182–191）。
11. 若候选与 winner 编码相同，记 duplicate 并不评测（`forest_solve.py:32–34`）。
12. 若完成时间认证下界 `lower >= winner.makespan`，记 bound_pruned；下界不支持则仅记录原因并继续（36–50）。
13. 剩余预算中增加一次 E0 请求；`EvaluationValidationError` 时拒绝并保留 winner（51–58）。
14. 评测成功后仅 Makespan **严格更小**才替换 winner；平局不按 DDR 字节破平（59–65）。

v7 纠错：`06-p3.md:204–205` 原框写“评测异常”泛称全部异常；此函数只显式捕获 `EvaluationValidationError`，不应将任意运行时异常描述为安全回退。`06-p3.md:137–138` 的连续 minimax 是 pipeline 父层，与 `forest_memory_order.construct` 无直接调用关系；若局部图后伪代码把它放入森林触发流程，属职责混淆。原框与局部图已有完整预算和守卫说明，局部图后宜只抽取排序和裁决必要步骤。
