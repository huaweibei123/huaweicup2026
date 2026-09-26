# 冻结 v8 流程图文字调整入口

`inventory.json` 由 `python3 figures/a/flow-language-20260927/inventory.py` 从固定 Git 图源生成，记录实际入稿的四组流程图、五份可编辑 Draw.io 的文字单元 ID、原文、原件 SHA-256 及连线拓扑摘要。P1 图源为 `83e03c093af991ec7414f80787984726ebdea329`；P2/P3 图源为 `4eb1dd426b25bde8871a31835416676314a50519`。清单是待审输入，不代表文字已改、科学内容已核或图已通过。

用户要求图中只保留读懂流程所需的清楚短标签。定义、适用条件、例外、评价预算、结论适用范围及解释须保留在正式图注或紧邻正文；图内、图注、正文均按 `docs/paper-acceptance/LANGUAGE_STANDARD.md` 审核。模型对每个文字单元提出 `keep_short`、`move_to_caption` 或 `split` 的建议，并给出原文、改后图中文字、应移文字与科学疑问。该建议由论文监督会话核对固定算法及 v8 上下文，再由验收台改可编辑图源和导出；论文监督会话负责正式 LaTeX 图注/正文和入稿后的科学、版面核对。

每张改图另存新版本，保留生成脚本、Draw.io、PNG/PDF、图注移位清单和可复算的来源。改图前后核对文字单元 ID、连线数与端点；任何需要修改拓扑的建议先单列科学问题，不因缩字顺手改算法。最后在论文实际插入尺寸目视检查，旧 v8 图件与 PDF 不原地覆盖。

## 2026-09-27 候选交付

`delivery.json` 为五份可编辑图源逐一登记冻结来源、改图、矢量 PDF、160 mm 宽纸面预览与图注候选的 SHA-256。四组图依次位于 `p1/`、`p2-local-cut/`、`p2-three-plans/`（a、b 两面板）、`p3-forest-decision/`。各 `build_compact.py` 或 `build_language.py` 读取本目录内按固定 Git 对象校验过的原 Draw.io，产生另名改图；原件不覆盖。

本轮把图内解释按对象转移：P1 的四块阶段预算、异常和回退说明转至 `p1/caption-proposal.md`；P2 局部割的公式、两行同组链说明和最多求解次数转至 `p2-local-cut/caption-proposal.md`；P2 三方案的门槛、两种 COPY 口径和错误分支保留于 `p2-three-plans/caption-proposal.md`；P3 的适用条件、差值定义、理论保证边界与下界计算说明保留于 `p3-forest-decision/caption-proposal.md`。图内只留能够识别对象、流向、分支与结果的标签，不用截去解释后遗失论文论证。

五份改图已重新导出 PDF 并以 160 mm 纸面宽度预览检查；源/改图的连线 ID、端点及容量标签逐项一致（P1 8、P2 局部割 8、P2 三方案 a 10/b 5、P3 16）。此检查只覆盖图形和来源完整性，图注候选仍需论文监督会话按固定求解器核对，正式 LaTeX 插入宽度、页面及图号仍需随新版稿复查。冻结 v8 PDF 和原图继续保留。
