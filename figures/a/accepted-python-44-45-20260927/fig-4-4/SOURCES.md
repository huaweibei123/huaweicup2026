# 整稿来源与主张边界（编辑资料，不进入匿名正文）

下列固定源码、作者原稿和讨论构成整稿的来源。整稿是重新组织的论证，不替换原作者版本；不将Pro回复、源码注释或作者报告自动当作已独立证明的结论。

## 三问主算法与结果

| 内容 | 固定入口 | 本文采用范围 |
|---|---|---|
| P1完整算法 | [834d8c9 / branch_refine](https://github.com/huaweibei123/huaweicup2026/blob/834d8c957538ee069c66aadac9509552a4cc69d7/src/q1/branch_refine.py) | 基础候选、响应/前沿细化、三片援助的完整策略 |
| P1三片构造 | 同提交 `src/q1/branch_aid.py` | 波次/角色守卫、X/Y/J、Task帽与软预算 |
| P1全量 | [a1bb445 / 全500](https://github.com/huaweibei123/huaweicup2026/tree/a1bb4451cd85c46b32bb928d57c81e22cfeca1a6/results/a/p1-branch-refine-full500-20260925) | 500新solver、1130在线E1、48新E0＋452核同复用 |
| P1上游归属 | [Fang fork-rank / 0bf12cf](https://github.com/huaweibei123/huaweicup2026/commit/0bf12cfe3164b155b02cc85896dabdfee72f9d37) | 分叉前沿的上游贡献，保留代码及方法归属，不称整稿者独创 |
| P2完整算法 | [c66559a / adaptive_hypergap_guarded](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/adaptive_hypergap_guarded.py) | 三候选、16链区域、预Step2超图费用、完整E2选择 |
| P2全量/负例 | [00d311e / P2结果](https://github.com/huaweibei123/huaweicup2026/tree/00d311ed0eea0fd86f9840df406956041a7c192a/results/a/q2-nikolastarx) | hypergap全500及C04六格，二者不混主成绩 |
| P3完整算法 | [311322b / forest_solve](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/forest_solve.py) | 完整Forest策略；树排序代理与候选剪枝分别限定 |
| P3全量原件 | [19bebf3 / revision2](https://github.com/huaweibei123/huaweicup2026/tree/19bebf35205d23fdd832781540f8879da52eeb62/results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft) | 原名虽含draft，身份/分母修正后的正式固定500配对原件；配合后续审计使用 |
| P3审计与R9F | [8416300 / P3材料](https://github.com/huaweibei123/huaweicup2026/tree/8416300c7245925795aaa3acc64d4d5b31fa13d5/results/a/q3-nikolastarx) | Forest审计、同计划Cache审计、R9F最终CSV和负消融 |
| 统一理论作者稿 | [229b322 / 三问统一理论](https://github.com/huaweibei123/huaweicup2026/blob/229b322a9778093782683841f3050db1dbdaabfc/paper/notes/a-theory-coherence-final.md) | 必要计算投影、窗口/原子/残余等待组合；新公式无新500证书 |

原章节继承与版本索引保留在 `paper/sources/manifest.json`，本目录不改写其字节一致性含义。P1旧稿的v4数值已在整稿中替换为834；P2/P3长研究分支按是否进入主算法重新安排到正文、负例或数学附录。

## Pro与对齐资料

Pro归档按main `a32dff7f7992299a009a6cebcb166a897b764d46`查阅；详细入口及条件风险见本目录 `DETAILED_OUTLINE_AND_ALIGNMENT.md` §5。15 chats / 593跟踪文件 / 16 ZIP CRC为归档复核事实，48条附件或附件组无原字节，不把链接存在当作已归档代码。

用户提供的两份总体框架/写作PDF、2025A参考论文及两张Task/Pipe截图均只作为结构与呈现参考。本轮没有把这些用户本地原件上传到PR。图中他人的具体数字未进入本队成绩表。

## 外部文献

正式引用和核对入口见 `chapters/09-references.md`。经典图划分、超图和Sethi–Ullman类思想保留已有研究归属；本文的新意应落在题面语义下的构造、守卫、组合、证明适配与完整证据，不作未经文献检索支持的首创声明。
