# P3 结构选择在线构造：100图×1–5核

固定算法 `a4e7ee13310d693ec4fb5cc236669ceb3b172d1f`，每格执行`python -m src.q3.solve`：按结构在`resource_word`与`affine_eighth`间选一个构造，**求解进程内部**调用冻结官方P3 E0一次，成功后才发布plan和完整result。本批500格全部成功，500次solver、500次内置E0、0 E1/E2、0重试；实际选择`affine_eighth`485格、`resource_word`15格，不按成绩选优。前4格2 worker、接着6格4 worker、余490格8 worker。T0=`2026-09-24T13:31:54.680Z`，最后完成`13:35:07.951Z`。

平台Apple M5 Pro/macOS/CPython3.12.13/48GiB RAM。外层完整求解墙钟中位0.571秒、最大23.876秒，**包含**构造与在线E0；不能把Q3收据的E0组件秒数加到这列。子进程采样最大RSS725.9MiB，采样不代表整批精确峰值或硬限制。逐格状态、命令、版本、墙钟与原件哈希见`cells/<case>/k<k>/run.json`，Q3原始内部计时见`evidence/receipt.json`。

`board-feed-first10.json`为001/002的首10格快照，`board-feed-full500.json`为全部500格；重叠attempt/revision内容相同，接收可只导完整feed。结果JSON是Q3源码所写的完整官方函数返回值 gzip；没有另跑一次官方CLI，也没有同计划P2无Cache对照，因此CacheGain缺省。官方P3 Makespan、字节命中率与相对单核分母由原件可算。工作树严格预检：

```sh
python3 src/benchmark_board/protocol.py results/a/local-p3-20260924/20260924T1331Z-s59ee/board-feed-full500.json --submission
```

返回`valid:true,records:500,eligible:500,reported_or_failed:[]`。这是格式和原件一致性，不是独立复跑或方法科学终验。完成目录不可重跑；复现需新批次、固定源码和新attempt身份。
