# 第九批：冻结 gap 构造的三图泛化

1. **目标 / 机制**：沿用 `a37eb931a22fb7df7e0d00d193538ce5289ae045` 的 `gap_list.py` 与 `gap_calendar.py`，不改算法或参数。由069的局部证据扩展到071第二小图及005/086较大一般DAG（4113/5274个计算操作，来自既有结构资料），检验质量与冷求解成本是否泛化。方法仍为最大串行链、剩余路径优先、最后前驱与JOIN至多k²算术分配、持久AVL最早空隙预约；模型不模拟官方COPY/Cache/容量，不是全局最优证明。
2. **输入**：严格按071、005、086顺序，全部请求5核，069不重跑。只读预检核三图、全部10个官方代码文件、配置，共14个冻结文件；算法/日历/依赖、冻结辅助函数、标准feed模板及三份实际官方单核分母也必须匹配。071旧JOIN P3=11613，固定ef80a88；005=90450、086=112029，固定fd0a78b3与ba99b74b历史feed，不称最新最优。005/086缺失原件已仅补取并保全于 `5d76036d19b79964a443e0546b657a5f1bef1e2c:results/a/q3-yuanzhifang/gap-generalization-controls-20260924/`，完整原feed无损gzip、选中记录、plan/result/run/manifest及来源哈希均保留；没有重跑控制。单核分母直接读取原件，不用ratio反推。
3. **输出**：独立 `gap_generalization_benchmark.py`、`gap_generalization_export.py`；正式批次目录 `results/a/q3-yuanzhifang/gap-generalization-20260924/` 在实际执行前不得创建。每图一份合法两字段plan、同计划P2/P3完整result/trace/log、cache_events/容量、stdout/stderr、调用账、run/manifest、实际共享资源与内存检查、gzip原字节/压缩哈希、CSV、board-submission-v1及固定数据提交预检。method仍登记实际 `q3-dag-join-gap-list`，用独立run/attempt与真实runner版本区分批次。
4. **限制 / 时间**：独立预算≤3 cold + 6外部E0，每图P2/P3共用一次构造；1worker，每solver/E0各30秒，整批含预检/封存≤240秒、210秒后不派新调用，首失败/超时/身份不符/守卫拒绝/子进程清理异常停，0重试/E1/E2/GPU/云。实际启动等待主会话明确START；`--concurrent-work` 必填，记录当时P1/P2共享情况，不能称独占。每次派发前用Windows系统内存接口核可用RAM≥1 GiB，不足或未知则停止且不启动该子进程；此本机批不声称跨平台内存门控已验证。
5. **验收**：源码与runner先提交，check-only只读通过后才报ready；准备阶段0solver/E0。完整保留3图的改善、退化、失败及资源停止；控制不参与在线候选选择。逐图构造墙钟覆盖启动、读图、日历/链结构、决策、排序校验和写出退出，外部E0另列；批墙钟还含固定身份核验及封存。实际并发条件、阶段时间及单次噪声必须随结果报告，不把同计划两场景重复计为两次求解。固定feed预检不等于中央接收、独立复跑或最终算法验收。
6. **交接 / 截止**：无独立硬截止，等待明确评分窗口；自然结束先给实际T0/T1、counts、状态与内存条件，再做归档/导出/固定提交预检。运行期间不读live ledger，避免共享Windows文件锁；不追加全100守卫扫描，复用固定结构资料。本批不替换、触发或扩展成绩台owner的旧四图JOIN跨平台队列。5–10分钟为官方效率建议，本批240秒是团队资源保护，不是官方淘汰线。

只读准备（不采集一份冒充未来运行时段的内存信息，不创建批次目录）：

```sh
python -B src/q3_yuanzhifang/gap_generalization_benchmark.py --check-only --graph-dir ../huaweicup2026/data/raw/a/official-cases/data
```

明确START后才去掉 `--check-only`，并根据当时真实状态填写 `--concurrent-work P2`、`P1`、`P1+P2`、`none-reported` 或 `unknown`。最后两项不代表独占证明。结束后运行导出器；数据提交后执行 `protocol.py <feed> --submission --commit <完整数据SHA>`，不推送或导入中央账本。
