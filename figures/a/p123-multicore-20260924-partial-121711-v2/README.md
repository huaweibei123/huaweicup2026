# P123 阶段图表：12:17 UTC 快照

这是部分结果，整批仍在运行。先看[均值表](mean_comparison.md)及[逐组计数](summary_statistics.csv)，再看[均值曲线](mean_multicore_comparison.png)、[P1](p1_multicore_speedup.png)、[P2 通用基线](p2_multicore_speedup.png)、[P3 扩展多核指标](p3_multicore_speedup.png)、[P3 同方案 Cache 收益](p3_cache_benefit.png)。每张图均提供同名 PDF/SVG。

来源为[固定快照](../../../results/a/p123-multicore-20260924/snapshots/20260924T121711.278791Z/README.md)，捕获窗口 2026-09-24 12:17:11–12:17:24 UTC，非原子。其 manifest SHA-256 为 `67a8315320d4b6ca68b3dd7344be18e8766e83ce4530941e589dce32a8e9b97d`；`comparison.csv` 及本目录 `input_comparison.csv` 的同一原字节 SHA-256 为 `7b57b5afbc0db26bdeaecb72b0d3db6b030e8531525251e44bf3ba890ea084a3`。源快照在提交 `e041bca2dcf825a55353765303b218491f351e2d`。

实际绘图源 SHA-256 为 `f1b40531c417d606585025c9276b9026bad910a26c039798b33eaa0d9b110339`，详见 `plot_summary.json`。其中 `plot_checkout_head` 是生成时的 Git HEAD，尚未包含当时未提交的绘图源码；使用源码哈希确定实际执行版本。JSON 内的 command 仅含文件名，完整可执行命令如下，从仓库根运行，输出目录须不存在：

```text
uv run --locked python -B src/benchmarks/p123_plot.py --csv results/a/p123-multicore-20260924/snapshots/20260924T121711.278791Z/comparison.csv --output-dir figures/a/p123-partial-REPRO --snapshot-label "PARTIAL SNAPSHOT | 2026-09-24 12:17 UTC | 749/1300 solver receipts; not final"
```

1500 个表位保留缺口，含 200 个复用官方单核锚点和 1300 个 solver 位置。749 个 solver 终态（697 成功、52 错误）并不等于每项加速比都可用：单核基准仅 86/100 成功；49 个成功 solver 缺该分母。P1/P2 一核点共用官方锚点，不是额外求解。P3 多核曲线为补充；主对照是同计划、同核数 P2/P3。

均值使用每组当前有效子集，并保留 n/100；各曲线覆盖不相同，不能直接作配对优劣结论。`matched_mean_comparison.csv` 另用所有三题、所有核数均有有效比值的同一 44 例子集，只作补充，不替代全 100 图结果。两类均值都不使用总周期相除。

Windows / Python 3.12.13 / Microsoft YaHei 实际渲染。已逐类打开 PNG 检查中文、数字、色标与 NA；修正均值图的注释和横轴重叠后在本 v2 目录重新导出。P1 与 Cache PNG 与已查看首版字节一致，其余三张查看本版。PDF/SVG 已生成，未在独立阅读器验收。数据完整原件审计及队长最终数据验收仍待全批结束，渲染成功不代表数据验收。
