# 容量窗口独立审计

审计对象为 `eb00b1c25fe92cf8b9f835a4f3e8a63ab20a90e8` 的 `capacity_window.py`、`CAPACITY_WINDOW.md` 和 6 项原测试，基础构造为 `e64723bdf99669c44f76d8e90ab0379a8578522e`，官方语义为 `45f647b395b84e9569f418fd33d62c2b8eb4d190`。2026-09-24 16:59:44 UTC 核对前三份工作树文件与 Git 固定字节一致。

**结论：在实现声明的逐核适用条件内，闭区间容量证书足以排除冻结 Step2 的 spill；未发现反例。** 证明依赖下面的实际构造语义，不能由几项小例代替。重分量改走 packet 的支路没有此证书，无法认证后保留旧顺序的核也没有此证书。本次没有调用 solver CLI、E0/E1/E2、Step2、`_build_scene_b_tasks`，没有构造官方 100 图或增加成绩。

## 逐桶上界为何覆盖真实 Step2 输入

1. **计入的本地 tensor 是完整的。** 冻结 P2 `_build_scene_b_tasks` 只为存在 eligible 生产者或消费者的 tensor 建本地副本；这正是 `footprint` 扫描的 compute 输入、输出并集。原始 DDR tensor 的本地副本转为 UB，代码和上界都采用该归属。新加 COPY 使用的 DDR backing 仍在 DDR，不计入 L1/UB。没有 eligible 触及的孤立 tensor、仅原始 COPY 使用的 backing 不进入该核本地池，漏掉它们不是少算池驻留。
2. **新 COPY 不延伸到触及闭区间之外。** P2 图输入 COPY_IN 放到该核首个消费子图；图输出 COPY_OUT 放到生产子图。每操作一个子图、唯一原始 producer 时，生产子图唯一。输出也有后续 compute 消费者时，输出 COPY 仍在生产桶，但该 tensor 一直计到最后消费桶。输入 COPY 的瞬态驻留和输出 COPY 的瞬态驻留都被对应桶的闭区间包含。
3. **同桶输入、输出必须共存。** Step2 为本步首次触及的 buffer 分配后先检查容量，执行完成才释放末次触及者；仅触及一次的 buffer 也必须参加瞬态峰值。`footprint` 对桶先加所有首次 tensor，记录峰值，再减全部末次 tensor，保守地把同桶各种 COPY/compute 触及同时计算。这避免了“先释放输入再分配输出”的错误低估。重复输入边由集合去重，与 Step2 每 step 去重对应。
4. **这些支路不会生成遗漏的跨核中间 buffer。** 一个 eligible producer 和该 tensor 的任意 eligible consumer 必然属于同一个 COPY 收缩后的弱连通分量；直接 eligible op-op 边也不能跨弱分量。共享支路完整分量同核，因此不存在跨核中间 tensor 或直接边的附加 UB buffer。经过原始 COPY 链的 eligible 因果仍使两端归为同一弱分量；不能把它拆成相互独立作业来证明窗口。本证书不需要把该收缩因果误称为 P2 物理依赖完全相同。

由 1–4，对任意桶内合法次序，真实 Step2 在任一事件的池驻留量不超过该桶的全部闭区间驻留和。无需假设 COPY_IN 的实际完成时间或 DDR 带宽份额。

## 从单作业峰值到 S + W P

对一个核的全部作业，`external_by_job` 是该作业使用且没有 eligible producer 的 tensor 集合；每个作业内先去重，再跨作业计数。被至少两个作业消费的 tensor 按大小在所属池一次性预留为 S，不因它在某个作业内多次使用重复预留。共享 L1 与共享原 DDR→UB 分开计池。同一 ID 不会同时属于两个池，因为原始 tensor 只有一个 `pos`。

剩下的 tensor 只属于一个作业。若有 eligible producer，它与全部 eligible consumers 已在同一弱分量；若没有 producer 且仅一个作业使用，也只在该作业的首末桶之间驻留。每个作业内顺序由 `components[j]` 固定，`pipe_window` 只交错各作业，不改变内部顺序，因此私有峰值 P_j 是该作业任意前缀位置的上界。分别对两个池取 P = max_j P_j，不要求两个池的最大值由同一作业达到。

在输出优先序的任意前缀，最多 W 个作业已开始而未写完。新作业只在旧作业的最后 compute 桶写完后入窗；其最后输出 COPY 也属于已写完的桶。于是私有驻留总和≤W P，加共享预留 S 得到证书。这里的“写完”指 Step2 访问优先序的桶边界，**不是最终多 Pipe 执行已完成**。从该字节证书不能直接推导最终时间线同时开放作业数、DDR 时延或最优 Makespan。

此外，实现还对完整生成优先序重新计算实际静态桶闭区间峰值。只要该峰值≤capacity，即可直接用逐桶上界和 Step2 的 alloc→检查→execute→free 作归纳：初始池为空，每次分配后的驻留不越界，spill 循环不进入。该检查不是官方模拟器，也不证明 Step3 和最终 P2 一定无其他合法性问题；最终 E0 仍须保留。

## 守卫与不能扩张的结论

- 原始 producer 唯一性由 `TensorIndex` 明确拒绝多 producer 保证；原始 `logical_tid` 别名使容量重排回退。L1/UB 容量必须为非负整数，拒绝 bool 和负数。
- 无 W≥1 时保持旧计划，该核可能仍 spill。`selected="capacity_window"` 只表示进入该路线，**不能单独当作整个计划的无 spill 标记**。必须逐个非空核确认 `window≥1`，并存在不超容量的 `bucket_footprint_bytes`；空核自然不占池。某核拒绝不影响其他核获得证书，但整计划不能因此概括为已认证。
- `heavy_component_packet_override` 在共享组原路线下按全图瓶颈 pipe 总工作/k 的向上取整识别重分量，复用 packet 分解，可改变分核。它在容量重排前返回，明确没有容量证书。本审计用零容量小例验证该支路仍构造计划并声明 `no spill certificate`；不能把这个计划当作零容量可执行结果。
- 资源词、原本 packet 路线通过直接返回基础计划保持方案；逻辑别名回退也是直接返回。共享分量仅容量重排时保留分核与 singleton mapping。守卫不保证性能严格改善。
- 新增工作量为固定基础构造之外的 O(n + tensor incidence + Wn)，W≤8；输入引用、各作業局部区间、最终全序列区间分别线性扫描。原始 COPY 收缩及基础构造/官方结构验证成本仍单列，不可据此声称整个 solver 线性。

## 有限独立验证记录

新增 `tests/q2/feedback/test_capacity_window_audit.py` 七项：

1. 从原始边独立生成微型端点 COPY 事件，枚举 6 种合法桶内 COPY 次序，按每事件 first/last 生存期计 alloc 峰值，全部被桶模型覆盖。包括中间 tensor 既写回 DDR 又被后续 compute 消费，最终原 DDR 输出本地映射 UB。
2. 两池共享输入在各作业内多次消费：S=(64,8)、P=(13,76)、capacity=(90,160)，得到 W=2，完整顺序保持各作业内拓扑顺序并符合容量。
3. 巨大无引用 tensor 与仅原始 COPY 使用的 DDR backing 不改变本地池峰值。
4. 原始 COPY 链与直接 op-op 因果不能跨作业。
5. S 超容量和 logical alias 分别正确回退，不伪造桶证书。
6. 多原始 producer 被拒绝。
7. heavy override 无容量证书，单独验证其覆盖性。

命令：`.venv/Scripts/python.exe -X utf8 -B -m unittest tests.q2.feedback.test_capacity_window tests.q2.feedback.test_capacity_window_audit -v`。实际 **13 项通过，unittest 内部计时 0.010 秒**，不是冷启动 solver 耗时。首次独立测试把排列数手算为 12，实际只有 6：共享输入只在首消费桶 COPY 一次，第二作业首桶只有私有输入；已修正测试期望，算法未修改，峰值不等式从首次运行即通过。此失败属于测试计数错误，不隐去，也不包装为算法修复。

固定源码 SHA-256：`3394e94a8269665dc3b9a3fe42333945abd73cdd588ff6c3844f82a836df611d`；原文档：`9378e36faeab3b6fde87bdcc1fd05a7f6767685dddd631c8e14a633949c90c2e`；原测试：`f2b2e19a3180e194398eb0e6ee72f2193a3a2d4f8559582975bbd688105822ca`。

未覆盖范围：全图官方评分、最终并行事件执行、容量窗口的真实收益与时延、原始逻辑别名的扩展支持、多 producer 模型。没有把“实测大于某上界”或若干正例用作一般证明。
