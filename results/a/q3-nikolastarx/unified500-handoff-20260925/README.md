# 统一 P3 全500交接（未运行）

固定solver **`2d5459fa042507cce0f0343e544ed43784c8488b`**，入口`python -B -m src.q3.adaptive_solve <原图> --cores <k> -o <新plan> --evidence <新证据目录>`。114项单测执行：113通过、1原有显式E0门控跳过；不将单测当正式成绩。路径、源码及原100图身份见[identity.json](identity.json)。

[完整500清单](manifest-full500.json)，或10个互斥manifest-sNN分片，**二选一**。每个分片50坐标/100 E0预留/360秒，完整串行清单500坐标/1000 E0预留/3600秒。共同总上限500 solver/1000 E0/3600秒，无重试，最多8并发；先做001k1、051k5、082k4、062k5四个已包含坐标检查链路，不能额外运行并再跑同一格。实际workers由中央在资源空闲后调度、写入原件。

原Q3 runner可在**独立稀疏checkout该solver SHA**后调用：`python -m src.q3.feedback_benchmark <本清单绝对路径> results/a/q3-nikolastarx/unified-full500-20260925-s59/<独立分片>`。清单属于后续材料提交，不能因此把solver checkout切到材料HEAD，固定源验证会拒绝。该runner保留first-error-stop；中央可用已审核自有并行runner，但须记录实际runner SHA、完整solver命令、候选账、预算及收尾，不热改solver。

[精确覆盖](coverage.json)当前是0成功/0失败/500未跑；历史不同入口的机制样本不冒充此批已完成。固定官方单核分母复用ba99b74b523f93a4002cd88970ec7164076d8008的results/benchmark-board/official-singlecore-20260924，按graph/config/code SHA匹配，不重跑、不用优化k1替换。失败、超时、未派发全保留；每核均值必须标n/100。无新P2配对调用、CacheGain缺失留NA。

单写执行者`s59ee5b053e1c48af8a64bc9ddb6ed5bc`；输出前缀由本任务保留给他，研发方不写。当前仅交接0评分，具体开始由已授权中央窗口安排。[规则与验收](../../../../docs/a/q3/UNIFIED_FULL500_20260925.md)。
