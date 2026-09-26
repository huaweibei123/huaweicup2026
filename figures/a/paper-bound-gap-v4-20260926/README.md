# 图 7.5-1 独立候选 v4

此目录只重绘冻结 v7 的 P2 下界图，修正纵轴和图注的量纲表达；不改冻结稿、既有图、数据或评测器，不进行求解或评价。

## 复现

在本目录运行，先将 V7_SOURCE 指向冻结检查点的 v7/source 目录：

```sh
python draw_bound_gap.py --v7-source "$V7_SOURCE"
```

使用现有 Python 环境的 Matplotlib 3.11.2、Pillow 12.3.0 及模板字体；数值输入仅为 `v7/source/data/figure-inputs/p2-audit.json.gz` 和 `v7/source/data/summary.json`，相对路径与 SHA-256 见 `source-record.json`。冻结 v7 原图和整稿仅作只读对照。脚本读入 `core_comparison[k].new_mean_B_over_M` 作为 $\operatorname{mean}(B/U)$，`relaxation_ceiling_mean_B_over_LB` 作为 $\operatorname{mean}(B/L)$；逐核检查样本数为 100、前者与 `summary.json` 的 P2 平均基准加速比一致、两者均为正且下界不超过上界。输入中 `M` 表示实测 Makespan，即本图的 $U$；`LB` 表示完成时间下界，即本图的 $L$。

产物 `fig-bound-gap-v4.pdf`、`.svg` 为矢量图，`.png` 和 `preview-160mm.png` 为 300 dpi 位图。画布宽 160 mm；`preview-160mm.png` 是实际纸面宽度的导出预览。图注建议见 `caption.md`。`SHA256SUMS` 列出本目录文件的哈希，生成清单时不包含清单自身。

已在 160 mm 宽预览检查中文、图例、轴标签、线型与阴影可辨，未见重叠或缺字。此检查是图件视觉检查，不等于论文重排或人工最终验收。
