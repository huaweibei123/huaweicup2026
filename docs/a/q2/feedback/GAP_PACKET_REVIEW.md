# Gap packet 原型的独立有界审查

审查固定对象为提交 `7385d80a7182923fb40e2871847b688d6db3c859` 的 `src/q2/feedback/gap_packet.py`、`gap_calendar.py`、`GAP_PACKET.md` 和原7项测试；四个工作树文件与该提交字节相同，SHA-256 分别为 `2a70c4be555b1eb9b81c98b7ae53305b341305227ad0c159080a1771e4a91049`、`203ebf550396bd86e2b4fc86678197ed0f5360765dce13862aca82bda5c1fc47`、`3f6557be6691760f9ea8f72c870208d1b847cd41ecc06f30d9be26957041c253`、`0811256eea1a7945cef7f1279a2139f6f95f0482a17821789b59a9d37c639787`。P3 来源为 `a37eb931a22fb7df7e0d00d193538ce5289ae045`；`gap_calendar.py` 与该提交的 `src/q3_yuanzhifang/gap_calendar.py` 除顶部来源注释外相同。P3 的 `gap_list.py`/`dag_list.py` 提供配对与链构造思路，P2 的 TensorIndex、物理关系守卫和容量回退属于本适配。保留 P3 原作者归属；P3 第8/9批不是本原型的 P2 成绩。

## 守卫与依赖

`TensorIndex` 在建索引时核对原始 tensor 不超过一个 producer，`Index` 建 COPY 收缩后的 eligible `pred/succ`。`chain_dag` 从原 tensor 的 eligible producer→consumer 与直接 eligible→eligible 边建立二元 `(u,v)` 关系；存在 `logical_tid` 别名、此关系与 COPY 收缩关系不相同、或图不同时含分叉及汇合时回退。只有 direct 边被 COPY 链替代的合成图实际返回 `None`；含 direct 1→3 再加同端点 COPY 链的合成图可进入新路线，因为收缩后仍是相同的 1→3 **依赖关系**。此时合成 `build` 在1/2/5核均导出结构派生接受的合法计划，没有发现漏掉 eligible 前驱的反例。

重合路径也说明守卫只是**二元依赖关系相等**，并非原始路径多重集、COPY 服务字节或通信时延精确相等。新路线的 `delay` 仅累计建模的 tensor/direct 边大小，额外 COPY 路径可能改变未建模的服务、容量或真实时间；它是静态模型限制，不能从本例推断官方 Makespan 改善或恶化。原先把这一例称为“正确性漏守卫”不成立。若未来要求每条物理 COPY 路径逐项等价，应另立更强契约与守卫；现有关系契约无需据此改源码。

## 链、汇合与日历

链只沿出度1且后继入度1的 eligible 边延长，且从 `index.order` 遍历，故每 eligible 操作只属一条链。收缩后拓扑序由入度队列重算；rank 从逆拓扑序计算，ready 按剩余最长计算路径排序。汇合配对仅在当前链 `j` 唯一后继是入度>1的 join，且其它父链均已放置时触发；它比较 `k²` 个 `(j 核, join 核)` 静态算术结果。`place(join)` 用临时父链的核与完成坐标，其它父链用已持久化值；同核读临时 parent 日历，异核读目标核当前日历。胜者先持久化 parent，再持久化 join。小 diamond 的1/2/5核输出均覆盖每个 eligible 操作恰一次并产生一次配对。

`gap_calendar` 是持久 AVL 空闲区间树。原7项测试的固定种子独立占用区间 oracle 涵盖12×80=960次最早可放置查询及预约，并验证旧根不变、未来预约前的空隙和重叠拒绝。本审查另用10操作固定种子合成 DAG 触发一次真正的 `operations_inserted_before_tail`、两次汇合配对；导出计划覆盖全部操作且每核有边前驱保持优先顺序。输出用 `(modeled_start, 原拓扑位置)` 排序，正持续时间来自 `Index.duration=max(1,cycles)`；相同核的模型依赖边必须晚于前驱完成，故该排序与已放置依赖一致。结构派生验证也运行于这些**合成图**，并非官方 E0。

算法模型不安排真实 COPY、DDR 竞争、容量/spill 或 Cache，日历中保留的未来预约只是静态计算 pipe 的优先坐标，不是 E0 保证的开始时间。每普通链至多 k 次 `place`，最后父+join 的二元选择至多 k² 次；每个 `place` 顺序访问链操作并对持久树查询/插入。以 AVL 的对数操作为前提，模型阶段的保守规模为 `O(k²(n+E) log n)`，另有图索引、COPY 收缩、结构派生、输入输出及冷进程开销；该式不是端到端运行时实测，也不能推出接近最优或官方加速。

## 回退容量口径与验证范围

守卫拒绝时调用 `capacity_window.build`。外层标签 `gap_guard_capacity_fallback` 只表示回退；内层 `selected=capacity_window` 也不能自动证明全图无 spill。合成 `chains()` 在 L1=UB=0 时返回 `core_details[0].window=0` 且 `changed=false`，所以该核没有容量证书。仅逐个非空核满足窗口≥1和闭区间峰值守卫的特定路线才可引用原型的保守内存证明。进入 `join_gap_packet` 路线则完全没有容量证书。

新增 `tests/q2/feedback/test_gap_packet_audit.py` 五项，配合原7项共12项通过，命令：`.venv/Scripts/python.exe -X utf8 -B -m unittest tests.q2.feedback.test_gap_packet tests.q2.feedback.test_gap_packet_audit -v`，本机 unittest 内部计时0.057秒。这些是小型合成图/纯calendar结构核查；没有加载官方图、没有调用solver/E0/Step2或完整官方评估。审查未找到已证实的 eligible 依赖遗漏或输出顺序违法，但并未穷尽所有图，P2 真实合法性和质量仍必须由后续未修改官方 E0 独立检验。未修改原型源码、现有测量批次或P3材料。
