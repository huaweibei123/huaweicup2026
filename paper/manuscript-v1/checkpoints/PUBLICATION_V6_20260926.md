# v6 冻结论文检查点

本目录按作者冻结的 v6 发布，供固定版本阅读与逐项审阅。v5 及更早检查点的原字节、人工批注 PDF 身份与坐标保持不变；`paper/manuscript-v1/LATEST_CHECKPOINT.json` 指向 v6，但旧批注和验收状态不自动迁移。PR #222 维持 Draft，发布不等于合并或参赛终稿。

| 原件 | SHA-256 | 范围 |
| --- | --- | --- |
| [`v6/anonymous-paper-v6.pdf`](v6/anonymous-paper-v6.pdf) | `8e151bd1cfb1ed8a9e8a14c0c52a626e6c1da034ba404e107d1ea04b62ee08a2` | A4，95 页 v6 检查点 |
| [`v6/result-tables.pdf`](v6/result-tables.pdf) | `36151098ca3b3abfb203bad8fcc729d26ce34ff23a91a4890da2ee1323b8c923` | A4，57 页补充结果表 |
| [`v6/build-receipt.json`](v6/build-receipt.json) | `5c8021efa6624c71f61e679a48a2e4f3d55153507f75bd4465d2aea3414019d4` | 冻结源码、模板和产物清单 |

v6 只处理 AI 辅助使用声明：附录中 7 份原始程序保持原字节（共 1464 行），另有 7 份前置声明的展示版（共 1520 行）。发布者逐份核对去掉声明后与原件字节完全一致，Python AST 一致；原始和展示 SHA 分列。`source/ai-disclosure/` 保存作者使用的声明依据、模板与型号元数据；队友其他程序须由其实际作者依据自己的使用记录补齐，不能把这份模板直接代签为全队历史。正文只在第 7 章数据分析说明和附录来源说明处更新。v5 图件、数据与候选状态不因本次发布自动改变；没有新增 solver/E0/E1/E2 实验。

发布前独立核对冻结目录 106 个文件、59,408,059 字节与作者工作树逐字节一致，整树 SHA-256 `0c805f5ae73b095b1206372c605f8376bf56489f789c8af038e8937ebe8723e6`；41 项源码、6 项模板、22 项图件、TeX 与正文 PDF 共 71 项哈希匹配。`pdfinfo` 核正文 A4/95 页、补表 A4/57 页。冻结包内 `source/figure-sources/capacity/plot.py` 仍是原始 CRLF；本发布分支为 v6 固定路径设置 Git 不转换规则，避免默认 `*.py` 的 LF 归一化改变冻结哈希。作者的 `validation.json` 记录页面和视觉检查范围；发布者不代替完整科学审查、队友逐程序声明、人工语言批注或最终图件验收。
