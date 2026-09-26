# 6-4 本机验收适配

原作者farmeruncle123，固定babdd74c。原figure.svg/png、原三表、plot.py与提取/获取源码均不变；工作台未执行上传代码。仅修caption的P2/P2笔误为P2无L2/P3只读Cache，补规范pairs/summary/negative与完整audit来源路径。原audit保存在original-audit.json。

原图可在本目录执行 `python plot.py` 从原三表重现。规范表可执行 `python prepare_cache_tables.py --verified raw-pair-verification.json --baseline <固定tensor-per-cell.csv> --out .` 重新生成，不调用实验。500配对实际压缩结果和计划字节全部独立核验；带宽/容量实值及共同config/graph/official身份一致。图面已实际查看165mm预览，四负例保留、三面板可读。来源和证明分别在sources.json/source-verification.json；候选仍待用户总验收。
