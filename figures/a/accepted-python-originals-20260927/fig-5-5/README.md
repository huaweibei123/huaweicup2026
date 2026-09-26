# 图5-5｜工作台数据与排版修订

原作者：lyx0217；原交付96e819b7049c15761b60e271d621bd6505a26522 / figures/a/p123-fig-5-5-lyx-20260926。原稿远端保留。本独立副本改用任务指定c665完整500格，不能与原budget批次混用。

来源固定提交、路径、哈希见sources.json。下载这些文件（大文件用git/blobs）至一个sources目录，然后运行：

```sh
python prepare_review_tables.py --sources <sources目录>
python plot_local.py
```

仅执行本包自编提取/绘图代码，未执行上传脚本。prepare_review_tables逐格核对summary与10份feed的6项指标和身份，验证100×5唯一坐标；source-verification含两份原始进程和gzip官方结果抽查。全部500结果未逐份重新解压/E0重跑，此边界保留。normalized CSV保留压缩文件与未压缩原件两种SHA，不能混为一项。字体Microsoft YaHei，165.1mm宽，8–11pt；PNG/SVG/PDF同一代码生成。最终定稿后计算audit。
