# 匿名完整论文检查点 01

2026-09-26。正文：`anonymous-paper-v1.pdf`；逐用例附表：`result-tables.pdf`；整包：`review-package.zip`。

本检查点包含摘要、第1–8章、参考文献、补充数学推导、固定版本说明，以及由1500行冻结CSV生成的完整附表。是可以通读审阅的完整版本，不冒称已完成独立科学审读、Fang汇总图件总验收或算法程序包验收。

图号/标题/图注由LaTeX管理。机制图使用已核对的中文生图，数据图和执行时间线使用官方原件代码绘制。图件清单含SHA-256，未调用新的求解器或评价器。

在项目仓库重建：

```sh
python3 paper/manuscript-v1/scripts/build_checkpoint.py
```

需要现有Pandoc和XeLaTeX。分章Markdown为唯一正文编辑源；不要手改生成的main.tex。

审阅ZIP中保存可独立排版的LaTeX源、已有模板类/字体、所用图、两份PDF、冻结CSV和来源收据。解压后在source目录连续运行两次 `xelatex main.tex`，附表连续运行两次 `xelatex result-tables.tex`。不包含完整算法运行环境，也不表示已在另一台电脑验证。

Fang核对请求：<https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5843634528>。收到回执后按科学正确性、数据身份、可读性与视觉品质择优，避免重复制图。
