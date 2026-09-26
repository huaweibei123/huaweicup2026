# 复编译 v13

在本目录连续执行三次（已安装 XeLaTeX）：

```sh
xelatex -no-pdf -interaction=nonstopmode -halt-on-error main.tex
```

然后导出新的文件，勿覆盖用于批注的冻结版：

```sh
xdvipdfmx -E -q -o anonymous-paper-v13-rebuilt.pdf main.xdv
```

主稿不依赖网络。目录页码、编号与引用目标由编译计算。原始 Markdown 位于 source/chapters，实际排版位于 main.tex。结果附表与外置完整代码沿用 v12 原件。工具版本及生成日期可能改变 PDF 文件哈希。
