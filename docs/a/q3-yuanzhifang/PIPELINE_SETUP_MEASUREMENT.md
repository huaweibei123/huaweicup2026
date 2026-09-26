# 第十一批：首次共同输入服务量进入流水切点DP

1. **目标 / 机制**：算法固定 `f14e8f0ae38033e83d9f497301595b7568a55cb6` 的 `pipeline_setup.py`。在同构共享链、正整数周期M/V、每个共同输入仅在唯一作业位置消费的守卫内，将逐tensor的 `ceil(bytes/bandwidth)` 作为首作业setup，用O(kL²)时间、O(kL)空间DP求串行阶段冷setup抽象的最优连续切分。输出仍为singleton和作业优先的合法计划；切点及核心归属允许改变。模型不含真实管线重叠、私有输入、激活跨核搬运、500延迟、争用、Cache或容量，因此模型时间不是官方下界/上界或已测收益。
2. **输入**：仅044/k4。只读预检核图、10个官方代码文件、固定config，共12个官方身份；核候选/pipeline_stages/active/construct/baseline及 `PIPELINE_SETUP.md` 与f14e8f0完整字节；原pipeline依赖另核 `6bae8dfa317bc71226068344b59dd65d2612c32b` 字节。核原公共helper、环境/清理helper、标准feed模板和044实际官方单核分母。控制固定 `e6b5500dcbf3818034804168ee79d0f65c16706b` 的完整singleton流水P2/P3原件，两者40927，不重跑、不从ratio反推分母。
3. **输出**：独立 `pipeline_setup_benchmark.py`、`pipeline_setup_export.py`；结果目录 `results/a/q3-yuanzhifang/pipeline-setup-20260924/` 仅在START后创建。保留plan、冷构造stdout及DP/守卫细节、P2/P3全result/trace/log、容量/Cache/操作/传输、调用账、环境/共享资源/内存记录、run/manifest、gzip原字节与压缩SHA、CSV和标准feed。算法登记 `q3-pipeline-cold-setup`，variant `pipeline_cold_setup`。冷构造后只读对照计划，要求全1364计算op无遗漏/新增、每op唯一singleton、每子图只调度一次、guard=true；记录逐核数量与核心变化数量，但不要求与旧控制同核。静态商图合法性由冷solver中的原官方derive校验，不重复调用。
4. **限制 / 时间**：独立最多1 cold + 2外部E0，1低优先级worker，solver/E0子进程用Windows `BELOW_NORMAL_PRIORITY_CLASS` 启动，不再调用有句柄类型风险的冗余子进程优先级API。单调用30秒，含预检/封存批次120秒，90秒后不派；每次派发前Windows可用RAM≥1 GiB，不足/未知不派并停止。实际CLI明确 `--concurrent-work P2`，不声称独占。首失败/超时/守卫不适用/覆盖或身份不符/清理异常停，0自动重试/E1/E2/GPU/云，不借旧额度。
5. **验收 / 去重**：源码和runner/spec先固定，再 `--check-only`；准备阶段只读源码/输入/现有原件，0真实solver/build/derive/Step/E0。收到主会话审阅后明确START才执行。仅当冷构造计划与控制原字节完全相同，才记录新cold墙钟、`alias_of`及旧两条attempt引用，0新E0，导出alias复用回执，不冒充新的独立成绩；同时保留完整两字段JSON比较。完整JSON相同但序列化字节不同时不复用，仍对新plan分别P2/P3一次。保留改善、无改善、退化和失败；无论模型分值如何，不追加候选或控制复跑。失败raw产物在清理未确认时标sealed=false保留；清理确认后gzip并核原字节。
6. **交接 / 截止**：自然结束先给真实T0/T1、counts、状态、派发前最低RAM，再归档/导出/固定数据提交协议预检；运行中不读live ledger。冷solver启动到读图、守卫/DP/构造、合法性检查、写盘退出计完整墙钟；外部E0和父runner控制核验/封存开销分列。仅一格开发证据，不是同一统一solver完整SHA/入口/规则的100×5主成绩，不混合历史逐格赢家；中央准入、原件复验及独立验收分开。没有另设硬截止，120秒只是本批资源保护；不推送，等根会话整合。

只读准备：

```sh
python -B src/q3_yuanzhifang/pipeline_setup_benchmark.py --check-only --graph-dir ../huaweicup2026/data/raw/a/official-cases/data
```

主会话明确START后才去掉 `--check-only` 并提供当时真实共享状态。这里没有提前生成044候选来确认切点或收益。父会话已报告4项合成检查（其中100组事件递推和全切分oracle）；它们是开发验证，不能替代本批官方实测。
