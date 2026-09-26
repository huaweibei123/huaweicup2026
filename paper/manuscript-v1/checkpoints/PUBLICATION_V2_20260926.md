# v2 冻结论文检查点

本目录发布论文组织任务冻结的正式 v2 检查点，供固定版本阅读与后续批注。作者的分章 Markdown 和 v3 在途写作工作区保持原状；`v2-preflight` 是排版预检，未纳入本次发布。

| 原件 | SHA-256 | 范围 |
| --- | --- | --- |
| [`v2/anonymous-paper-v2.pdf`](v2/anonymous-paper-v2.pdf) | `e6b5a08a9b2b1cad52526a710916e9f209167aa80ca28a818e42824002e15209` | A4，86 页正式 v2 检查点 |
| [`v2/result-tables.pdf`](v2/result-tables.pdf) | `a8e78a888b6e79bdb84bd021311731ab94f6fcdca62c538b3403a557e9c332af` | 补充结果表 |
| [`v2/build-receipt.json`](v2/build-receipt.json) | `d6287d42b34f79be05d7eed03f9b394aa46ef955c8333fa260db1920361a0746` | 31 项冻结源文件、排版源和模板哈希 |

[`annotation-lock.json`](v2/annotation-lock.json) 将 v2 PDF 与补充表的哈希锁定，并声明旧检查点的人工批注仍按原 PDF 哈希和坐标定位。目录中同时保存实际 TeX、图件、模板/字体、31 项冻结章节与代码/数据源，以及 [`validation.json`](v2/validation.json)。本次独立复核了两个 PDF、锁定的构建回执、TeX、31 项源文件、模板哈希及 18 项图件哈希；`pdfinfo` 为 A4/86 页。

构建记录列出 12 条参考文献、7 份核心代码；`validation.json` 报告代码 1464 行及所查页码。上述是冻结原件与文件一致性检查，不代替语言、事实、科学、整稿版式或用户最终验收。此次发布没有运行 solver、Task 或官方评价器，也没有改动 CP04–06 原件及其批注坐标。

**冻结后的已知科学待修项**：后续 v3 数学审计发现，附录 B.3 用所选操作的 head/tail 最大值作共同阈值，不保证对每个操作成立；集合还须限定同一 Pipe。该结论来自代数反例，并非新的官方评价实验。v2 PDF 与源文件保持原字节供追溯，修正只进入后续独立 v3 版本；不能将本检查点标为数学验收通过。
