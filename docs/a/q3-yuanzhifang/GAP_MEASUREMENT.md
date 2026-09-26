# 第八批 gap-list 有界测量

1. **目标 / 机制**：检验把已就绪计算放入各 pipe 的现有空隙，能否进一步降低官方 Makespan。候选冻结 `a37eb931a22fb7df7e0d00d193538ce5289ae045`，入口 `src/q3_yuanzhifang/gap_list.py`，日历 `gap_calendar.py`。不可变增广 AVL 支持最早可容纳区间和预约；JOIN 至多 k² 算术分配后只提交选中版本，最后按模型开始排序 singleton。模型不模拟官方共享 COPY、Cache 或容量，局部最早放置不保证整图改善。
2. **输入**：仅官方069、请求5核、固定配置和原版P2/P3 CLI。只读 preflight 核全部114官方文件、算法/日历/依赖/spec、冻结辅助函数、既有官方单核分母，以及两个控制的完整 plan/result/trace/log：`b4f3f2895f52975cb6275ea85b89bf5a4a76ef7b` 的 release 为P2/P3=16403/15123；`ef80a88ed04b26e70465d56a54c373b0dcc5d00f` 的 JOIN 为16742/15221。控制不复跑，分母不由比值反推。
3. **输出**：新 `gap_benchmark.py`、`gap_export.py`；独立 `results/a/q3-yuanzhifang/gap-list-20260924/` 保存实际命令/环境/冷构造及外评墙钟、两字段plan、完整result/trace/log/cache_events/容量、stdout/stderr、调用账、压缩字节/原字节哈希、标准feed与固定数据提交预检。未封存产物在partial_outputs列明；进程清理未确认时保留raw并标sealed=false，禁止稳定哈希声明和后续调用。
4. **限制**：独立预算仅1 cold、同计划P2/P3各至多1 E0，共≤1/2；1worker、每调用30秒、含预检与封存的整批120秒、90秒后不派新调用，首失败/超时/guard拒绝/身份不符/清理异常停止。零重试/E1/E2/GPU/云，不借旧批余额。当前仅准备、提交和只读预检，等待主会话明确START；不从P2 B的瞬时进程空隙推定释放。
5. **验收**：本次构造后完整比较两个控制的node_to_subgraph与全部有序core_schedules，并另记原字节相等。任一完整JSON相等就保留新的实际cold wall与旧run/attempt/time/hash引用，0新E0、0新增成功成绩行，单独alias-reuse回执；若都不同才做本次2 E0。P3必须附本次同计划P2配对，完整保留改善、无收益或退化，不用模型完工、空隙利用或命中率代替官方结果。
6. **时间 / 证据边界**：父会话报告的3个合成测试（180次整数时间oracle预约、旧版本持久性/重叠拒绝、长短菱形插入独立操作）是另列研发成本，并非本批官方成绩。冷solver包括启动、输入、链/DAG/日历、算术决策、排序/校验和输出；外部E0单列。本次只读预检不调用build/derive/evaluate。第七批两份既有P3的零E0逐opID复核见 `results/a/q3-yuanzhifang/release-order-20260924/fifo-readback.json`，确认10条M/V FIFO不变，不能据此保证第八候选的FIFO不变。5–10分钟是效率建议，本批120秒是资源保护；单图结果不代表全100图、稳定尾延迟或算法终验。

冻结runner后只读检查：

```sh
python -B src/q3_yuanzhifang/gap_benchmark.py --check-only --graph-dir ../huaweicup2026/data/raw/a/official-cases/data
```

该命令不创建结果目录。只有明确窗口放行后才去掉 `--check-only`；数据提交后对新feed执行 `protocol.py --submission --commit <完整SHA>`。空records只表示没有新评分尝试，不是新增两条成绩。
