# 两格额外DDR增量：已有E0元数据核验

只读配对固定旧feed `60afc38b327680fbda0ff10182e3e05a01edd72d` 与已完成c665全500审计。依据 `results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json`，官方movement定义 `added_copy_bytes = partition_added_copy_bytes + spill_added_copy_bytes`；不是COPY活动时长。072/K5新旧M为4,877,876/5,087,361；014/K2为8,749,303/8,869,498。

| 格 | added DDR旧→新（增量） | partition copy旧→新（增量） | spill旧→新（增量） |
|---|---:|---:|---:|
| 072/K5 | 103,942,944 → 225,319,748（+121,376,804 B） | 37,515,608 → 102,138,244（+64,622,636 B） | 66,427,336 → 123,181,504（+56,754,168 B） |
| 014/K2 | 50,500,536 → 150,205,276（+99,704,740 B） | 9,893,208 → 61,415,260（+51,522,052 B） | 40,607,328 → 88,790,016（+48,182,688 B） |

两类增量都重要，partition略多于spill；不能只归结为重载。旧→新计划仍是相同数量的子图（072: 29,666；014: 35,705），但子图归属变化分别为23,917与21,725个，说明切分方案/分核分配发生大幅改动；这不是消费者core触达数；现对原图和保存计划调用静态COPY计数器后，可把新增partition bytes进一步归类，但未逐tensor排序。分核子图数：072由[9565,5117,4998,4993,4993]变为[5570,5734,5695,6239,6428]；014由[17858,17847]变为[19091,16614]。

E0 timeline的COPY_IN/OUT操作计数：072旧13,547/484、新19,767/11,711；014旧9,201/1,340、新18,096/11,864。`step3_by_core.memory_dependency_count`合计：072旧61,285、新71,666；014旧108,565、新129,617。这些是操作/依赖计数，不能等同spill次数或字节。新结果分别含5,199/4,397条`cross_core_transfers`；旧result中该列表为空且无task_dependencies记录，表示旧产物缺少这些明细，不能据此断言旧传输为零。

可见两图的新计划都增加了partition和spill字节，且COPY操作/内存依赖计数上升；数据不足以判断哪个改动因果地产生DDR增量。M虽略降，也不能由这些计数推出更好的重新分配方案。未解析完整图trace、未运行构造或评分。

固定原件与哈希：审计汇总`completed-summary.json` SHA-256 `083c3f5b603cb61dd8b132718b6437b35c7706ff3aa165bdcdd490617547a2f2`；secondary DDR报告的输入摘要及旧feed SHA列于其`sources`。旧072计划/result SHA-256分别`fbe47561ecc6a1390628b5db8b68db1dca0080b25171cf9a09b41d9c92cc5152`、`3f855309b98e94ae342e766632eb3630b82b2354ae034b94dee9c31f587d139c`；新归档`cases-071-080/072-k5/plan.json.gz`、`result.json.gz` SHA-256分别`98103d139cdb15181bfa4b8190b309e792a3b27ee846884ff8604c9b7f31efc4`、`39fc8031cd6fb0b7122c3a9ab7c091c538c767d688c3acb39d703ef78738ed1b`。旧014计划/result SHA-256分别`aa6744c96635d8c8f63db725b1dd82ed481b591bfe17e6e97fbeebac31fcc992`、`ce1dee4e6341048b940803903e6687399e56a26d011164dea2835a7137f5ce8e`；新`cases-011-020/014-k2/plan.json.gz`、`result.json.gz` SHA-256分别`51ab18c47b01f8b9679e1cb367111bec5cd5bfd1d77d96a594b7dad1fb4dba27`、`c0759b41f9a762854b8ef733bc3ed4acf59a3c68f9dd2b1076c7aa9fff8e2d8c`。旧文件来自固定feed Git blob，当前归档SHA与字节已核。

## 原图与已存计划的静态COPY拆分

复现命令和逐类原始计数见 [`ddr-copy-static-probe.json`](ddr-copy-static-probe.json)，一次只载入一张官方原图；命令调用 `candidate_ddr.mandatory_copy_work(graph, saved_plan, 60)`，不运行Step1/2/3、E0或构造。`transfer_bytes` 与官方 `original_graph_copy_bytes + partition_added_copy_bytes` 四次均精确相等。原图SHA：072 `09ecc7be74ccdd06b00843fa6cd0696fb76ed623ca2ea3c9f36590450bc2749f`；014 `e27abb053ac57786e510ba80e60a6ec60a8b0df11b2a818010a1df17c29d94dd`。计数器源码SHA：`a0b732ffc4ce68ab8a821f6ece096cd51198a437a4993f2e174cdea602d4cd3d`。

关键结果是两格新增的partition复制都来自计数器的`cross_tensor`类：072增加10,398个COPY操作、65,411,636 B，同时boundary_input减少789,000 B、80个COPY；014增加8,794个操作、52,042,756 B，同时boundary_input减少520,704 B、104个COPY。boundary_output和cross_direct两格均不变。净额分别就是partition增加64,622,636 B和51,522,052 B。这比先前的COPY活动/Step3计数更直接地支持“计划分核引入跨核张量复制”这一**静态字节记账结论**；仍不能据此断言哪些tensor或算法步骤造成官方spill增长。单tensor扇出排行未做。


复现：`python3 -B scripts/q2_ddr_regression_categories.py --raw-root <OFFICIAL_DATA_DIRECTORY> --out results/a/q2-nikolastarx/ddr-regression-mechanisms-20260925/report.json`。新增公开脚本进一步逐份断言保存计划和官方结果原件SHA，摘要绑定既有完整审计SHA；未调用评价器。
