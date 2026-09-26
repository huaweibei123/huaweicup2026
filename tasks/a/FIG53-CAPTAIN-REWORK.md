# 数模任务卡：问题二图 5-3 修订

负责人：@NikolaStarx，验收台会话 `nikolastarx/s-01a0dc7a4aad77d1aa6e5d10c83d7ac9`

分支：`codex/fig53-captain-rework-20260927`

沟通 Issue：[图 5-3 交接](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5848204054)

1. **任务目标**：从 Fang 实际交接的半成品改出科学口径正确、160 mm 纸面可读的多方法平均加速比图，逐项关闭 F53-R01～R05。
2. **输入文件**：固定提交 `6ac4ec28582212c9fab967ceab5e09e796dbadba` 中的 `deliverables/a/fig53-captain-handoff-20260927/fig5-3-captain-rework-e5b785c.zip`；其中三份成员结果表和一份 `c665` 汇总的来源、单位及 SHA-256 见同目录清单。100 张官方计算图为相同用例集合，`F1` 仅五核心完整。
3. **输出要求**：`src/analysis/fig53_rework.py`、`figures/a/fig53-captain-rework-20260927/` 内的 PDF/SVG/PNG、逐图长表、方法汇总表、图注、来源和字节哈希清单，命令 `uv run --locked python src/analysis/fig53_rework.py --figure 5-3`。
4. **限制条件**：固定既有结果，不运行求解器、E0/E1/E2，不修改冻结 v8；所有方法的一核心点直接画真实观测均值，理想线另作参照；F1 不补造其他核心数结果。使用仓库锁定依赖及已安装中文字体，设计宽度 160 mm。
5. **验收标准**：三完整方法各 500 唯一格，F1 五核心 100 格；官方情况 A 单核共同分母；逐图比值再算术平均；指定参考均值相符；规范 CSV、单图重现、输出哈希与实际图面检查通过；论文监督会话和用户最终验收另行记录。
6. **截止时间**：本轮交接后尽快交付，具体时间由队长与论文监督会话按合稿进度确认（亚洲台北时间）。

## 交付记录

实际命令：`uv sync --locked`；`uv run --locked python src/analysis/fig53_rework.py --figure 5-3`。

代码提交与输入版本：输入固定提交 `6ac4ec28582212c9fab967ceab5e09e796dbadba`；图与脚本修订提交 `7b6545226ce5b9c7e00d669d60fc2a9bd97d9013`（初版 `7d1bf1e4718596f428696ed4f4b12015003f59ca` 保留历史）；Draft PR [#231](https://github.com/huaweibei123/huaweicup2026/pull/231)。

结果与图表：`figures/a/fig53-captain-rework-20260927/`。

结论及限制：参见本目录 `README.md` 与 `self-check.md`；只复核固定汇总表，不宣称新官方实验或最终论文验收。

已按修订提交核远端 Git 的图、表、图注、清单、脚本共 11 件文件，逐项 SHA-256 相符；回读收据见 `figures/a/fig53-captain-rework-20260927/publication-readback.md`。一核心三个点均为真实观测值。

未验证项：论文监督会话的选版与实际 LaTeX 页面、独立科学复核、用户最终确认。

PR：[#231](https://github.com/huaweibei123/huaweicup2026/pull/231)；验收台登记另见 [#225](https://github.com/huaweibei123/huaweicup2026/pull/225)。
