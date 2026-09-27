# 论文调整清单与完整逐用例附表交接

负责人：@yuanzhifang30-sudo，session `yuanzhifang30-sudo/s-02c2e2990fc5405cbdcda9a87fff5a6e`

分支：`codex/paper-appendix-handoff-20260927`

沟通：[Issue217](https://github.com/huaweibei123/huaweicup2026/issues/217)；[会话登记](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5851222933)

1. **任务目标**：整理本会话所有已知论文调整项，交队长统一修改；制作完整可用逐用例附录。用户追加要求在不改变题面覆盖前提下压缩57页结果表。
2. **输入文件**：v9-format-01摘要05及57页附表、用户提供题面DOCX、冻结all-results.csv；CSV与v13-public `f1e63781adcb6ce7506b5e8297f0213ad57de5bb`同字节，身份见交付包。
3. **输出要求**：`paper/review-deliveries/20260927-appendix-handoff/`内调整清单、28页PDF、可接入TeX、重建/核验脚本、原数据及来源、PDF全量提取结果和核验报告。
4. **限制条件**：不改数据/基线/正文；不接管其他格式会话主TeX；0新增solver/E0/E1/E2。小四宋体、单倍行距，必要指标与所有用例不能删。仅免费Git/Issues/PR，不启用Actions。
5. **验收标准**：全部100个用例 × 三题 × 1—5核完整，另500同方案无L2配置；实际PDF提取2000条配置结果，6000数值全同，缺失/重复/错误0。28页全部渲染、代表页放大检查。主稿集成和队长最终验收另记。
6. **截止时间**：用户本轮要求交付，未设具体时刻。

## 交付记录

Windows使用bundled Python、XeLaTeX、Poppler；命令见包内README。实际结果：57→28页，减少29页（50.9%）。P1/P2左右合排，P3同用例横向配对；保留原1500项求解时间。1000版面数据行承载2000配置结果，非删掉1000条数据。PDF记录与CSV全部6000数值一致；1500图哈希与100份官方文件一致。全部字号、行间距及边界核查见verification.json。

此为作者构建与数据转录一致性验证，不是新的官方评价或全量方案合法性复评。队长当前v13主附录接入已交另一格式会话，本包只提供组件。数据、图件和代码实验证据身份不得被新排版版本替代。
