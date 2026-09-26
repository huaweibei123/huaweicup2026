# P3 章节证据索引与修订约定

对应正文：[问题三 Markdown 初稿](../sections/a-q3.md)。本文件为合稿与复核记录，不直接作为参赛论文正文。

最新理论来源为 `3d22453deb0d2e3618f9d6cb41795ff164c6c84e`，另跟进 `a35d384653d175bf36a59f7d7bed26c19979d3cc` 的唯一机制候选冻结。正文包含 §6.4.4 离线分桶、§6.5.7 多释放包络、§6.5.8 共享服务反馈及 §6.6.7 事前验证规则，仍为24式、7处文字图占位。完整统一算法仍为311322b，主表仍为19bebf；没有将新结构、模型系数或冻结预算替换为官方成绩。

## 写作范围与衔接

用户已澄清原请求中的“P1”为笔误，本任务整理 P3 完整思路。按用户指定的 `paper/论文结构参考.pdf` 参考章节层次，使用问题分析、模型、算法、结果与局限的结构。参考 PDF 为 52 页的往届评审方案论文，只参考其组织方式；它的统计模型、数据、图、姓名和结论均不是本题成果。PDF SHA-256：`f302a6d59b7cea9bcfe3c12287a0d6fb76d1dc5d1a0394f88896121c3336fe12`。已读取目录、相关 P3 章节文字，并查看物理第 35、40 页图像；不声称逐页审读全 52 页。

本 session：`yuanzhifang30-sudo/s-3d9c78db26714786b88b987ca6f58e2b`。正文及本索引为本 session 单写；正式 TeX 由队长整合。已向队长发送[范围与固定版核对](https://github.com/huaweibei123/huaweicup2026/issues/51#issuecomment-5826374399)。本稿采用 P1/P2 已沟通的 $\phi$、$\kappa$、$\sigma$，但不把 P1 的 Task 完成门控搬入 P2/P3。

写作期间继续读到队长[2026-09-25T04:05Z 的目标更正与新单格通知](https://github.com/huaweibei123/huaweicup2026/issues/51#issuecomment-5826502623)，已实际读取 `a73d1e1e664ef95e6cdc8d9d0da2d95fba7aa718` 的 `OBJECTIVE_AUDIT.md`：Makespan 仍是首要质量量，CacheGain 是同计划相对效益核心比较；当前算法只按 M 接受，尚未将 G 作为接受条件。正文 §6.2.3、§6.7 已据此修订，未改变既有算法或实验预算。

另读取新发布 `e96a8551d6b3c92bbf00285376ce950f9246c0dc` 的前缀 Linux 机制报告及 `62c69b20ab887c76567dbab5fcce6eef30107b5c` 的静态构造说明，加入 §6.4.3、§6.6.3。该项是 044/k5 单格 38390→38024，0 P2、solver wall 未知；只按已发布报告引用，未独立核全部原件，不替换完整主表。完整算法最新可用版本仍为下表所列固定版本。

2026-09-25T04:32Z 后继续跟进到 `28e8c7ddfe2223b2261056f554259c43d5bba272`。新增的是对已保存044/k5结果的 Cache 事件和实际路径分析，0新官方调用，不是新统一算法。本稿在 §6.5.4–6.5.5、§6.6.4 加入固定读取集合的命中上界、取整共享服务研究界及启动竞争分解；主表保持原版本。

2026-09-25T04:41Z 队长[新增研究通知](https://github.com/huaweibei123/huaweicup2026/issues/51#issuecomment-5826864457)后，实际补读 `734914db51cecf094453c2b02e67fc5f5619b090` 的部分预加载设计、纯函数、测试代码及 `guard-audit.json`。正文 §6.5.6 加入单激活固定服务闭式、线性扫描和真实多激活守卫。此次只读推导与已发布守卫结果，没有运行测试、重建 Task 或产生新候选；队长报告的4项纯模型测试按来源归属，不计作本会话复现。当前19式、7处文字图占位，统一算法与主表保持原版本。

## 主算法与数据身份

| 项目 | 固定版本或内容 | 本稿采用方式 |
|---|---|---|
| 完整统一算法 | `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`，`src.q3.forest_solve.main` | §6.3 主方法；不是只有 `adaptive_solve` 的旧版 |
| 最终 500 格 feed | `19bebf35205d23fdd832781540f8879da52eeb62`，十份 `board-feed-sNN-revision2.json` | 全部 100 图 × 1–5 核，revision 2，仅补证据不改原成绩 |
| 官方 code 聚合身份 | `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0` | 逐格声明一致；本次写作未重新执行 E0 |
| 配置 SHA-256 | `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9` | L1/UB、带宽、500 周期跨核等待及只读 Cache 固定 |
| 完整结果与配对审计快照 | `cf4d77a018def540358c3b4667c2d2466390981a` 下的两份 `independent-audit.json` | 团队固定审计数据，不假称本会话重跑全部原件 |

完整 feed 目录为 `results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/`。各输入 Git 原字节 SHA、字节数、核对项与统计记录在[根会话复核结果](../drafts/p3-published-summary-audit.json)。复现命令为：

```powershell
python -B paper/tools/audit_p3_chapter.py
```

脚本只读十份固定 feed 和两份发布审计，不调用 solver、derive、Step、E0/E1/E2，也不下载或展开大 trace。需本地 Git 对象可读；Git 部分克隆若缺对象，获取所需对象的成本与重新评估不同。

本次自行重算并核对：500 格完整覆盖、相同算法 SHA/入口、最高 revision、状态、图/配置/官方身份绑定、计划与配对声明绑定、P3 平均周期、逐图命中率平均、平均额外搬运、求解墙钟统计、声明调用账 500 solver / 973 E0。元数据身份一致不等于重新 hash 每份原始计划和结果。

本次从固定团队审计引用：逐图 $B_i/M_i$ 的平均、同计划 P2/P3 的平均、汇总 hit/miss 字节命中率，以及负收益格的全量清单。原审计说明其核对原件与复用证据的范围；本稿没有重复核全部大体积原件。四个负例的 P3 周期已与本次 feed 对齐。

Luna medium 的第一份[feed 审阅](../drafts/p3-forest500-audit.json)保留独立读取结果及限制。其额外尝试的压缩 Git 对象批量映射未能可靠完成，已停止；不能据此判为源文件缺失或 500 格无效，也不能宣称这次已 hash 600 个 B/P2 原件。随后根会话使用上述限定小文件脚本完成可复现核对。未新增算法实验。

## 逐项来源与可用结论

| 正文部分 | 固定来源 | 可支持结论与限制 |
|---|---|---|
| §6.2 官方目标、输出与计时 | [官方目标核验](https://github.com/huaweibei123/huaweicup2026/blob/2da54f2bcfb85e033df900b03b4d181a698fd012/docs/a/OFFICIAL_OBJECTIVES.md)；冻结 `multicore_cut_evaluate_problem_3.py`、`config.txt` | Makespan 与求解墙钟分开；P3 Cache 字节口径；配置不能改 |
| §6.3 路由与接受策略 | [forest_solve](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/forest_solve.py)，同提交 witness/pipeline/calendar/expanded/adaptive 及 guarded 模块 | 新基准、固定结构候选、总在线 E0 ≤ 3、仅严格 M 改进接受 |
| §6.3.1 一般 DAG 日历 | [gap_dag.py](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/gap_dag.py)，同提交 `gap_calendar.py`/`GENERAL_GAP.md` | 凝聚链、固定就绪秩、至多两链联合归核、持久 AVL；复杂度不含输入展开与官方评价 |
| §6.3.2 连续划分 | [shared_pipeline.py](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/shared_pipeline.py) | 精确解固定串行阶段最小最大段和；不等于原题最优 |
| §6.3.3 森林交换证明 | [FOREST_FRONTIER_ORDER.md](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/docs/a/q3/FOREST_FRONTIER_ORDER.md)，同提交 `forest_memory_order.py` | 固定树、子树不交错、内部输出标量峰值；不覆盖真实 Cache/双池/跨流水线 |
| §6.3.4 条件下界 | [pipe_bound.py](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/pipe_bound.py) | 单节点子图、整数 M/V、已证明原依赖与 FIFO；不支持 COPY 收缩歧义；不证明合法执行 |
| §6.4、§6.6.3 容量流水 | [固定单例报告](https://github.com/huaweibei123/huaweicup2026/blob/7edacdd97a7be36a402af20bc8bfa8a7454dbbe0/results/a/q3-yuanzhifang/pipeline-capacity-20260925/REPORT.md)；源码 `2df4a5fa70d7a59492a7477e9ecd706501e64ad6` | 044/k4 实测 40927→37581、extra DDR 135168→121088 B；非全家族或统一500格结论 |
| §6.4.3 完整 Task 前缀 | [固定静态说明](https://github.com/huaweibei123/huaweicup2026/blob/62c69b20ab887c76567dbab5fcce6eef30107b5c/results/a/q3-nikolastarx/pipeline-prefix-static-20260925/README.md)；[新官方单格报告](https://github.com/huaweibei123/huaweicup2026/blob/e96a8551d6b3c92bbf00285376ce950f9246c0dc/results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/REPORT.md) | 044/k5 的结构、容量守卫和38024周期为发布证据；本稿读取报告，不代签独立原件验证或完整算法 |
| §6.4.4 离线部分分桶 | [README与构造](https://github.com/huaweibei123/huaweicup2026/tree/3d22453deb0d2e3618f9d6cb41795ff164c6c84e/results/a/q3-nikolastarx/partial-bucket-compile-20260925) | 7个冷读断点受限族的保存结构检查；不是全部合法h，不含Step3内存边，不是新官方方案验收。非规范键缺陷已修复，任意证书身份认证仍由入口负责 |
| §6.5.1 完整作业必要界 | [WHOLE_JOB_BOUND.md](https://github.com/huaweibei123/huaweicup2026/blob/09191c18bebc8b93e7751058b7c1b0f67c7d08fe/docs/a/q3-yuanzhifang/WHOLE_JOB_BOUND.md) | 067/k5 完整作业家族下界 12446880；不能超越已存 12237901；不证明全局最优 |
| §6.5.2 首波阶梯 | 源码 `68fbe66e97f78161bfb6f4f9e83cd2f0977ce7a9`；[当前保留的冷构造与停止记录](https://github.com/huaweibei123/huaweicup2026/blob/6152817144576bec9918a2ae59ef54e42352b21e/results/a/q3-yuanzhifang/wave-stair-20260925/REPORT.md) | 真实构造成功 1 次，随后父进程导入失败，0 E0；无官方分数 |
| §6.5.3 响应压缩 | `1b70dd6076430230c531b10e3e403e88474179cc` 的 `tail_response_model.py`；[真实图静态审阅](https://github.com/huaweibei123/huaweicup2026/blob/6152817144576bec9918a2ae59ef54e42352b21e/results/a/q3-yuanzhifang/tail-response-static-followup-20260925/REPORT.md) | 8804 操作与完整计算/FIFO DAG 一致；零 COPY/零额外 lag 模型，不是缓存模拟 |
| §6.5.3 阈值 DP | [TAIL_CUT_DP.md](https://github.com/huaweibei123/huaweicup2026/blob/2ec2ab12e1becdd600198eeb85deefc464678e9e/docs/a/q3-yuanzhifang/TAIL_CUT_DP.md) | 固定区间四系数表内精确；小表合成穷举对照；真实全区间表未完成 |
| §6.6.2 完整算法均值与墙钟 | [统一算法审计](https://github.com/huaweibei123/huaweicup2026/blob/cf4d77a018def540358c3b4667c2d2466390981a/results/a/q3-nikolastarx/forest-full500-feedback-20260925/independent-audit.json) | 500 格、973 在线 E0；本次独立重算 feed 墙钟/计数一致；共享主机单次分布 |
| §6.6.2 版本差异 | 同一固定审计的 `forest_vs_c2_counts`，旧结果来源 `c2d628ba0fe8dce4630e5f9c0a5c8fb810fcd41a` | 引用已发布500格版本差异；本次核分类计数合计与单位，不重新读取旧版500份原件；不是森林模块单因素消融 |
| §6.6.2 Cache 配对主表 | [配对审计](https://github.com/huaweibei123/huaweicup2026/blob/cf4d77a018def540358c3b4667c2d2466390981a/results/a/q3-nikolastarx/forest-cachepair-delta-20260925/independent-audit.json) | 476 同字节 P2 复用 + 24 新 P2，完整 500 对；不声称本批重新跑500个P2 |
| §6.5.4、§6.6.4 命中饱和 | [固定 Cache 事件审计](https://github.com/huaweibei123/huaweicup2026/blob/28e8c7ddfe2223b2261056f554259c43d5bba272/results/a/q3-nikolastarx/prefix-cache-critical-audit-20260925/REPORT.md)及 `summary.json` | 两份044/k5原结果在本次重新核 SHA、键大小/次数和事件：171首次miss、11重复hit、0淘汰；上界只针对固定读取集合 |
| §6.5.5、§6.6.4 共享前缀与路径 | [固定实际路径审计](https://github.com/huaweibei123/huaweicup2026/blob/28e8c7ddfe2223b2261056f554259c43d5bba272/results/a/q3-nikolastarx/prefix-realized-path-20260925/README.md)及 `audit.json`/`test_math.py` | 1678操作开始时间重现为团队已发布结论；本次复核分项算术，不重新构建准备图。36592仅有理数共享取整模型界，不登记为官方浮点剪枝证书 |
| §6.5.6 部分预加载 | [DESIGN.md](https://github.com/huaweibei123/huaweicup2026/blob/734914db51cecf094453c2b02e67fc5f5619b090/results/a/q3-nikolastarx/partial-preload-design-20260925/DESIGN.md)，同提交 `fixed_service.py`/`test_fixed_service.py`/`guard-audit.json` | 单激活、固定服务和串行计算链中精确；逐读递推测试为队长报告，本次仅审阅代码。真实核2/3/4不满足单激活条件，核1只通过此单项；没有新官方方案 |
| §6.5.7 多释放函数 | [模型、测试与保存签名](https://github.com/huaweibei123/huaweicup2026/tree/3d22453deb0d2e3618f9d6cb41795ff164c6c84e/results/a/q3-nikolastarx/release-envelope-model-20260925) | 固定服务下的完整释放函数；在相同独立非负变量域内的模型支配，不是官方剪枝；本次独立重算8个已保存签名和支配表 |
| §6.5.8 共享供给反馈 | [R7正文及清单目录](https://github.com/huaweibei123/huaweicup2026/tree/3d22453deb0d2e3618f9d6cb41795ff164c6c84e/AI%20chats/20260924-Pro-P3-%E5%BD%92%E7%BA%A6%E6%A3%AE%E6%9E%97%E5%88%87%E5%88%86) | 阅读本轮问答正文并核回答字节哈希；反例及两流推导经代数/手算审阅，九项测试仅Pro自述，附件未取得，不能称本机复现 |
| §6.6.5 非单调反例 | [CACHE_NONMONOTONE_021.md](https://github.com/huaweibei123/huaweicup2026/blob/f26704ed8748f0a575b55f1a02b83d7335a1083f/docs/a/q3-yuanzhifang/CACHE_NONMONOTONE_021.md)，同提交 `audit_021.py`/`audit.json` | 同 plan 2140720→2140863、同 COPY/字节；已核字节原件及逐操作观察；尚非完整退化因果链 |
| §6.4.4、§6.6.7 唯一机制候选 | [冻结目录](https://github.com/huaweibei123/huaweicup2026/tree/a35d384653d175bf36a59f7d7bed26c19979d3cc/results/a/q3-nikolastarx/partial-preload-one-20260925)，执行源码固定 `817e9e399f5efaf66cea6ddc495fe444950e43f2` | 结构规则得到core2/h15；事前最多1prepare/1P3/2条件P2，未读取到本候选的正式运行原件，不代表正在运行或已经通过 |

## 公式审阅与图件计划

Sol medium 只读复核了式（6-6）至（6-16）及相关小源文件，未运行真实图或 E0。两项意见已采纳：连续流水公式就地明确不同阶段使用不同核、同序通过且每阶段单作业串行；森林最优性在结论句中限定固定树/归核和不交错内部峰值模型。峰值符号改为 $h_i$，避免与计算时间 $p_i$ 混淆。此为团队内部复核，不标为独立盲审。

文档检查：正文16个公式编号连续、显示公式分隔符成对、六处图占位均明确标注，正文与索引的相对链接目标存在；小文件聚合脚本执行成功，正文数表和墙钟与固定输出一致。新增文件已检查个人绝对路径及凭据形态。当前平台为 Windows，没有 `dot_clean`；对本次写入的具体目录只读扫描，未发现 `._*`、`.DS_Store` 或 `__MACOSX`。未生成正式图片、PDF 或 TeX 排版，因此未声称这些产物通过视觉/版式验收。

2026-09-25T04:20Z 后续修订：再次核对 `311322b` 的 adaptive/guarded/gap/calendar/pipeline/witness/forest 实际调用关系，补入按顺序的结构路由表、一般 DAG 链与汇聚联合放置和构造复杂度边界。明确“严格接受”只相对于本次已成功评价的基准，基础路由没有跨历史算法的不退化保证；初始评价或程序错误不属于可静默回退的候选拒绝。同时补出首次装入闭式的递推与归纳理由，明确装入不能提前与上游重叠的抽象前提。均为已有源码/数学说明的完善，无新构造或官方调用。

本次完整 Mailbox 抓取 6 话题/667 评论、读取整个索引；继续仅按 P3 与公共协议清单补读，不宣称导入同账号所有专项历史。队长算法 HEAD 核对仍为 `e96a8551d6b3c92bbf00285376ce950f9246c0dc`，完整统一版本未变；保留本稿已有主表。

实际读取 [P1 固定 ad168d9e 的符号与跨问节](https://github.com/huaweibei123/huaweicup2026/blob/ad168d9e8dfe9e36a75503788a9f4852a1946729/paper/sections/P1-%E9%97%AE%E9%A2%98%E4%B8%80%E8%AE%BA%E6%96%87%E5%88%9D%E7%A8%BF.md)及 [P2 固定 87cd5d2d 的对应段落](https://github.com/huaweibei123/huaweicup2026/blob/87cd5d2d14db8de9ad0d7ab44f5e3a36c4ae6537/paper/sections/a-q2.md)后，发现各初稿尚未完全同名。P3 已在本人章节内消除与 P1 的 $\mathcal T$ 冲突，并与两问共有记号对齐；未修改他人文稿。合稿映射为：

| 对象 | P1 固定初稿 | P2 固定初稿 | 本 P3 修订稿 |
|---|---|---|---|
| 可提交方案 | $P=(\phi,\kappa,\sigma)$ | $\Pi=(\mathcal S,c,\sigma)$ | $P=(\phi,\kappa,\sigma)$ |
| 分区含义 | $\phi$ 的非空原像组成 Task 集合 | $\mathcal S$ 为子图分区 | $\phi$ 的非空原像对应 $\mathcal S$；每核合并 Task |
| 张量集合 | 与 Task 集合 $\mathcal T$ 分开 | $T$ | $T$，不再用 $\mathcal T$ 表张量 |
| Pipe 与有效周期 | $p(v),d_v$ | $p(v),d_v$ | $p(v),d_v$ |
| 固定 A 场景单核分母 | 固定官方基线 | $A_i$ | $A_i$；JSON 源字段 `B_over_M` 是同一分母的旧命名 |
| 求解、外部复评墙钟 | $T_{\mathrm{solve}},T_{\mathrm{E0}}$ | $\tau_{\mathrm{solve}},\tau_{\mathrm{E0}}$ | $T_{\mathrm{solve}},T_{\mathrm{E0}}$ |

P1 正文核编号从 1 起，P3 对齐接口从 0 起；只是编号映射，合稿时需统一，不应改变各自等待语义。P2 的整体方案符号和时间符号可由队长最后统一，不为了形式一致改写它的实质模型。主表数据和源 JSON 字段未因记号调整改变。

新增小范围原件复核：`python -B paper/tools/audit_p3_prefix_cache.py`，输出[前缀 Cache 核验](../drafts/p3-prefix-cache-audit.json)。只读取固定提交中的两份 P3 压缩结果（48,921 B 和 50,375 B）、一份计划、两个审计小文件；结果/计划 SHA 与已发布绑定一致。独立核实了完整键—大小—次数多重集相等、首次/重复读取、命中字节上界取等、零淘汰和搬运字段一致。对路径部分只核来源绑定、38024分项和、8244差值及四个前缀完成下限算术；未重新加载完整准备图，也未调用Task/Step/E0。七处图占位与18个公式对应最新稿，旧“六图/16式”是上一版检查记录。

bf583f1版部分预加载修订增加式（6-19），截至该版共19式、7处文字图占位；上述18式/7图及16式/6图保留为各版的实际检查记录。森林节点孩子数改记为 $a_v$，消除与有效计算时长 $d_v$ 的同名冲突。

| 图号 | 目前状态 | 最终绘制需要 |
|---|---|---|
| 6-1 技术路线 | 文字占位 | 冻结入口及模块归属；可编辑结构图 |
| 6-2 容量与切点 | 文字占位 | 044/k4 各候选固定元数据与真实峰值；估计/实测分开 |
| 6-3 核数与质量 | 文字占位 | 最终单版本完整100×5与基线绑定 |
| 6-4 Cache 分布 | 文字占位 | 同计划P2/P3；逐格 hit/miss 字节；保留负例 |
| 6-5 044 启动竞争 | 文字占位 | 实际时间轴、独占乐观值、条件共享模型界分别标识；不画成三个实测算法 |
| 6-6 021 事件差异 | 文字占位 | 对齐原 timeline；未有关键路径证明时不能画成因果结论 |
| 6-7 质量—墙钟 | 文字占位 | 固定硬件/worker 的端到端计时；重复试验与跨用例分布分开 |

按用户要求，当前不生成看似实测的示意数据。最终科研图使用项目 `scientific-figures`/Matplotlib 工作流，保留绘图输入、脚本和可编辑来源，待算法冻结后绘制与视觉验收。

## R7 与多释放研究的本次复核

实际读取3d22453d的离线分桶README/AUDIT/compile.py/test_compile.py、完整结构表，以及多释放README/model.py/test_model.py/task_profile.py/audit_saved_family.py和保存签名字段。没有运行这些候选编译器、模型选择器或测试。发布的6项编译测试、4项/20次模型递推检查按队长结果归属，原数据依赖、内存峰值和上游COPY_OUT先后也未在本次重建完整Task图验证。

8c4907b4版首次新增 `python -B paper/tools/audit_p3_release_envelopes.py`，首次输出[只读包络核验](../drafts/p3-release-envelope-audit.json)。共读取12个固定Git文件：重算8份已保存传输记录对应的系数和全部模型支配关系，得到h=2/15/17；核对构造/模型源码、结构表、原计划与容量证书的已发布散列，检查示例仍为两字段且其他核提交列表不变。没有加载完整Task压缩快照，没有重新验证预估峰值或依赖无环，也没有产生新候选。模型周期绝不登记为官方Makespan。

R7本轮问答和manifest已读取，回答 `bb41cb93-c330-4de4-bda1-78825d4aa74f` 的保存正文为19,805 B，SHA-256为 `1b5519801e99614842802c72cdeed4a3541ff5a4144952b756ab261f6cff67ff`，本次按Git字节重新核实。Pro自述完整/局部读文件范围保留在正文开头；归档只核该轮可见回答，不代表重新验证全部七轮历史。清单明确数学内核压缩包和证书JSON未取得可验证原件，本会话未下载或执行这些附件；“九项检查通过”只能作作者报告，不当作本机测试。新章节主要采用可从文字逐步复核的推导、反例及保存代码中已明确的适用条件。

## 后续更新规则

本轮进一步实际读取a35d3846的冻结README、build.py、manifest/transport、prepare/probe入口及其判定分支。只读核验脚本扩展为v2，原12文件复核之外增加6个冻结文件，共18个固定Git文件；核实4个候选产物散列、名义工作量选择算术、节点归核与前缀清单。新计划SHA-256为 `0a75e3613ad5f69e293e45e6c1cfc1545b3b1036245ebc7bf0af75b3321df0fd`，manifest为 `b36ef3ae7b974b139d9f7d5969a27df7868ebfba9d69818d26055bc83bd310a4`；运输声明的执行源码为817e9e39。本会话没有导入或启动这些执行入口，不把已冻结的启动方式视作进程存活证据。

§6.6.7明确准备与评分的事前停止条件，以及严格M改善后才补两组P2的条件采样范围；尚无固定执行结果时不填新M、G、命中率或solver wall。当前有界脚本只重核保存字节/元数据与结构选择算术，未生成新候选、Task或任何官方评分。

b0b3414版续读核对时，队长算法分支为 `734914db51cecf094453c2b02e67fc5f5619b090`，主库 `c1c2c7947de6bd3459f87f6b3cbbb2ba52ce3084` 的新增内容为成绩台展示与文档，不是新算法或实验。对照冻结 `schedule_step3._op_duration` 与 P3 的 `issue`/`advance_pool_work`/`reschedule_pool`，正文补清“每笔 COPY 先取整为服务量、共享服务后再按事件退休”的两个层次。另实际读取官方 P2 结果构造与[成绩台配对边界](https://github.com/huaweibei123/huaweicup2026/blob/c1c2c7947de6bd3459f87f6b3cbbb2ba52ce3084/docs/benchmarks/BENCHMARK_BOARD.md)，说明结果 JSON 不自带计划散列，原件/收据互校不等于本会话重新运行。

b0b3414版新增的版本比较表直接来自上述固定团队审计，`audit_p3_chapter.py` 将其原始计数与差值保存到 `published_version_comparison`，仅核各行总计500，不冒称重新计算旧版逐格差值。3格额外搬运上升和9格命中字节下降保留，命中字节不称作命中率，额外搬运与spill减少量不相加。此轮无新求解、Task/Step或官方评分。

1. 先取得队长发布的固定算法 SHA、入口与完整结果版本，再检查其相对于本稿的模块和语义差异。新研究分支、少量成功格或成绩台逐格最佳，不能自动替换完整主表。
2. 结构改动同步修改假设、公式、伪代码和复杂度；对旧证明审查是否仍适用，不只更新结果数字。
3. 指标至少保留 Makespan、总额外搬运、同计划 CacheGain、字节命中率与完整求解墙钟。比较版本时固定图/核数/配置/官方源码身份，缓存收益固定计划身份。
4. 容量或单尾扩展只有完成官方验证并进入冻结统一入口后，才迁入主算法描述；局部实测、静态分析、理论必要界始终单独标明。
5. 发布修订使用新提交和原任务 Issue 通知队长，等待对方实际读回或合稿回执；发送成功不当作已采纳。早期持续研发目标已被用户后续“完成本次咨询/论文后暂停、保留额度”收紧，本次交付不启动新的实验或无限研发。

## 第四综合Pro后的修订

三问本轮完整问答已对照，第四综合回答已完整取得，见[最终理论札记](a-theory-coherence-final.md)及[公开归档](../../AI%20chats/20260925-Pro-全题数学框架-coherence/README.md)。新增§6.5.9的共同投影、窗口原子组合与残余跨核等待推导，§6.6.8的固定500格理论包络、近最优计数与迭代保证；共26个编号公式、8处文字图占位。图6-8待最终冻结后绘制真实L/U区间，不使用虚构性能数据。

§6.6.7已经从事前预算更新为完成状态：保存的控制P2=P3=38024、候选P2=P3=37060，降964周期，两个CacheGain均1。此前“尚未执行”是旧时点，不再当作当前状态。MTE2/MTE3同时变化、求解全墙钟未知，机制格不替换主500结果。

本轮独立验证脚本verify_pro_coherence.py检查227输入载荷、100原图充分条件、634506原计算/740641边、1500组保存B/U/L及组合公式的小例算术；只读/静态检查，无新候选、Task、Step、评分或响应模拟。P1全部窗口与屏障仍归属负责人/Pro报告，未冒充本机重跑。新组合全500证书未生成，所有主均值保持既有冻结身份。

第四回答1问1答与独立消息清单逐字相同，正文原件已归档；输出ZIP及附件原字节下载失败，明确列为未取得。作者报告的大小/SHA不当作本机校验，也不将本札记代替附件原文。该缺件不改变已保存正文、已有原图和静态算术的可追溯性；如以后收到原件，追加补件记录。
