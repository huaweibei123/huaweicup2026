# 方案成绩台交付：P2 连续分块，真实 k=1，100 图

本批于 `2026-09-24T13:16:49.687Z` 开始，最后一格于 `13:18:12.024Z` 完成。100/100 求解成功，100/100 使用冻结官方 P2 E0 成功复评；求解器调用100、E0调用100、E1/E2调用0、无重试。先以2 worker执行001/002/044，三格均成功后以4 worker执行003–010，最后8 worker执行剩余89格。模拟核数始终为1，外层worker数2/4/8不是模拟核数。

算法为 `0b58c123cccf02fc993b741d79dcd8511e4dd38f` 的 `src/q2/construct.py`：min-ID Kahn 拓扑序按累计计算权重划连续块；`k=1` 是单块构造。它不是已有官方 A 单核基线，也不是Fang的优化构造。独立官方P2 CLI来自冻结源码，官方代码聚合哈希 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，配置哈希 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。100个P2结果的Makespan恰好都与对应官方A单核分母相同，因此 B/M 的100图算术均值为1.0；这个相等是本批观察，不把两种运行身份混同。

平台：Apple M5 Pro，18物理/逻辑核心、48GiB RAM，macOS，CPython 3.12.13；`uv sync --locked`在批次前完成。每个子进程BLAS/OMP/MKL线程变量设为1。求解外层墙钟中位数0.278秒、最大0.559秒；独立E0外层墙钟中位数0.550秒、最大9.336秒。每个子进程的采样峰值RSS，求解最大184.4MiB、评价最大724.0MiB；采样值不是同时运行全部进程的精确峰值，也不是硬内存保证。完整失败/时间/命令/原件身份以各 `cells/<case>/run.json` 为准。

运行与导出：

```sh
uv sync --locked
python -B scripts/a_materials.py --extract
python -B src/local_benchmarks/s59ee_p2_k1.py --source ../local-p2-fixed-0b58 --batch results/a/local-p2-k1-20260924/20260924T131640Z-s59ee --cases 001,002,044 --workers 2
python -B src/local_benchmarks/s59ee_export.py --batch results/a/local-p2-k1-20260924/20260924T131640Z-s59ee --cases <逗号分隔的用例> --output results/a/local-p2-k1-20260924/20260924T131640Z-s59ee/board-feed-<唯一名>.json
python src/benchmark_board/protocol.py results/a/local-p2-k1-20260924/20260924T131640Z-s59ee/board-feed-full100.json --submission
```

上述 runner 命令是**真实执行**，不可在此已完成目录重跑。复现需新建独立batch目录及固定提交的干净求解器工作树；其他两阶段实际用例和worker数在 `batch.json`。`board-feed-first3.json` 是最初三格快照，`board-feed-full100.json` 包括全部100格；两者重复的attempt/revision内容一致，接收时可只导入full100。结果JSON与Trace为原CLI产物的无损gzip，摘要按所存压缩字节计算。feed的 `run` 指向逐格收据，`baseline`指向已有100例官方单核结果，不触发新baseline运行。

验证：`python3 src/benchmark_board/protocol.py .../board-feed-full100.json --submission` 返回 `valid:true,records:100,eligible:100,reported_or_failed:[]`。这是格式、冻结身份与原件一致性检查，不是独立再次执行官方求值，也不是方法优越性验收。
