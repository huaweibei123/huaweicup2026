#!/usr/bin/env python3
"""Assemble the editable chapter sources without rendering figures or LaTeX."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ['00-abstract.md','01-problem.md','02-assumptions.md','03-framework.md',
         '04-p1.md','05-p2.md','06-p3.md','07-experiments.md','08-conclusion.md',
         '09-references.md','10-appendix.md']

def main():
    contents=['# 多核神经网络处理器的计算图切分与调度优化\n\n'
              '> 完整文字稿；由分章 Markdown 自动合并。图稿说明尚未替换为实际图件，'
              '本文件不是最终提交检查点。请编辑 chapters/ 后重运行 assemble_markdown.py。\n']
    for name in FILES:
        contents.append('\n<!-- chapter-source: chapters/'+name+' -->\n\n'+(ROOT/'chapters'/name).read_text())
    (ROOT/'manuscript.md').write_text('\n\n---\n\n'.join(contents).rstrip()+'\n')

if __name__=='__main__': main()
