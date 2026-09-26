# 图 5-3：问题二多核平均加速比（修订候选）

本图从 Fang 在固定提交 `6ac4ec28582212c9fab967ceab5e09e796dbadba` 交接的真实半成品出发。该半成品与 LYX 的 `e5b785c96f3c589cf3029c62f76fea67dcd7a90c` 原稿相同；Fang 已说明自己未另画新版，并停止了本图写入。原稿保留在 `deliverables/a/fig53-captain-handoff-20260927/original/` 及交接 ZIP 中，本目录为独立修订稿。它是供论文监督会话选用的候选图，不等于正式论文已采用或用户最终验收。

## 数据与图的口径

四组输入均在交接 ZIP 中，逐项哈希由 `MANIFEST.sha256.json` 约束。`tensor`、`gap` 各有 100 张图 × 1–5 核共 500 个有效坐标，`F1` 只有五核心的 100 个有效坐标；这三组的结果表来自固定提交 `178a3673bd238b20772211427b8134b6db35f5af`。`c665` 的 500 个官方评价结果来自固定提交 `1c00079aadbd071de62db17686d5ba3fed1da0f2`，求解器为 `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`。各方法的完整求解器提交见 `validation.json`，没有逐格拼接历史最优。

每个坐标先以同一张图的官方情况 A 单核心完成时间 `B_i` 除以该方法在对应核心数下的官方完成时间 `M_{i,k}`，再对 100 张图的比值作算术平均。共同 `B_i` 取交接包内已核的成员结果表，不使用 `c665` 汇总中表示前一优化版本的 `row.baseline`。`per_case_speedup.csv` 保留真实逐图比值；`method_core_summary.csv` 的 `mean_speedup` 与 `mean_observed_speedup` 均为实际观测均值。三条曲线在一核心处分别采用 1.056973、1.167562、1.206139，而非统一设为 1；理想线性加速线独立表示一核心为 1 的参照。由于分母是共同的官方情况 A 单核心基线，各方法优化后的单核心结果可以优于该基线。

左侧展示三种全覆盖方法的 1–5 核真实观测曲线与 F1 五核心独立点。右侧把同一组五核心数值按方法分行列出，专门区分相差仅约 0.008 的 `tensor` 和 `F1`。图内不放整图标题和长篇解释；适用条件、一核心口径及方法定义放在 `caption.md`，由 LaTeX 图注和邻近正文排版。图号“5-3”是工作台交付编号，正式稿位置由合稿核定。

## 从固定提交重新生成

在仓库根目录运行：

```sh
uv sync --locked
uv run --locked python src/analysis/fig53_rework.py --figure 5-3
```

该命令只读取交接 ZIP 中的既有结果表，校验全部来源哈希、覆盖与共同分母，生成本目录的长表、汇总表、`validation.json`、PNG、PDF 和 SVG，并更新 `manifest.json` 与 `audit.json`。它不调用求解器或官方评价器。输出 PDF/SVG 为矢量图，PNG 仅供预览；设计宽度为 160 mm。中文字体从本机已安装字体中选取，跨系统重新渲染的图像字节可能不同，数值应相同。

## 交付与限制

- `fig53_p2_speedup.pdf` / `.svg` / `.png`：同次绘制的矢量图与预览。
- `per_case_speedup.csv`：1,600 行，字段为 `case,cores,method,baseline,makespan,speedup,source_commit,result_sha256`，其中 `F1` 只含五核心。
- `method_core_summary.csv`：16 行，各方法和核心数的样本数、真实观测均值及显示规则；保留原有字段以便逐版核对。
- `caption.md`：给论文监督会话的图题、图注与邻近正文建议。
- `validation.json` / `manifest.json` / `audit.json` / `self-check.md`：覆盖、来源、最终文件哈希与 F53-R01～R05 的逐项证据。

本次独立复算的是交接包中的固定汇总表，并核对其中 1,600 个坐标和规定均值；没有重新审计全部官方评价原始文件，也没有进行新实验。图件本身仍须由论文监督会话核对当前正文和实际插入宽度，再由用户作最终验收。
