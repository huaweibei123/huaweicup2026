# Stage G：051/k5 整链根核预取，实测完成

E0 Makespan **234536**，比既有 C 的253856降低 **19320周期（7.6106%）**；单格官方单核比 **2.59076645**。本批实际 **1冷solver+1外部E0**，均成功，0retry/E1/E2。cold solver **0.5056320秒**，独立E0 **1.4357794秒**；共享资源环境，不能据跨批耗时差声称算法提速。

作者 `e29685da0268420f2d881246603763d6bf8baf5b`，实际runner `902000f6504f5c23e566f02d434a176ec9e83ceb`；与准备版66f4559相比仅任务卡更正服务量下界措辞，算法与runner源码字节不变。批次T0 `2026-09-24T17:55:51.560790Z`、T1 `17:55:53.758253Z`，2.1977067秒。预算封存，不追加评分。

144 Tasks，调度搬运9438614B、总额外9045396B、spill0，与C完全相同；逐(tensor,direction,bytes)边界COPY多重集也相同，共1003个。原外部重复加载仍9043968B。R从180644升到208152，E0反而改善，说明仅计算/gate和总DDR工作量不足以排序这两个计划；不能将收益唯一归因于预取，未做完整trace因果分解。

原件在 `run/`；[逐例比较](run/comparison.csv)、[静态DDR分析](run/ddr-analysis.json)、[COPY多重集对照](run/copy-signature-comparison.json)、[完整报告](REPORT.md)。标准feed为 [board-feed-20260924T175725Z-stage-g.json](board-feed-20260924T175725Z-stage-g.json)，[本地预检](precheck-local.json) `valid=true, eligible=1`。单例不代表全100均值；未代签成绩台接收、上台或独立复跑。

原件固定 `45fde88569b4ce877bda397ae32bc9a1b4abf082`，对应 [固定Git字节预检](precheck-fixed-45fde88.json) 亦为 `valid=true, records=1, eligible=1`；该预检不执行solver/E0或写中央服务。

## 原准备记录（保留）

新族 `q1-guarded-intact-prefetch / fixed-root-four-two-v1`，作者固定 `e29685da0268420f2d881246603763d6bf8baf5b`。只准备这一个真实单格，没有求解、评分或Task编译，F预算保持封存；完整零评分身份预检后仍需父审阅与START。

固定构造假说：首轮12条四节点重链按3/3/2/2/2分配，之后4/2/2/2/2，独立归约尾固定核0；预计144 Tasks，计算+Task门控模型R208152。保留大tensor链并利用根核可早900周期启动是否改善实际DDR时间线，必须经过官方E0证伪，不能由模型值预言胜负。

本轮新授权至多1solver+1E0，1worker，30/90秒、全批180秒、0retry/E1/E2。等待父审阅runner与明确START；不自行抢窗口。旧C051/k5的253856周期和9438614B调度搬运只引用 `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a` 原件，不重跑。

任务六字段见 `tasks/a/q1-yuanzhifang-stage-g.md`。本目录只含准备文档，`run/`尚未创建；后续必须独立首次创建、保留全部正负结果和失败、分别记录cold solver wall与外部E0wall。标准feed仅在实际尝试后生成；source/runner/输入/官方byte哈希、完整原件与固定Git预检保全，不直接写中央服务。

[零评分预检收据](preparation-checks.json) 已通过：5算法源码依赖、10官方源、051/config及旧C原件固定字节；AST语法与旧计划静态DDR分析通过，0solver/E0/Task compiler、0全图扫描。准备耗时19.948239秒包含硬件清单，不是算法性能。父审阅与明确START仍是下一步，未执行本轮预算。
