# v7 冻结论文检查点

本目录发布作者工作树已冻结的 v7，供固定版本阅读和审阅。相对 v6，正文只修改摘要；其他章节、图件、结果数据和附录代码保持原字节。摘要重新组织三问的方法与主要结果，并突出关键数值；这里记录的是作者冻结稿，不代替科学、语言或最终人工验收。

| 原件 | SHA-256 | 范围 |
| --- | --- | --- |
| [`v7/anonymous-paper-v7.pdf`](v7/anonymous-paper-v7.pdf) | `51cd3c6fefd4885c7978bf46d6ad279297c170f3c8b590ae649aa4963df51ff0` | A4，95 页正文 |
| [`v7/result-tables.pdf`](v7/result-tables.pdf) | `80e090e9fae0d246cd76f127d8440e754f328bff40da570b5fcf8f1571958ac9` | A4，57 页补充表 |
| [`v7/build-receipt.json`](v7/build-receipt.json) | `203b195b5480fa2f3301496697d2d4a548ee89626c46ed33a67f77230557300e` | 冻结源码、模板和产物清单 |

发布者将作者冻结目录的 117 个文件、60,033,200 字节逐文件复制并复核哈希，整树清单 SHA-256 为 `e0da467829d427b41d3b2bee1c87f44967999324ea561859767f45d50f62211e`。独立核对构建回执列出的 41 项源码、6 项模板、14 项可编辑图源、1 项辅助脚本、22 项图件、TeX 与两份 PDF，均匹配。`pdfinfo` 核正文 A4/95 页、补表 A4/57 页；摘要页已目视检查。v7 的 `source/figure-sources/capacity/plot.py` 保留原始 CRLF，发布分支以固定路径的 `.gitattributes` 规则防止 Git 转换原字节。

`LATEST_CHECKPOINT.json` 指向 v7；v6 和更早 PDF 及人工批注坐标不迁移。作者工作树的在途正文、候选新图、2025 参考论文和其他草稿均不在本次发布范围。PR #222 保持 Draft，不合并作者分支；本次没有新增 solver、官方评价或云端实验。
