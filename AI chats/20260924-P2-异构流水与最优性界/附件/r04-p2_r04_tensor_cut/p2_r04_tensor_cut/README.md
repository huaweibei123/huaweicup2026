# P2 r04 — 精确 tensor 复用成本的固定日历 min-cut 修复

## 读取身份

授权源码入口为 `Vioano/huaweicup2026` 固定提交
`923b25ecb0b9d6d0e2d3f149fccef431b5403f99`。
全文读取了 gap_candidate.py、candidate_ddr.py、P2官方入口和 PRO_R03_REVIEW.md；
另读 P1官方文件中 _original_tensor_views / _copy_traffic_bytes。

本包是独立实现的原型，不是已合入镜像的补丁，也没有调用任何官方评估器。
没有读取原图全集，没有调用 E2，没有使用 prepared/MEMORY_REUSE 接口。
所有测试结果仅为本包的数学模型与代码检查，不是新官方成绩。

## 输入与适用域

`repair_gap_witness` 输入现有 gap_candidate 构造完毕时的：

* 原图 graph，非分支链列表 chains；
* unit→core 字典 placement；
* 原计算操作的模型 starts；
* 原 _chain_dag 得到的单位边 delay 字典；
* 核数以及已固定的 singleton mapping。

图和 seed 应已经过现有 _chain_dag 的守卫。调用者仍须在输出前调用
`derive_multicore_plan`，本原型不替代官方结构校验。

## 精确性范围

原图每个 physical tensor 至多一个 eligible producer；本实现拒绝 logical_tid。
预 Step2 COPY 字节计数按实际消费核集合去重，输入、输出、tensor跨核和直接边分别计入。
保留所有 tensor 的物理身份；decision-support 聚合只是流网络目标的等价压缩。
原始直接边记录不擅自去重；端点相同的合法记录按冻结 helper 的逐记录语义处理。

返回计划保证的只有：

1. 精确的预 Step2 COPY 字节不增加；
2. 在传入的静态通信延迟模型中，原来的全部计算时间位置仍是一份可行 witness；
3. 每次 min-cut 全局最优于当前 source→target corridor 的所有子集迁移。

它不保证官方 Makespan、spill、总 scheduled_copy_bytes 或 credit 门控不变。
原始 timestamps 绝不作为计划字段提交。
单次过全部有向核对，不运行收敛循环，不扫描时间/通信惩罚系数。

## 接入点

在 gap_candidate.build 的 while ready 结束后，保留原 mapping：

```python
mapping = {str(u): position for position, u in enumerate(index.order)}
plan, repair_detail = repair_gap_witness(
    graph, chains, placement, starts, delay, cores, mapping
)
derive_multicore_plan(graph, plan)
```

`starts` 和 `placement` 原件应只读保留，以便断言和诊断。
新完整求解器仍只评价 baseline 和修复后的 gap 候选；不增加第三个在线候选。
这只保护相对本次 baseline 的选择，不保护相对未被评分的原 gap 候选。
候选族的新 E2 准入仍由项目维护方按公开接口做；本包没有实现或验证该接口。

## 复杂度与停止

先用并查集合并不能在固定时间位置下跨核的单位边。
每个有向核对只处理 source 上能原时原 Pipe 放进 target 空闲段的组。
因为所有可动组原来在同一核上，其每 Pipe 区间互不相交，任意子集迁移均无资源冲突。
目标净增量按决定变量支持 F 压缩为 OR 开核费与 AND 关核返还。
若 `sum(max(R_F-O_F,0)) == 0` 则该 corridor 没有正字节收益，零流调用停止。
否则一次 max-flow 得到精确子集；最优无改善则不改标签。
最多 k(k-1) 次流调用，且每个有向核对恰处理一次，不因尚有秒数而继续迭代。

原型用标准库整数 Dinic 与迭代阻塞路径，无递归深度依赖。通用最坏界仍为 O(V_f^2 E_f)。
当前代码为了清晰会重建/排序 pair calendars；生产版可复用已有 sorted calendar / 线性扫交叠。
保持源整数容量，不用浮点最大流冒充整数最优。

## 运行测试

```bash
python test_reuse_corridor.py
```

完整子集枚举仅用作小规模测试 oracle；生产构造没有枚举。
`diamond_*.json` 是独立模型 fixture，未做官方图验证，不是官方结果或建议直接提交的成绩输入。
`test_results.json` 包含实际测试计数。合成修复 seconds 不是全求解器墙钟或官方 cycles。
