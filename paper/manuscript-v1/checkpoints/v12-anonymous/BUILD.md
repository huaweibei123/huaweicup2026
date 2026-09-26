# 复编译 v12

使用既有 XeLaTeX 安装，在本目录连续执行三次：

```sh
xelatex -no-pdf -interaction=nonstopmode -halt-on-error main.tex
```

然后导出新文件：

```sh
xdvipdfmx -E -q -o anonymous-paper-v12-rebuilt.pdf main.xdv
```

请勿覆盖已用于批注的冻结 PDF。日期与工具版本会影响 PDF 字节哈希。主稿不依赖网络；当前编号、目录页码与引用目标由编译计算。补表 result-tables.pdf 及独立程序附件保持 v11 原件。原始 Markdown 位于 source/chapters，实际排版位于 main.tex。
