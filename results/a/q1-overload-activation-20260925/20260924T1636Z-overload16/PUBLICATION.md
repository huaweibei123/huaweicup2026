# overload16 发布核对

本文件仅整理已完成的数据，新增 solver/E0/E1/E2 调用均为0。

- 算法source：`3c6e41b938c764d207de45584fb526c64f4eb845`。
- 实际runner：`79d3f271ae63039e4fc969e08120f90c87e832db`。
- 原始data：`8f0009ac4a934c2161943b70530e418eb55f9366`。
- 本分支数据汇合：`3215c0416ff189e3f584bdb20b30b9d85a7a109a`。
- delivery：本报告所在的后续固定提交，由签名enqueue使用完整40位SHA；该SHA不是算法source或实际runner。

新16图全部成功、固定Git预检16/16eligible，包括031/032/057/077四个质量退步方案。
原两图加本16图，完整18激活图相对原bounded为14改善/4退步；旧heavy5为4改善/068一退步。
eligible并不表示改进或入榜赢家。18图的均值只对这一预声明子集有效，不称全100成绩。

发布流程为本分支commit/push → PR124正文更新 → 既有签名enqueue。入队、已发送、中央accepted、
eligible、赢家和独立算法验收分别记录；本文件不预先声称队列已送达或中央已接收。
报告与对照的可复核入口见本目录README、activation18-comparison.json和heavy-comparison.json。

本次只更新报告；不更改算法、冻结官方程序、原batch/feed/结果，不写中央账本，不同步研究镜像。
