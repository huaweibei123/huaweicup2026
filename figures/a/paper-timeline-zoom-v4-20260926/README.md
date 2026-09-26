# v7 时间线可读性候选

每例两张独立图：`p26-timeline-full` / `p26-timeline-zoom` 和 `p38-timeline-full` / `p38-timeline-zoom`。全图高 170 mm，局部图高 92 mm，均宽 160 mm；图注在 `caption.md`。新稿分别自动编号，局部图引用完整图；实际编号以合稿为准。原稿、实验、评价器及正文不改。当前仅核实单张物理尺寸与图件可读性，未在最终 LaTeX 版面中验收图注与浮动体位置。

## 重生成

在具有锁定 Matplotlib 环境的仓库根目录运行。`--v7-source` 指向冻结的 `v7/source` 目录；替换为实际相对路径：

```sh
uv run --no-sync python figures/a/paper-timeline-zoom-v4-20260926/draw_timeline_zoom.py all --v7-source <path-to-v7/source>
```

本次实跑使用 Matplotlib 3.11.2；未调用求解器或评价器。脚本核对输入 SHA-256 和四个 makespan，再逐事件检查时间戳、正持续时间、公共横轴边界与 Pipe 类型。每张图导出 PDF、SVG、PNG；`*-160mm-preview.png` 按 160 mm 纸面宽度、300 dpi 导出。SVG 每行尾随空白已去除。

## 冻结来源与语义

以 `--v7-source` 为根，p26 为 `data/figure-inputs/p1-026-k5.json.gz`，SHA-256 `9d7eb4298f5c97aebea3c9699630604f8a2b62211216d7879a8c24ee8f290151`；p38 为 `data/figure-inputs/p2-019-k5.json.gz`，SHA-256 `8b1ebb9e3a116df56dbf89e8977b669411675734968a61b5c009ad8c2a6acd1f`。

原 `draw_figures.py` 的 `timeline` 以 `result.per_core_timeline[*].tasks` 表示 Task 区间，以 `ops` 表示四条 Pipe 的实际占用事件。候选全图逐一绘制全部 Task/op，局部图重绘同一来源时间窗内的原事件。没有更动事件、在全图过滤事件或给泳道空白指定原因。p26 两方案共用 0–44,114 cycle，局部窗为 5,200–9,400 cycle、Core 0/1；p38 两方案共用 0–28,514 cycle，局部窗为 13,800–17,400 cycle、Core 0/3。p38 的 16,247 与 28,514 cycle 均来自冻结输入。具体 Task、op 数量与时间窗证据见各自 `*-semantic.json`；其中路径只使用相对于 `--v7-source` 的标识。

只读参照件 SHA-256：原 `draw_figures.py` 为 `cc2ed6d024df419ec9a2a23fc34e6f8a23846da523beec55ee1cc568887f3e95`，v7 PDF 为 `51cd3c6fefd4885c7978bf46d6ad279297c170f3c8b590ae649aa4963df51ff0`，审阅 `AUDIT.md` 为 `291c46b67e066addbd50ca842e2323b634e4d14e0edd4eeab8fc77dd5f773112`。输出哈希见 `SHA256SUMS`。

## 版面检查

四张预览均以实际 160 mm 宽目视检查了文字、轴、Task ID、Pipe 事件、放大区和 (a)/(b) 对应关系。两张全图的 PDF MediaBox 约为 160 × 170 mm，两张局部图约 160 × 92 mm。两张图各自的图注能否与图同页、自动编号和交叉引用是否正确，仍需论文排版验收。
