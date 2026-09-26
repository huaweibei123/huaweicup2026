# 图6.7-1下一版排版候选：排序与完整方案评价

原图位于 v7 PDF 第47页，源稿 SHA-256 `51cd3c6fefd4885c7978bf46d6ad279297c170f3c8b590ae649aa4963df51ff0`。本候选从 v3 可编辑图源另起，不修改冻结稿。改为 `(a)` 非交错归约树内部结果的排序、`(b)` 树状完整方案与先行方案共用官方评价预算两块内容；整图长解释和符号定义移入 [caption.md](caption.md)。

`build.py` 为当前可编辑图的确定性来源，生成 `.drawio`；Draw.io 导出 SVG、PDF 和 PNG。160 mm 纸面宽预览见 `preview-160mm.png`。重建命令：

```sh
python3 build.py
drawio -x -f svg -e -o p3-forest-decision.svg p3-forest-decision.drawio
drawio -x -f pdf --crop -o p3-forest-decision.pdf p3-forest-decision.drawio
drawio -x -f png -s 2 -b 16 -o p3-forest-decision.png p3-forest-decision.drawio
sips -Z 1890 -s dpiWidth 300 -s dpiHeight 300 p3-forest-decision.png --out preview-160mm.png
```

图内保留适用结构、`hᵢ−rᵢ` 排序、内部结果峰值保证、三个先行检查、完成时间下界的可得/不可得分支、三次共用预算和官方 E0 严格改善条件。下界不支持时继续，不以此剪枝；E0 校验失败保留原方案。固定语义来源为提交 `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1` 的 `forest_memory_order.py`、`forest_solve.py` 及先行方案模块。

已在约160 mm宽度目视核对中文、连线、数值与文字遮挡，并由 PDF 文本提取核对主要节点未缺失；`.drawio` 保留可编辑文本与箭头。没有运行求解器或评价器，不宣称科学结论、论文整页版面或人工最终验收通过。`SHA256SUMS.txt` 列出实际文件哈希。
