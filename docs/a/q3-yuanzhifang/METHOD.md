# 共享输入输入束构造：首轮假设

`baseline.py`逐字节取自a4e7ee13310d693ec4fb5cc236669ceb3b172d1f的src/q3/construct.py；作者NikolaStarx，保留资源词/affine_eighth、COPY收缩与守卫，不修改上游文件。新模块作者yuanzhifang30-sudo，公式来源为Pro2 r02 §6输入束；不是复现其未读取的原型代码，也不声称新颖性。

对官方COPY收缩后的每个弱分量j取边界输入集合I_j。固定分量整体分核，静态入口字节为sum_c sum_{t in union(I_j: j on c)} size(t)。同支撑张量只在构造器中聚合排序权重，真实张量ID、Cache key、COPY和配置保持不变。该量不是P3物理DDR服务量，也不是Makespan。

两条候选：shared_order保持基线分核，用跨分量共享输入束的权重和最小tensor ID产生全核一致的作业优先顺序；shared_place先在基线每Pipe最大工作量上限内，贪心选择新增入口字节最少的核，再采用相同排序。装箱失败整组回到基线分核，不逐步偷偷放宽上限。每核沿用固定1/8仿射交错。MVM严格守卫命中时两条候选都直接保留resource_word。

这只是静态构造：FIFO Cache在COPY_IN完成时插入、查询在开始时进行，命中不刷新FIFO。同刻跨核首访仍可能全部miss；输入聚集也可能增加spill或破坏计算交错。负载上限不保证真实时间不增，贪心入口总量本身也可能比基线更大（037静态预检已观察到）。保留反例，评测后决定方向，不将静态量当硬淘汰条件。

复杂度：沿用上游索引O(n log n+e)；输入pins为p，分量数b，核数k≤5，分核约O(kp+b log b)，共享束排序/签名最坏O(p log p)，计划输出O(n log n)。Python集合和有理数比较有常数成本。没有暴力枚举、随机重启、图名查表、模型训练或在线评分。

阅读来源与反馈：Pro2 r02输入束及037退化；Pro3 r02卡C指出080减少输入量仍可能让P3退化；Pro4 r03给出044命中率/内存代理不能单调化。新Coherent Pro C研究报告开头明确旧数值属于作者报告，签名相同不证明未来变换等价；本实现因此只按最终plan字节去重，不用相同命中率/分值合并状态。

本机成绩台2026-09-24T13:57Z读到797条，P3/k4快照中的008=63768、037=53852、044=70261目前均为eligible=false（仅报告），源为固定674ce012的LYX快照；不是中央最新全量。Issue33的5815381196报告中央2197条/1013正式格，成员同步仍由原网站专项负责。首批比较以本机新的完整官方原件为准，不把本地落后数据称中央最优。

正式主指标为P3 Makespan cycles，副指标为官方added_copy_bytes、spill_added_copy_bytes、hit_bytes/(hit_bytes+miss_bytes)。P2/P3严格同plan比较，不取两张最优表相除。每个variant独立产生一次plan并外部复评；事后优胜不是实现了自适应在线选择。
