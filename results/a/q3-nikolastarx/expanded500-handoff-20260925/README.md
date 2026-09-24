# 固定expanded算法全500交接

source **a5dafdf94d0694132fb9ec7121f5fe1fe0d6ee3b**；入口 `src.q3.expanded_solve`，runtime q3-central-expanded-20260925。材料提交不等于评分源码。先前3格正式probe已成功，仍需该入口完整100图×1～5核的新运行，不拼旧2d5赢家。

执行者沿用生产session s59ee；输出独占前缀 `results/a/q3-nikolastarx/expanded-full500-20260925-s59/`。请在P2已排3格完成并实际释放后执行；本研究session不并行复制批次、不写生产输出。10个manifest互斥，每片50格，上限100 E0/360秒/90秒每格；总500solver/1000E0/3600秒，最多8并行片、每片1worker、0重试，首失败按原runner保留并停该片。既有控制器可复用，但固定其真实源码hash与最终收据hash并分开标注。

每片执行固定source下 `python -B -m src.q3.feedback_benchmark manifest-sNN.json <独立输出/sNN>`。沿用统一2d5生产时已核的原图、官方、配置和单核分母原字节，评分前重新核输入/源码SHA；缺原件不重跑分母。其余identity/全500每格E0证据、进程清理、时限与计时口径遵守原统一500交接规范。

本批源码/参数/选择规则完全冻结。stage/attention规则保留；一般fork/join使用Fang固定a37eb931 gap对同次新评anchor择优，至多2在线E0，全部费用计完整solver wall。不改变这10份manifest的候选规则来追逐得分，不跳过3个已探针格或任何未测格。失败/超时/未跑完整保留；仅全100/核完成后报告统一均值。
