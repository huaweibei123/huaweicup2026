# 067/k5 固定波次双模式测量

候选固定为 `wave_capacity.py` 提交 `2cf325fb717077cd902830e7f01c920d27cbf8ec`。本批在同一官方原图和固定配置下独立构造 `full`、`capacity` 两格，每格一冷启动构造加 P2/P3 外部 E0，最多 **2 cold + 4 E0**。这是研究比较，不用 E0 在线选模式，也不是统一 full500 算法成绩。既有 pipeline 067/k5 P2/P3 均为 15,686,331，来源固定提交 `c514edf0a8ef95861fc5cfbcc6719ffd5fdd4e07`，仅作历史参考；本批不重跑、不计入新调用。

新 run ID `yuanzhifang-q3-wave-20260925`，目录 `results/a/q3-yuanzhifang/wave-20260925`。一名 worker 在 full 完成后派 capacity；每 case/mode 顺序 cold、P2、P3。最多一个子进程并发，每次派发在锁内检查可用物理 RAM 和输出盘空闲空间均至少 2 GiB。每调用上限 60 秒、总批次 300 秒、240 秒后停派；首次调用、资源、守卫、合法性、结果或审计失败即停止后续派发，零自动重试。已运行子进程安全回收，已成功原件不覆盖。

`--check-only` 核官方图/config/代码与 manifest 哈希、候选及依赖固定字节、单核基线和已提交 runner/export/spec 身份，**零构造、derive、Step、E0**。正式运行必须声明当时真实并发工作：

```powershell
python -B src/q3_yuanzhifang/wave_benchmark.py --check-only
python -B src/q3_yuanzhifang/wave_benchmark.py --concurrent-work P1+P2
python -B src/q3_yuanzhifang/wave_export.py
```

runner 要求每格 metadata `guard=true`、`selected=wave_capacity` 且 mode 与命令一致；提交 JSON 恰有官方两字段、五核、singleton 全覆盖，每个完整 job 只归一个核。P2 官方结果没有 `problem` 字段，按 scene B/5核/正 Makespan 验证；P3 另要求 `problem=3`、`cache_mode=read_only`。每个 variant 有独立 construction/evaluation ID、目录、冷墙钟和 P2/P3 对照。原件保留计划、完整 result/trace/log、stdout/stderr、调用账、资源检查及 gzip/raw 双 SHA-256；导出只读最终原件、先封存 manifest/ledger，再生成标准 feed。新调用数以封存的 `call-ledger.json.gz` 为准。

P3 外评结束后，runner 从原始图找无 eligible compute writer 且有多 compute consumer 的共享 tensor；仅按 `cache_events` 的 hit/miss 和原始逻辑 tensor ID 统计共享读取字节，与该模式 metadata 的条件界比较，并要求 `cross_core_transfers` 为空。越界或身份不符即保存 E0 原件并停批，不静默调整参数。这一步属于批次墙钟，既不再构造计划，也不是新 solver/E0 调用。模型容量包络、共享读量界及历史参考都不能替代官方 Makespan 或零 spill 证明。

审计同时核对共享输入总字节身份、每个活跃核心对所有共同输入的读取覆盖、逐事件大小及官方 hit+miss 总账。审计对象及 passed 标记先落盘再决定是否停批；官方 E0 成功与后置研究假设审计失败分别记录，不能用对象存在代替检查通过。标准 feed 不添加协议外的 artifacts.call_ledger；封存账本由 run 收据引用。
