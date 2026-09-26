# v9 排版修订与完整 LaTeX 交付

负责人：@yuanzhifang30-sudo

session：yuanzhifang30-sudo/s-01a0df7fdd1e7ed2bd33463b30bdf5fc

分支：codex/paper-v9-layout-final-20260927

沟通 Issue：https://github.com/huaweibei123/huaweicup2026/issues/217

1. **任务目标**：依用户批准的格式审计修改 v9 衍生 revision03，并把主 PDF、完整 LaTeX 和核查记录交队长。
2. **输入文件**：用户提供的 v9-format-01 衍生 revision03，133 页；固定输入 PDF SHA 见交付 package-manifest.json。官方格式附件2、模板附件3、用户给定格式说明；只读接收 PR237 固定交接。
3. **输出要求**：paper/manuscript-v1/layout-revisions/v9-layout-04/，包含 140 页主 PDF、完整源码 ZIP、变更 diff、核查和 Word 实测证据。正文首行缩进两字，图注/续表小四宋体，图表章编号与题注位置沿用用户要求。
4. **限制条件**：用户明确保留目录、封面自行做、图内文字和图片不改；不改数据、算法或代码；不接管语言监督移动中的 v10 章节稿。新增求解/评价调用为 0，不启用 Actions。
5. **验收标准**：实际 latexmk 编译退出0，无越界/未定义引用警告；29图注实测12bp，218段脚本及1段人工定位首行24bp；140页连续页脚与边界检查；41图表区域视觉检查；30图件、12数据、15代码/清单哈希与输入相同；ZIP 171项CRC、170项清单哈希、48项本地编译输入封闭性通过。
6. **截止时间**：本次用户要求完成后直接交队长，2026-09-27 Asia/Shanghai；不另扩实验或模型预算。

## 交付记录

平台：Windows，TeX Live 2026 / XeLaTeX / latexmk，本机 Word16.0 宋体12bp单倍样张。源目录执行 `latexmk -xelatex -interaction=nonstopmode -halt-on-error -jobname=anonymous-paper-v9-layout-04 main.tex`。Word样张相邻基线中位数约15.6bp，采用正文15.6bp；官方模板导出页脚基线距底部18.1695mm，采用18.17mm。

完整 ZIP 包含 PDF、source、离线图表对比、原57页逐例补表及源码、数据/代码、字体、真实路径映射与说明。原补表作为数据附件不改，不在本次主稿图表版式验收中。原稿页数不构成官方篇幅限制；增加页数来自字号/行距/分页，未删科学内容。

已读：用户当前AGENTS目标与session协议；full查收8话题1122评论的索引，仅按专项读paper/格式交接/公共通知，没有宣称全账号历史已读；Issue217最新格式相关12评论、Issue15#5849863670；PR237固定0b770788的PUBLICATION_INDEX/HANDOFF/独立审核；语言标准ccf4722b。本次只读交接，未覆盖快照或新章节。质量Makespan与端到端墙钟分开，5–10分钟建议不当硬门槛，限制次数不等于非暴力设计。

限制：图内字号按用户新要求不改、目录保留、无正式封面，不能声称官方严格提交验收完成；代码外移和精简属于另一内容版。对源数据与科学结论不作新增独立复核；队长收件、已读和最终接受待其回执。
