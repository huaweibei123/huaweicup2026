# v8 冻结论文检查点

本目录发布作者工作树在 2026-09-26 16:11:45 UTC 冻结的 v8，供固定版本阅读和审阅。正文 PDF 为 103 页，补充结果表为 57 页；这里记录作者冻结稿，不代替科学、语言或最终人工验收。

| 原件 | SHA-256 | 范围 |
| --- | --- | --- |
| [`v8/anonymous-paper-v8.pdf`](v8/anonymous-paper-v8.pdf) | `5d806108a559eaf0f18d9d3268efa477674d67ddceb9c03bc7d5b08b0f890cf6` | A4，103 页正文 |
| [`v8/result-tables.pdf`](v8/result-tables.pdf) | `7e477adb4511db7cd3c40c47b2880fc41a60d4ff2001b871c6cd9a9d5193cef7` | A4，57 页补充表 |
| [`v8/build-receipt.json`](v8/build-receipt.json) | `351a5408e09e7208cc6d8bb487bf2cb4be8d6eabe52743fb7f8ed18d19023175` | 构建输入与产物清单 |
| [`v8/freeze-manifest.json`](v8/freeze-manifest.json) | `6cb6f8b33f1e92d3869b79e2553699b9f4c16c9217eec5c1a0a3c92e9755dac5` | 冻结目录的 135 项文件哈希 |

发布者逐项核对冻结清单、41 项构建源码哈希、24 个图文件与两份 PDF，并保留冻结目录的原始字节。v8 的 `source/figure-sources/capacity/plot.py` 仍为原始 CRLF，发布分支设置固定路径的 `.gitattributes`，防止 Git 转换。当前章节、合稿、构建脚本及写作规则随本版同步；旧版 PDF 和批注不覆盖。

本版有 23 个图位、17 条参考文献及 7 个附录程序声明页；第 71 页的 case051 图只作单例诊断。更晚收到的 5-4/6-5 图因语义范围不匹配，本版没有替换。缩览、重点页、字体、引用和排版检查见 [`v8/review/validation.json`](v8/review/validation.json)；留白、理论及 AI 声明的范围限制见 [`v8/review/review-summary.md`](v8/review/review-summary.md)。本次没有新增 solver 或官方评价运行。

`LATEST_CHECKPOINT.json` 指向 v8。v7 和 v8-preview1 的人工批注继续绑定各自 PDF 哈希与原页码，不迁移到 v8。PR #222 保持 Draft，不合并作者分支；用户总验收后再确定最终版。
