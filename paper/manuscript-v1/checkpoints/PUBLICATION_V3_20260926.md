# v3 冻结论文检查点

本目录发布论文组织任务冻结的 v3 检查点，供固定版本阅读与后续批注。v2、CP04–06 及各自人工批注的 PDF 哈希和坐标保持原状；作者的在途章节、`v2-preflight` 和另行比选的三张 P2/P3 候选图没有纳入本次发布。

| 原件 | SHA-256 | 范围 |
| --- | --- | --- |
| [`v3/anonymous-paper-v3.pdf`](v3/anonymous-paper-v3.pdf) | `f9009cf38df083d0130ea7438c9ec44a77c405f818a6856b79f389aa739e0fca` | A4，87 页 v3 检查点 |
| [`v3/result-tables.pdf`](v3/result-tables.pdf) | `c673b6f9e4063022a4d5fb1d46462d87a941f901930c5b752321ba3107321518` | 补充结果表 |
| [`v3/build-receipt.json`](v3/build-receipt.json) | `3f02bb996647eaa19317c1386d21032b3ef7ffce068f9bf342488591fa1c996c` | 31 项冻结源文件、排版源和模板哈希 |

[`annotation-lock.json`](v3/annotation-lock.json) 锁定本版两份 PDF 的哈希；目录另存实际 TeX、图件、模板/字体、冻结章节、代码与数据、数学审计及 [`validation.json`](v3/validation.json)。发布前独立核对了两个 PDF、构建回执、TeX、31 项源文件、6 项模板和 18 项图件哈希，整目录 71 个文件在作者源目录与独立发布目录的字节摘要一致；`pdfinfo` 报告 A4/87 页。构建记录列出 12 条参考文献、7 份核心代码；验证记录报告 1464 行代码和两份 TeX 日志零警告。这是来源及文件一致性核对，不代替重新构建、完整科学或用户语言验收。

相对 v2，本版收紧附录 B.3 的同 Pipe 集合、逐操作共同阈值及跨核指示变量，补充 B.4 固定参考环境，并修正摘要/因果断言、依赖投影和 FIFO 总字节容量语义；具体审计在 [`v3/review/mathematical-audit.json`](v3/review/mathematical-audit.json)。这些修改属于作者冻结版的内容，本次发布未额外运行 solver、Task 或官方评价器。三张另行比选的 P2/P3 候选图不在此版中。v3 仍待用户语言、科学与最终版式验收，不应标为终稿。
