# v9 冻结论文检查点

本目录发布作者工作树冻结的 v9，供固定版本阅读和审阅。正文 PDF 为 123 页，补充结果表为 57 页。此版本是人工审阅稿，不代表论文科学、语言或最终人工验收已完成。

| 原件 | SHA-256 |
| --- | --- |
| [`v9/anonymous-paper-v9.pdf`](v9/anonymous-paper-v9.pdf) | `0def584bf9f031d0c754a96c88abe356b554d6ef373fd07276e844d8843fef8a` |
| [`v9/result-tables.pdf`](v9/result-tables.pdf) | `c913309fd0cf7851f0ca7bc2127e1e6b6c4edb50719a80c5c02abc06fbcd7fde` |
| [`v9/build-receipt.json`](v9/build-receipt.json) | `f5113975a92103c7e0463ab6228ca9ff49cae74d97d893de3cf47e0a608fc762` |
| [`v9/freeze-manifest.json`](v9/freeze-manifest.json) | `5dda78f83e81c6a538572ee4d6f4f14782beead868d85a55049f3888a9ecedcd` |

发布者从作者冻结目录逐项核对清单登记的 284 个文件大小和 SHA-256，复制后再次核对，目录另含清单自身。两份 PDF 的页面数和上述哈希已独立回读。冻结包内的 `source/`、`figures/` 和审查收据保持原字节；不修改含 CRLF 的图源。`LATEST_CHECKPOINT.json` 指向 v9，旧 v8 和其人工批注仍绑定旧 PDF 哈希与页码。

作者的 [`v9/README.md`](v9/README.md) 与 [`v9/review/validation.json`](v9/review/validation.json) 记录本轮修改和验证范围：29 幅编号图、21 条实际引用文献、94 个目录目标、41 个源码和 30 个图文件的哈希检查，以及 PDF 视觉抽查。构建日志保留一处轻微 underfull 警告；没有新增求解器或官方评价运行。新收到但未纳入本轮冻结收件截点的图件留待后续批注轮，不覆盖本包。

PR #222 保持 Draft，不合并作者分支。发布只固定和公开当前 v9 字节，不替代后续论文整页适配、科学复核、官方投稿格式核验或用户总验收。
