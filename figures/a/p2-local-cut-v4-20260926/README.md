# 第33页局部最小割图候选

以已入稿 v3 可编辑图源为基础另存候选。冻结 v7 PDF 未改。新图用 Fₑ 表示“超边 e 在调整区域外已固定触及的核心集合”；正文最大流标量统一为 fₘₐₓ、超边全集为 𝓔。图中例 A/B 的割容量对应各自给定分配，不是未加锚定约束的自由网络最大流。计算工作量在图内标明模拟时钟周期；原图底部橙色长说明移到 [caption.md](caption.md)。网络容量、偏移和工作量检查保留。

build_local_cut.py 确定性生成可编辑 Draw.io 文件与 semantics.json。Draw.io 导出 SVG、PDF、PNG；preview-160mm-300dpi.png 是约160 mm宽的预览。SHA256SUMS.txt 给出全部源与导出文件的字节哈希。重建命令为运行生成器，再对 Draw.io 源分别执行 svg、pdf、png 导出；README 不作为入稿图注。

固定语义依据：c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f 的 src/q2_nikolastarx/binary_hypercut.py 和 gap_hyperrefine.py。本件没有运行求解器或官方评价器，也没有修改论文正文。作者须按 [caption.md](caption.md) 同步正文符号，再在新检查点验收整页版式、图注和科学含义。
