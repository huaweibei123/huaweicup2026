# 已验收 Python 原稿交接：图 5-5、5-6、6-6、6-7

负责人：@yuanzhifang30-sudo；沟通：[Issue 217](https://github.com/huaweibei123/huaweicup2026/issues/217)。
session=yuanzhifang30-sudo/s-f42fb47d93984f22a151b0a09f678c84。

1. **任务目标**：按用户 2026-09-27 授权，将工作台已通过的 Python/MATLAB 原稿直接交队长复审；其他图先美化并等待用户确认。
2. **输入文件**：各图目录保存当前验收提交的全部原件；同名 acceptance.json 保存 submission、审查、来源及逐文件 SHA-256。工作台做过的修复以其验收版本为准，本次交接不再绘制或修改。
3. **输出要求**：原图、矢量图、绘图代码、CSV、图注及审查证据一并发布。各图 README/self-check/source-verification 记录复现命令与来源；本次未执行上传代码或新实验。
4. **限制条件**：原件逐字节保存，未修改精度、数据或科学结论。Makespan 是方案质量；solver wall 是完整求解程序墙钟，两者分别报告。5～10 分钟是题面效率建议，不是 Makespan 或新增淘汰线；本次不扩充实验预算。代码/工具可复现说明由原验收记录提供，不等于本次已重新运行。
5. **验收标准**：以下逐项转交工作台真实审查原文。交接方只重新核对当前 submission/review 绑定及全部文件 SHA，并查看原稿；不将转交等同于重新独立完成全量科学审计。用户全套总验收、队长审核和论文入稿均仍独立。
6. **截止时间**：2026-09-27（Asia/Shanghai）本次交接；持续检查后续已通过图件。

## 交付验证与边界

64 个工作台原文件哈希全部与 approved review 相等，4 份完整验收收据一同保存；package-manifest.json 覆盖全部交付文件（清单自身除外）。原件换行符保持，使用本目录 .gitattributes 禁止 Git 转换。

未运行 solver/E0/E1/E2 或队友上传脚本；未新增实验，未更改验收台状态。6-6 是旧 witness 的同计划机制案例，不能冒充最新 forest 的500格性能。5-5 与6-7的资源、分位数、在线评估及独立外部复评边界不同，按各自图注保留。

本 session 已读队长语言标准 2026-09-27.1（1be28c77b911ef00781e0c23413b68b62823a566）。本包按用户要求原件转交，不替队长断言原稿已通过新一轮语言验收；后续非数据流程图按短标签与完整图注/正文要求整理。图4-1美化候选待此项复核和用户确认；新版4-4/4-5待工作台独立验收；图5-3是队长7d1bf1e4原图，已收到工作台验收回报，本包不重复发送。

## fig-5-5

版本：96e819b7 / workbench local-source-v1 / c665 full500。

submission：`3b81a0c008bb47738b915ef97fb13136`；review：`f6eb33105e1147a39038af824196b52c`。

原来源：https://github.com/huaweibei123/huaweicup2026/tree/96e819b7049c15761b60e271d621bd6505a26522/figures/a/p123-fig-5-5-lyx-20260926

以下为工作台验收证据原文：

- **criterion-1**（passed=True）：实取1c00079a summary与3fc333c3十份原feed；500唯一case/core、6指标（M、solver wall、外部E0 wall、总/额外DDR、spill）、图与配置SHA逐格相等，均绑定c665算法/attempt/run。另解压001/k1、尾部014/k5原始官方结果并核未压缩SHA、M及核数，读取两端进程status/exit/wall。读取ff47 runner与monitor源码，perf_counter在Popen前至cleanup/reap后，在线E2位于solver，独立E0另进程；没有用batch/500。证据source-verification.json及sources.json。

- **criterion-2**（passed=True）：500格统一macOS-27.0-arm64、Python3.12.13、实际worker1；CPU/线程未记录如实注明，未拼Windows/另一批M5数据。solver wall含online native E2；独立E0逐格另存；1131 native、0fallback、500external calls。预编译/校准成本未测明示。没有稳定跨平台速度结论。

- **criterion-3**（passed=True）：自编prepare_review_tables从实际固定原件重算每核100条的median、线性P95、max；全量1.5584785205/18.8500354643/40.1865057920秒，区别原报告nearest-rank18.8411202080。5条ECDF使用全部500原始墙钟，无删尾、无冷启动命名、无Pareto/重复测量误差声明。

- **visual**（passed=True）：实际查看最终624×797论文插入宽预览，第二面板轴标题与统计表已分开；8–11pt原图165.1mm宽，五色配合点形/线型，坐标、全部尾部、表格及底注可读无裁切。自编plot_local生成SVG/PNG/PDF同版，final audit SHA161f09567781e9ecb324e570e23e6c414780f81c8ea656d2de9342e08121c57d。

## fig-5-6

版本：c49424c1 / workbench local-format-v1。

submission：`4306f8284d394e87947658e5ebf2d27a`；review：`b8485eb3d8aa4339b93db919092375d0`。

原来源：https://github.com/huaweibei123/huaweicup2026/commit/c49424c14956ba61073e30b938401b80c3dd8362

以下为工作台验收证据原文：

- **criterion-1**（passed=True）：实取c49424c1图件13个Git blob，原audit12项SHA全相等；当前发布的两必要输入也再次读取，分别fe25f7b7证书/083c3f5b summary，与既有1c00079a原件完全相同。独立按case/core及graph SHA核500格、accepted upper、支持域和多生产者守卫，500格0<L<=U，未裁剪负gap。复用既有源证书/code5862e1a2及理论OPTIMALITY_BOUNDS检查，未重跑生成器。

- **criterion-2**（passed=True）：逐条500个ECDF点与500个真实U/L-1排序相等，各核100个有效样本且末端1；81/62/32/33/23个<=5%由整数20*(U-L)<=L复算，无缺测填零。工作台仅为机检合并重复横坐标为右连续累积值，原CSV和原曲线字节保留，归一化表由自编normalize_tables.py生成。

- **criterion-3**（passed=True）：实际阅读固定全局界理论：对所有分区/分核/每核次序的计算工作、不可分割、保留依赖关键路径/窗口必要界取max；无固定FIFO界，不把DDR理想时间混入执行器证书。100图单生产者适用域真实，domain规范化同时保留applicability原文字；L<U不证明可实现改善或非最优，caption/README保留compute-only及未决边界。

- **visual**（passed=True）：实际查看作者原PNG全图及605×340的160mm插入宽预览，五条曲线、5%虚线、n=100图例、坐标和全部长尾清楚无裁切；原SVG/PNG/PDF和源码哈希未改。无新增实验/未执行队友脚本。仅本次规范补全audit角色/表名、适用域及等值ECDF；最终audit6f5c094732b6a44e2b20f63891d73d8bdbffdf517f506f4f3b54e98b877a57d6。

## fig-6-6

版本：68a81247 / workbench local-layout-v1。

submission：`9a8de80b872f461c82cb06a89fbb5add`；review：`95e1c655dfbf4b1d92549fc0a147192a`。

原来源：https://github.com/huaweibei123/huaweicup2026/tree/68a812479ae7326f662794594aacdb5f0fae4628/figures/a/jia-fig6-6-20260926

以下为工作台验收证据原文：

- **criterion-1**（passed=True）：实际取得f26704ed审计、19bebf35 P2 gzip、130dfe4c P3 gzip和plan、27409658配对summary；SHA逐件核验。配对summary两结果SHA与实际字节一致且绑定13362774计划；两raw的scene/cores/bandwidth/capacity/cross-core-delay/任务依赖及搬运五字段一致。完整面板同12行，局部核3/核1均同绝对窗口4900–7000与443050–443250，未平移。详prepare_review_tables.py及source-verification.json。

- **criterion-2**（passed=True）：独立读取两原始per_core_timeline，将8881操作按(core,task,op)逐条与作者CSV核对，17762事件的起止/历时、类型、Pipe、Cache字段、三类差值全部一致；每Pipe顺序相同但合并列表不宣称相同。复算变化7485/7808/2392和三个关键操作4905/6255/6089；生成标准表的全部端点均来自这些已核CSV。三原CSV哈希不变。

- **criterion-3**（passed=True）：总端点实际2140720与2140863，+143与CacheGain0.9999332保留；原搬运五字段相等，Cache命中率按字节独立复算。图和caption明确旧witness同计划单格机制案例，仅事件观察，不将一个COPY_IN视作全部退化原因，不外推500格或真机。无新solver/E0/E1/E2。

- **visual**（passed=True）：实际检查修订PNG的624×1008插入宽预览，图例移出数据区；完整12行清楚，局部四Pipe对照上灰P2/下橙P3，关键命中绿色并有操作ID箭头，时间轴与窗口范围一致，文本无重叠。新自编plot.py和机检适配器可复现；作者源码另留，未执行上传脚本。

## fig-6-7

版本：03f445ac / workbench local-format-v1 / forest revision2 full500。

submission：`4eafc6800a884d23871da2e09d99a80a`；review：`754017cc38a045ce90ef0c9cd703c7d7`。

原来源：https://github.com/huaweibei123/huaweicup2026/tree/03f445acf647a5cb90dffb83350f004b192ce395/figures/a/p123-fig-6-7-lyx-20260926

以下为工作台验收证据原文：

- **criterion-1**（passed=True）：实取03f445ac图件与published merged input，并逐格核19bebf十份原feed：500唯一case/core的M、extraDDR、wall、attempt/run/算法/图/配置/plan身份全相等。058/k5及最大wall014/k1原run/trace/压缩官方结果实际取字节核SHA，exit0、M、wall、身份一致。读取311322b runner run_child和forest_solve：perf_counter包Popen至communicate、进程清理与日志落盘；evaluate在solver进程内部。父进程预检另计batch；没有独立外部最终复评，外部字段null/CSV空值保留而非0。

- **criterion-2**（passed=True）：500格统一Apple M5 Pro、48GiB、macOS27 arm64/Python3.12.13；每分片worker1/global_max_workers4在源数据、CSV、图面和图注明确。线程数/峰值RSS未记录如实保留。每格单次观测，无独占/稳定重复/严格冷启动声明。逐核100条线性P95/median/max共15项由原始墙钟重算一致；全局max51.335295834秒与原进程实核相同。

- **criterion-3**（passed=True）：500点质量和时间均来自同一forest311322b revision2记录，主版本整体更新，未混旧witness质量或耗时。图仅展示质量—墙钟散点与分核ECDF，不画Pareto线、不做不同图点之间的算法支配推论；20.887372677秒仅为最大分核P95，图注未冒充全量P95。

- **visual**（passed=True）：实际查看最终624×797插入宽预览（165.1mm/8–11pt），两面板、五种点形/线型、全部尾部、5行median/P95/max表及资源底注清晰无遮挡裁切。与5-5本机候选同风格；自编plot_local读取原CSV，生成SVG/PNG/PDF。两CSV字节保持作者原值；修复audit角色、真实来源路径与可复现命令。audit SHA9955f53e625212f27df07559c4ebba1791f15b83b630a030a8570104e57ef7a5。
