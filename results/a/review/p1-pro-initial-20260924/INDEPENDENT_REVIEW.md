# P1 Pro 初审：下界、资源单位及构造条件

审阅日期：2026-09-24 UTC。范围为本次 Pro 可见回答、研究报告及
`p1_phase_cut.py`、`lower_bounds_extensions.py` 的相关实现，与冻结官方
`161cdb35de11b0d174a5a0ca149aa36657af2abd` 的 Step1/2/3 和 P1 evaluator 对照。
所查官方文件相对该固定提交没有差异。

本审阅没有执行 solver、E0、E1、E2 或官方整图求解，没有修改 Pro 原附件。
Pro 报告自己的单测与实验不作为本机独立证明。本记录中的反例运行是纯小对象
中层模型核对，不是官方成绩；008 原图和官方微图验证由主会话另行记录。

## 结论和适用条件

### 完整链阻塞／拆链搬运下界

严格私人真链族的主不等式成立，尚未发现该范围内的反例：

`K * C >= W_M + sum(b_i for intact chains)`。

需要补明为何这个结论适用于任意合法 Task 混合，而不只是既有计划：私人组件
没有跨组件局部依赖；未切完整 spine 的末端或其 COPY_OUT 比本组件较早的输出
终端更深。第一次 reverse DFS 展开该组件时，从末端会访问整个计算 spine，
期间不能进入另一个私人组件。Step2 插入 MTE COPY 但保持原计算顺序，因此其
两次 M 之间没有其他 M。这段至少 `a_i+b_i+c_i` 的区间独占或阻塞 M Pipe。
不同 Task 也不能在同核重叠。将完整链的 M 工作替换为阻塞区间，再加拆链的 M
忙时，可得不等式。

沿依赖 spine 的 Task 标签不能 A→B→A，否则 Task 商图有环。因此拆链至少有一
个真实完整切口。单生产者、私人 tensor、无内部原始 COPY_OUT tap，保证切口
至少增加相应一写一读服务，且不同链的这些必要服务不重复。`D0+s*delta`
由此成立。对所有拆链数取最小值覆盖全部合法类别；同构二分交点及异构有理
凸组合的推导均合理。

不能直接推广到共享 tensor、删除 COPY 后消失的计算桥、一般 DAG，或未经核实
的 FIFO 连续性。008 是否通过这些结构条件由原图审计决定。

### 双阈值资源窗口

若每个必要 job 有释放下界 r、服务 d、完成后必要尾部 q，则被窗口选中的工作
必在 `[R, C-Q]` 内完成。由容量守恒得到
`C >= R+Q+ceil(sum(d)/capacity)`，对可抢占公平 DDR 同样成立。

Pro 必要 job 构造以保留依赖图为基础：输入选择最大尾部消费者所需的一个必需
COPY 实例，输出选择最大释放生产者所在 Task 的必需 COPY 实例。不同 tensor
对应不同实例；并未将候选 FIFO 加成普适约束。Pipe 容量为 K，DDR 为 1。
段树必须排除尚无激活 job 的 q 阈值，否则会产生空集合伪界。

证书核验只证明所报窗口不等式，不证明输入 job 本身对全部计划必要，也不证明
给定证书是最大窗口；图到 job 的正确性、图身份、容量仍需独立核实。

### DDR 单位和 noMEM 充分条件

官方将每条必要 COPY 的服务计为 `max(1, ceil(size/bandwidth))`；不能先将所有
字节求和再取整，不能将 DDR 总服务除以核数。最多 2K 条 MTE COPY 同时活跃，
数学公平模型中每请求服务率至少 `1/(2K)`，因而 `2K*d+1` 是保守延迟包络。
这是固定数学语义的结论，不是对任意大数、二进制浮点和 EPS 行为的形式验证。

对 P1 重建后的 Task，每种位置全部本地 tensor 大小之和不超过容量，是保守的
无 SPILL、无 MEMORY_REUSE 充分条件。P1 重建给本地 tensor 补齐生产／消费
边界；所有生产者先于消费者，无 spill 时每个 tensor 只分配一次。VIRGIN 额度
排在回收额度之前，总首次分配量不超过原额度，便无需消费旧来源额度。零字节
分配不改变论证。不能反过来把证书失败解释成一定 spill；也不能用低峰值替代
这个证书。该结论不自动扩展到任意手写、可能重复分配同一死 tensor 的扩展图。

## 发现：返程错位的 FIFO 优先前提不足

报告第 5.2 节（RESEARCH_NOTE.md:129）说 prefix 至少含 M→V，所以必先于
return；但识别器允许首 M 没有输入、只含一个 V。这时新 prefix 与旧 return
的终端 COPY_OUT 深度均可能是 2，ID 破平局可令旧 return 先访问。

纯小对象反例定义：两条同构私人链的计算 op ID 分别为 `[1,2,3]` 和
`[11,12,13]`，Pipe 为 M/V/M、cycles 为 1000/1500/1000。每个 op 各产出一个
60B UB tensor，ID 分别为 `[101,102,103]` 和 `[201,202,203]`；前两个输出交给
下一个 op，最后输出无计算消费者。首 M 无输入。所有 op 类型为 `Compute`。

`recognize` 通过；`encode(..., cores=1, packet=1, cut_count=2, whole_packet=2)`
生成 return-cut 方案。混合 Task 的中层 Step1 结果为：

- 完整序列 `[15,3,16,11,12,17]`，15/16/17 是模型边界 COPY；
- 计算顺序 `[3,11,12]`，M FIFO 为旧 C3→新 A11；
- 自有模型 Task 时长 3502 cycles；预期 A→C 顺序的理想 F(1,1) 为 2500。

这个反例运行用时约 0.00023 秒（模块导入后的纯对象计算），无官方调用。
差异来自 FIFO 顺序，不能当作真实 case 性能退化。`task_profile` / Uenv 使用
实际重算的 Step1 顺序，因此此发现没有推翻保守采用门禁或 cut-or-blocking
下界；受影响的是方向性论述和解析参数的适用条件。

最小修正：构造后检查混合 Task 的真实 M FIFO，或证明所有新 prefix 终端的
start_key 严格优先于旧 return；理想公式只在该顺序成立时使用。008 的六段 V
不直接属于本例的深度平局，仍应以原图核查。无需为这个局部条件缺口再开长时
Pro 研究。

## 独立可复用模块

本次将资源窗口独立实现于 `src/q1/resource_windows.py`，输入已认证必要 job 的
非负整数 `(r,d,q)` 与正整数容量，输出可 JSON 序列化的窗口证书。允许零服务
但保留必要事件的 r/q；拒绝 bool、浮点和负数。求界 O(J log J)、见证核验 O(J)，
不解析原图，不接入现有 lower_bounds，不引用 Pro 可执行附件。

测试见 `tests/q1/test_resource_windows.py`：固定种子小对象与独立朴素窗口枚举
对照，含空集合伪界、零服务、重复 job、容量取整、大整数、输入不变性、稳定
ties、证书篡改及“有效见证不等于全局最大”区别。具体本机命令及结果由下面的
实际测试记录补充。

### 本机测试记录

记录时间：2026-09-24 17:01:46 UTC。Python 3.12.13，macOS 27.0 arm64。

```text
.venv/bin/python -B -m unittest discover -s tests/q1 -p test_resource_windows.py -v
Ran 10 tests in 0.017s
OK
```

其中固定种子 `660724` 的 350 个小对象逐个与独立朴素阈值枚举比较；只运行
这一轮本模块测试，没有执行额外评估批次。源代码 SHA-256：

- `src/q1/resource_windows.py`：`0c6b1303bc2d4e1009573f0b02451dc80aa7bf7f67daf92da9df1a1415be0fa3`
- `tests/q1/test_resource_windows.py`：`9bd1bf0ae3cbc9e7ae30597d305178064a3fd044503bfb7d6995977271e2997c`

接口：`resource_window_bound(jobs, capacity)` 返回证书；
`verify_resource_window(jobs, capacity, certificate)` 独立线性核验。
容量由调用方再次传入，防止篡改证书时静默更换资源容量。
