# 严格私有 M→V+→M 链及共享输入结构分类：待排期脚本

**状态：已在 s59/主控确认的空档完成唯一一次扫描。** 冻结代码为 `fefd422af7b5dc7d869ba2aa5b753fbc84061d2b`；执行记录见 [run01-static100/run.json](run01-static100/run.json)，结论见 [SUMMARY.md](SUMMARY.md)。100/100 图完成，单 worker 6.524 秒，返回0，未重试、无评分调用。资源已释放；不得据本文件自行再扫。

## 固定来源

- Pro 原件：`a556d534382cc670a6e5450661da6f8adbe638ca`，`AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py`；完整原件 SHA-256 为 `5a753611e52654ca93155256602e4cc1ea75fc0234bd4db1b24f756d3fef96b0`。同时读了该目录 `RESEARCH_NOTE.md`。
- 独立初审：`2fa5b169` 的 `results/a/review/p1-pro-initial-20260924/INDEPENDENT_REVIEW.md`。已纳入 prefix/return FIFO 深度平局反例：严格识别通过 **不代表** 理想返程计算式的 FIFO 顺序已核验。
- 008 既有原图审计：同 `a556d534…` 的 `results/a/review/p1-pro-initial-20260924/008-independent-interfaces.json`。本目录 [reference_008.json](reference_008.json) 仅提取其输入身份、N/a/b/c、必要服务和最小完整切口服务，并保存原件哈希；以后同一次扫描会与这些已有事实交叉核对。
- 固定官方配置 SHA-256：`dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。配置字节不一致便停止，不按别的带宽/容量悄悄重算。

`strict_recognizer.py` 只抽取 Pro 的 `Unsupported/topo/Views/views/recognize` 五个定义及必要常量/标准库。逐个定义与原件 AST 一致。额外的 `recognize_prebuilt(view)` 只删除原 `recognize` 的第一句 `v=views(graph)`，接受已解析的同一 view；余下识别函数体 AST 逐项相同。这样每图只解析一次，且本地模块根本不存在 choose、encode、model_plan、编译或评估函数。

## 唯一生产入口与预算

必须先取得实际静态空档；下面的标志不能自行授予资源：

```sh
python -B results/a/q1-return-cut-triage-20260925/triage.py \
  --confirmed-static-slot --output <new-output-directory>/triage.json
```

可显式传 `--archive`、`--config`，默认使用当前脚本所在仓库的只读官方文件。路径不是写死的个人路径。单 worker、单进程，不生成子进程，不导入求解器。

- **最多一次 ZIP 扫描**：原 ZIP 物理字节读一次并求 SHA，在内存 ZIP 中每个 `data/case_001.json` 至 `100.json` 仅解压/读取一次。结构分类和共享输入统计复用同一个 graph/view。
- 内部计时 **28 秒**中止，给保存部分报告及退出留约 2 秒；生产者仍应设 **30 秒进程硬预算**。如果超时、配置/输入身份异常、断言失败，保存 partial/error 状态并非零退出，**不自动重跑、不补第二次扫描**。
- 先在同一进程内检查两个极小静态 fixture：长 skip 切口、跨切口外部输入复制、必需 DDR、共享输入交并集、严格拒绝共享张量、零字节 COPY 仍需一周期。没有 Task plan、模拟或评分。本次唯一运行中这些检查全部通过。
- 真实图 `construct/choose/encode/model_plan/Task compiler/E0/E1/E2` 均不调用。输出若已存在拒绝覆盖；没有参数搜索或批量计划生成。

## 每图产物

每个图均记录输入 SHA、strict 是否匹配和明确拒绝原因。非匹配图的 N/a/b/c 留空，不强行套同构公式。严格条件为：保留 compute 真 spine、M→V+→M、无被删除 COPY 桥、单 compute 生产者、无跨组件共享张量、无内部原 COPY_OUT tap、完整规范化签名一致；允许前向 skip。

匹配时记录 N/a/b/c 和代表链全部切口。以下量分别命名，避免混淆：

1. 完整内部界面 bytes：包括所有跨界 skip 张量。
2. 内部额外 COPY bytes/service：一写一读，服务逐张量 `2*max(1,ceil(size/60))`。
3. 固定**一次切口**的完整额外代价：上述内部流量加同一外部输入跨两段消费造成的一次额外读；其 bytes 与 service 分别求最小值，保留对应切口索引。不能把 bytes 最小和 service 最小强行合成同一个切口。
4. 必需 DDR：按原 compute 生产/消费与输出标记判断每个必需输入读/输出写，记录总量和每链量；不直接拿原图所有 COPY 总和当必要量。
5. prefix、return、whole 的全部不同本地 tensor footprint（原 DDR 映射 UB）；`q*(prefix+return)<=capacity` 给 mixed q 的**充分条件**，whole 同理。证书失败不等于必然 spill，q 也不是硬件真实最大包宽。
6. 每 K=1..5 的量级比较：多链渐近资源重叠上限 `min(a+c,b)` 对 `K*最小完整单切口服务`、`K*返程切口服务` 的精确有理比值。零服务单独标记，不做除零或写无穷大 JSON。

同时给容量允许 q 下的理想稳态 F(q,q) 与扣除每 Task 100 gate 的每链算术收益。**FIFO 顺序未验证、启动排空未计、DDR/MEM 未模拟，所有这些值都不是 Makespan、保证改善或已构造方案。** 比值只用于寻找“小切口/大计算”的值得研究对象，不能替代端到端验收。008 仅作为已有静态审计参照，重点标签为084/095，不对它们设置特殊算法规则。

## 同次扫描的统一路由字段

对所有图（包括不匹配私人链者），另统计最近 compute 的 COPY 收缩弱组件：组件数、每组件外部输入 ID 集合的交集 bytes 与并集 bytes、交并比例、M/V 等 Pipe 工作 min/max/total、compute Pipe 数量与 op 类型计数是否一致、一个按 ID 破平局的拓扑 Pipe word 是否一致，并保留轻量组件明细。

共享输入交集使用**同一 tensor ID**，不能按相同 size 猜成相同输入。外部输入按“组件有 compute 消费者而无本组件 compute 生产者”判断。单组件交并比为1时仍必须结合组件数解释。确定性 word 一致不是 DAG 同构证明。

这些字段供主控研究“高共同输入比例＋近同工作/类型组件”的一般路由条件。脚本不写 route，不以全图输入超过524288作为开关，不按044/046/090或其他 case ID 分支，不覆盖 overload，也不生成统一 solver 成绩。

单次产物已包含全部100图及084/095的实际结构分类；它没有产生新E0批次或新方案成绩。下一步是否构造、采用何种固定方案仍由主控统一排期。
