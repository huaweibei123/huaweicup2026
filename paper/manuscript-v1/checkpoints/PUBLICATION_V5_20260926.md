# v5 冻结论文检查点

本目录发布作者冻结的 v5 图文整合检查点，供固定版本阅读与逐项审阅。v4 及更早检查点和各自人工批注的 PDF 哈希、坐标保持原状；`paper/manuscript-v1/LATEST_CHECKPOINT.json` 指向 v5，但旧批注与验收状态不随最新版自动迁移。

| 原件 | SHA-256 | 范围 |
| --- | --- | --- |
| [`v5/anonymous-paper-v5.pdf`](v5/anonymous-paper-v5.pdf) | `c2543e13146b5c75dc8e2103e983c07c5db746b8e98129fff40f2721f1d29233` | A4，92 页 v5 检查点 |
| [`v5/result-tables.pdf`](v5/result-tables.pdf) | `4cd597b2a46360763fa6f1b5bddcebd179b37b268ab8eb11aa5cdc3681c27529` | A4，57 页补充结果表 |
| [`v5/build-receipt.json`](v5/build-receipt.json) | `7c70c87f498deae1254bcb5bbc2c85b8f11b747883ca3dde7659aa06b8e9b990` | 冻结源码、排版源和模板哈希 |

相对 v4，v5 保留新版摘要，加入四张现有候选图，分别位于正文第 28、33、35、47 页；第 5、6、8、10 章的图文相应调整，并修复表格编号、重复小节序号与长公式排版。作者的 `review/figure-selection.json` 标明入稿图件仍供批注和复核，不等于图件、科学或用户最终验收。旧 1500 格固定数据与七份附录代码的冻结哈希和 v4 相同；本次没有新的求解器或官方评价运行。

发布前独立核对 31 项冻结源码、6 项模板、22 项图件及正文 PDF、补表、构建回执和 TeX，共 63 项均匹配；作者源目录与独立发布目录的 91 个文件、59,299,523 字节逐字节一致。`pdfinfo` 确认正文 A4/92 页、补表 A4/57 页。冻结包内 `source/figure-sources/capacity/plot.py` 原件采用 CRLF；发布分支在根 `.gitattributes` 对该唯一固定路径设置不转换规则，并以原始字节写入 Git blob，避免默认 `*.py` 的 LF 归一化改变其哈希。作者的验证记录包含全 92 页缩览和重点页检查；发布者另渲染抽看第 28、33、35、47 页，四幅图及正文均可见。本次发布不代替重新构建、完整科学审查、语言批注或最终版式验收。
