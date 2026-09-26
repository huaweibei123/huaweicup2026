# Attention capsule 空隙放置候选

`attention_rows.construct(..., placement_mode="gap")` 仅改变已有 closed attention row、可选 FFN diamond 和 exclusive chain capsule 的选核代理。每个 ready capsule按原操作拓扑顺序，在每个核的 M/V 持久 AVL 空闲日历中试放；每个操作根据已放前驱的完成时刻和跨核固定延迟释放，选择最早可容纳区间。试放使用私有根，提交结束时刻、不同核边界 tensor 字节数、核号字典序最小的一个。每个 capsule 只提交一次，每核至多一次试放；日历操作为 O(log V)，构造约 O(k(V+E)log V)，另有识别和最终顺序重建成本。

默认 `placement_mode="append"` 保持既有计划和 metadata。gap 候选以 `attention_rows_gap` 或 `attention_rows_ffn_gap` 标识，并报告插入在原日历尾部之前的操作数。闭合识别、FFN 规则、原始操作及 singleton 提交不变。

**边界**：日历时间只用于 capsule 归核。随后 `_ready_word` 从该归核重新构造操作级顺序，丢弃 placement 的具体开始时刻；因此日历代理改善不保证最终顺序代理改善，更不保证官方 E0 Makespan 改善。模型未证明 DDR、Cache、容量或官方合法性；构造仍调用 `derive_multicore_plan` 做官方计划派生检查，不调用 E0。是否接受该候选须由外层固定预算与官方评价决定。

## 固定统一入口与验收

`src.q3.calendar_solve` 保留 expanded 的全部其他路线。只有原 route=attention 时，在同次新评 append 结果之上构造一个 gap 候选；相同计划不重复评，可靠下界不能改善时剪枝，否则第二次在线 E0。只有严格改善官方Makespan才接受；候选违反官方合法性时保留锚点，程序错误不伪装成结构拒绝。最多2在线E0，所有构造/评分/回退计完整solver墙钟。没有case编号或历史成绩查表，不对候选参数作扫描。

截至源码冻结前，128项单元检查运行、127通过、1项显式E0门禁跳过；包括60个固定合成小图的规模、M/V比、独立panel、FFN数、编号/存储顺序变换。它们证明所覆盖构造的依赖/日历隔离/原图保护，不证明未知数据的性能。071/069/005五核各append/gap一次静态构造，共6构造、0solver/E0，最终代理周期6266→5441、7050→6232、21228→20732，计划均变化；这些不是官方成绩，也不是未见样本。下一官方机制探针最多3solver/6E0、1worker、120秒总/30秒每格、0retry；成功也须固定整套算法做全量评价，不能把三格替换进a5均值。

单核提前跳过gap构造：两种placement都把所有原op放core0；最终 `_ready_word` 只取决于原graph、归核和同一个delay。因此计划必然相同，不必再识别/构造一次才做字节去重。这是代码路径上的等价性判断，不是按已测case记忆的捷径。该优化随后固定在新源码，035三格探针仍保留其原始版本身份。
