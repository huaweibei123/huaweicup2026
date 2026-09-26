# 复编译本检查点

在本目录使用既有 XeLaTeX 安装，连续执行三次：

```sh
xelatex -no-pdf -interaction=nonstopmode -halt-on-error main.tex
```

再导出：

```sh
xdvipdfmx -E -q -o anonymous-paper-v11-rebuilt.pdf main.xdv
```

新导出文件另存；不要覆盖已冻结用于批注的 PDF。`source/chapters` 是 Gemini 的固定 Markdown，LaTeX 使用已交付格式并转换表格、附录标题及引用，实际编号依赖编译。复编译日期可能改变 PDF 字节哈希。
