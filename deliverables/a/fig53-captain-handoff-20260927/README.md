# 图5-3 半成品修改交接（非验收终稿）

收件人：NikolaStarx（队长）。用户已把5-3交队长修改，本工作台停止改图。这里是实际文件包，不是要求自行寻找附件的通知。

## 从哪里开始

- `original/`：LYX当前待修版本 e5b785c96f3c589cf3029c62f76fea67dcd7a90c 的11件原文件，PNG/SVG/PDF、plot_figures.py、两份CSV、图注、README、manifest及audit，字节不改。已与工作台提交4f0eff7bd72744c8ba770d9c7d4e625a的11项SHA全部核对相同。
- `review/fig-5-3-note.md`：上一轮集中反馈原文，稳定问题编号F53-R01～R05、执行步骤、完成判据及参考均值；`task-standard.md`为本图技术标准。
- `inputs/`：按反馈实际取到的tensor/gap各500格、F1仅五核100格，以及c665完整500格summary。四文件均由固定Git blob取字节，来源与SHA见source-manifest.json。不需要新增solver或E0实验。

## 必须处理的五项

1. F53-R01：当前只画q2-adaptive-budget，缺tensor/gap/c665完整对照及F1五核独立点。三完整方法各100×5；F1仅k5，不拼接另5个k3样本。方法和版本分别标注，不能把此比较称单模块消融。
2. F53-R02：全部方法用共同官方A单核分母。三份per-cell.csv的baseline_cycles为已核固定分母。**c665 summary每行baseline是旧优化算法，不可用作官方A分母。**逐例B/M再取算术平均；主曲线k1展示1，真实优化k1观测另存。原图86例/430格分母有误。
3. F53-R03：生成规范长表case,cores,method,baseline,makespan,speedup与method,cores,n,mean_speedup汇总；F1机器字段精确F1。不要用缺测0补齐。
4. F53-R04：发布实际可运行的仅绘本图命令；原声明src/analysis/p123_figures_lyx/plot_all.py在该固定提交不存在。按包中相对输入或显式参数执行，勿依赖本机gitignored输入，不执行整套实验。
5. F53-R05：全部图、源、表和文字先定稿，再按最终Git LF字节生成manifest/audit。原audit中7项是CRLF副本哈希，与远端LF不符；本交接保留此原始问题，外层source-manifest.json记录实取字节正确哈希。

## 已核与边界

原budget表500坐标及其内部算法均值正确，但不能替代指定方法/分母。原PNG已目视可读；k2标注与理想线交叉是重绘时的排版建议，不是新增门槛。历史退回原文的标准SVG DOCTYPE误报已由工作台兼容修复，队长无需删除标准声明。包内原作者self-check/audit是历史声明，不等于本工作台通过。

审查记录复用了既有100份单核原件核查，并抽取002重新核SHA；没有重审1500份官方原始结果或重跑评价器。此包只是待修半成品和可用输入，不是论文最终版，也不替代用户总验收。

## 交回

队长独占5-3修改范围；其他图由本工作台或farmer按原安排处理。请在Issue15回复实际接收包的固定提交/ZIP SHA以及接手会话；完成后提供新固定提交、成图、可编辑源、正确CSV、图注、真实再生成命令、最终audit及逐项F53-R01～R05关闭证据。请保留原稿，在新修订目录/提交中改。发送成功不等于对方已读。

**当前版本澄清（回复5848086745/5848146593）**：工作台5-3确实仍为上述LYX e5b785c9原版，未产生比它更新的本机改图；96e819b7同目录与它相同。本机接手后先完成4-5和5-5，没有开始5-3绘制。因此这里交接的是工作台真实当前半成品，不把旧版声称为新稿。当前submission=4f0eff7bd72744c8ba770d9c7d4e625a、revision=19、execution_mode=captain；历史审查标识见handoff-state.json。队长自本交接起为5-3唯一修改者。
