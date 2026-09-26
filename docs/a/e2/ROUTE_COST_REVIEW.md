# LYX 路由成本审计：专项有限只读复核

2026-09-24；复核者`nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`。
被审交付[09eef20b2285fadb88b2a6e2cad9b4bd9c389d88 / PR64](https://github.com/huaweibei123/huaweicup2026/pull/64)，
输入`603b0741e21c449d3db652ebd67c94f2dc014cc9`。结论：**在报告列明假设下，可采用单请求
完整评价次数条件上界；未发现阻止接收这份静态报告的问题。** 这不是完整调用图/原生二进制
的独立形式化证明，不是E2等价性、性能、Windows续测或共享服务终验；是否合并由调度决定。

## 核对结论及可采用范围

| 项目 | 结论 | 接入影响 |
| --- | --- | --- |
| P1 score/full | engine的单一fallback分支→P1Evaluator.evaluate_record→evaluate→派生_scene_a；完整E1≤1，严格冻结E0=0 | E1须独立预留和记实耗/unknown，不得视为免费；P1 full不满足纯E0 official_full |
| P2/P3 score/full | scene_b的单一fallback分支选本问题冻结完整函数；完整E0≤1，E1=0 | 每个可能回退请求事前保留本问题1次E0；不把两个problem一次配对算成一次 |
| 冷准备失败 | fast builder可已执行，再由完整后备重新build；最多两轮上层prep | 不能加算两个完整E0；也不能忽略额外CPU/wall/内存 |
| native开关 | True仍自动回退，False强制后备，公开API无fallback许可回调 | 零完整评价预算下不得用此开关声称native-only；私有调用不是公共契约 |
| started/中断 | pool ready仅初始化；send在active登记之前，timeout检查在响应读取之前，整chunk完成后yield | actual可未知而max仍≤1；没消费到结果不等于没执行。保留额度，无自动重投 |
| 调用方 | truth/final/shortlist和外部重试是额外调用 | 单候选上界不能推广到任意实验脚本总额；score和final分operation计费 |

条件是单次公开候选调用或一次派发、正常JSON形状输入、未替换的预期依赖/原生库、无外部
重入或重试。能力注册须绑定实际源版本、problem/mode、构建/ABI与表示，不能仅复制数字1。
P23路径counter在调用表达式前增加；route/counter与服务派发STARTED都不是完整函数体进入
证明。参数绑定前拒绝可证明完整入口0，单看TypeError名不能证明。成功可信native结果能说明
该次没有进入完整回退；完整记录丢失/异常不能据此类推。

旧resources_b的native批预留0与verify_b事后断言不构成事前预算保护，报告指出这一点正确。
这说明驱动缺少最坏路径保护，**不证明历史运行实际发生过超额**；历史实际次数仍按原证据。
CLI内部计时排除启动/import；pool同步send不受独立监控，不能作为进程硬wall截止证据。

## 实际阅读与检查

全文读审计Markdown/JSON；逐条检查18路由/6中断的口径。直接阅读固定输入中的：

- engine.py原生与公开入口、scene_b.py全文、batch.py构造/prepare/evaluate/record链；
- _official_b.py、_local_b.py全文，核对两个独立bundle与fast副本改写范围；
- pool.py全文、_full_cli.py、P1官方格式包装器、src/eval_exact/cli.py、problem1.py末尾完整入口；
- 冻结contest_io.py:197–265；以标准库AST只读解析派生_scene_a与冻结P1/P2/P3，列出完整
  evaluate/build/CLI调用位置，未见P2→完整P1或P3→完整P2调用。此文本检查不是helper全语义证明；
- resources_b.py:78–103、verify_b.py:85–120、benchmark.py:130–150、workflow_probe.py:42–57，
  核对事后账本与额外truth/final。未穷尽整个实验驱动总量。

本次无被审源码import、E0/E1/E2调用、原生构建、worker、算法/模型测试、依赖安装。
文档修改只在本专项PR63，未修改LYX两份原件或生产后端。现有10项模型结果未重跑，
不能为本轮新增E1分账/多operation/父stage停止域背书。保留LYX原独立E2测试任务。

## Fang父stage停止域：另一个接入缺口

全文读[5805545792](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5805545792)
及[5805578444](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805578444)，
直接读`0b58c123cccf02fc993b741d79dcd8511e4dd38f:src/q2/stage_b.py`全文和
budget_search.py的baseline/候选/停止/final/收尾分支。问题成立：只限制每experiment一个在途，
会允许拆开的多个case×method同时进入，从而破坏原stage失败后不启动后续unit的语义。

[设计](CONCURRENT_EVALUATION_DESIGN.md)新增stage→unit experiment→epoch映射：strict父stage
只有一个active unit，unit含baseline/探索/final；父控制器核对stop_after_unit和完整清理回执，
协调者持久放行下一unit。特定baseline拒绝仅阻断同case，其他监督/意外失败阻断stage；
祖先状态必须在派发事务内验证，跨unit并行须显式新策略。该修订尚待使用方核对与实际实现，
不是LYX报告的阻断缺陷，也不改变Fang封存实验或独立续测的授权。

本专项本轮邮箱完整抓取6话题293评论，仅按专项补读最新Issue15、33及公共26原文，
不声称已读全账号历史。Fang后续C/D/E单次批准与结果由其原协调链负责；本复核未接管驱动。
