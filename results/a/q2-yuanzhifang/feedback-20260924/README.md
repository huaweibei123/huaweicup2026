# P2 反馈迭代交付索引

生产session：`yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24`；[PR108](https://github.com/huaweibei123/huaweicup2026/pull/108)；[队长/成绩台交付](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5816307261)。源码与结果均在独立 `codex/q2-feedback-yuanzhifang-20260924` 分支；不接管旧Q2、P1/P3、网站或Atlas写区。

| 批次 | 固定原件提交 | 成功/其他 | 实际调用 | 主要结论 |
|---|---|---|---|---|
| round1 | `30f8ad352c3ff15a7c1c29fd182a9e32776fdc35` | 18成功/2预期unsupported | 20solver/18E0 | 直接计算窗口不能替代既有word/共享结构 |
| round2 | `044deba0e8d4f26514a266d9e68a9477822ba318` | 5成功 | 5solver/5E0 | 044 fill=66901；其余4图退化 |
| round3 | 本交付提交，算法 `8910f45`、spec `97a6975` | 3成功 | 3solver/3E0 | 002/062/063均胜旧连续；002仍输队长72056；标量最优不等于调度最优 |

两份 `round*-spec.json` 均事前冻结；每个batch有完整ledger、spec、plan/result/trace/log/run、标准 `board-feed-*.json`、workspace预检和summary。两个 `round*-git-preflight.json` 保存固定Git原件校验回执。较差结果与不支持行都在feed，不用事后赢家虚构在线组合算法。

算法解释、六字段范围与阅读来源见 `docs/a/q2/feedback/METHOD.md`；科学反馈见 `ROUND1.md` / `ROUND2.md`。`measurement-008-dependency-audit.json` 给出008的V→M必要依赖与3108cycles气泡；`peer-044-comparison.json` 独立读取P3固定原件比较映射/分核/字节/收尾时序，未新增评价。`structure-scan.json` 是100图事前结构扫描，不是100图E0验收。

`local-board-readback.json` 实际逐ID读回本机25/25、23 eligible、2 unsupported，且当时P2/044/4核选中66901；核对了身份、原件引用、状态及Makespan。本机网站维护session是 `s-c909b5a9a43b4bc78807afcf27341a38`，P1统计fork `s-e777d827b5af4adfafd148ff3a4fae8b` 不是网站写者。中央接收、主线合并、全量同步、独立E0复跑和科学终验均不由该本机回执代签。

R1～R3均已结束，至此账本累计28solver/26E0、2预期unsupported。用户进一步授权持续朝更好官方质量、端到端速度和理论界研究；目标仍未完成。每个新批独立固定实现、输入与预算，旧预算不自动重开。持续目标、图片数值和全量口径见 `docs/a/q2/feedback/CONTINUOUS_GOAL.md`；`goal-baseline/` 独立复算已有全500格并核100份单核原件，新增评分0。时间与资源边界见 `MEASUREMENT.md`。

R3的 `measurement-audit.json` 核6份gzip、13份冻结源码、trace全部区间与18个feed附件；科学限制和原始负结果见 `docs/a/q2/feedback/ROUND3.md`。固定Git预检与中央实际接收另记，不能由workspace预检代签。062/063优于旧连续并不证明优于当前中央最好。

第二轮044=66901已与队长新pipe_ready持平，中央维护者回报R2新增严格改进0；上方本机旧回执仅保留当时时点，不再作为“超越队长”的依据。P3同机会话的active2与分段流水是独立作者结果，引用时须核其P2固定原件并注明来源。

本目录Windows原件由局部 `.gitattributes` 保全字节。依赖、代码、参数、环境、失败、未知peak RSS及开发成本均在运行收据；solver端到端墙钟与独立E0墙钟分列。无Actions或付费云计算作业。
