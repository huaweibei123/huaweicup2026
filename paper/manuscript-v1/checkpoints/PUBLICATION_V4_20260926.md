# v4 冻结论文检查点

本目录发布作者冻结的 v4 摘要优化检查点。v5 正在另行撰写，未混入本版；v2、v3 与 CP04–06 及其批注坐标继续按各自固定 PDF 哈希保留。`paper/manuscript-v1/LATEST_CHECKPOINT.json` 指向 v4，但逐项语言批注和验收状态不会随最新版自动迁移。

| 原件 | SHA-256 | 范围 |
| --- | --- | --- |
| [`v4/anonymous-paper-v4.pdf`](v4/anonymous-paper-v4.pdf) | `4919ae31aefb3e479c9604f87fe4944d4dc5fa283b46babbe55f1e88c3dac653` | A4，87 页 v4 检查点 |
| [`v4/result-tables.pdf`](v4/result-tables.pdf) | `19abe7aac1ac066ea70980f07b51d6b4f6b84e95368bbf3646c37fd6a4a5fc00` | 补充结果表 |
| [`v4/build-receipt.json`](v4/build-receipt.json) | `3ede2ffab5909b0accad8ad756db001ac84c3cf71337370ecb0546a3dc6e6abc` | 冻结源码、排版源和模板哈希 |

相对 v3，冻结源稿仅 `source/chapters/00-abstract.md` 改动；重建的 `main.tex`、两份 PDF、构建回执、批注锁和验证记录随之变化。v3 的数学审计记录仍留在 v3，不复制为 v4 新审计。v4 目录 69 个文件，共 53,624,492 字节。发布前独立校验 31 项冻结源文件、6 项模板、18 项图件，以及主 PDF、补充 PDF、构建回执和 TeX，共 59 项均匹配；作者目录与发布目录逐文件和整树字节摘要一致。`pdfinfo` 确认主 PDF 为 A4、87 页。

作者验证记录报告无 overfull、缺失或未定义警告，另有 3 条 underfull 排版提示留待 v5 处理；本次不重新构建论文或运行求解器、官方评价器。发布固定原件不代表全文科学、语言、版式或最终用户验收通过。
