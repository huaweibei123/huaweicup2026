# P3 单一结构路由入口

`uv run python -m src.q3.adaptive_solve <graph.json> --cores 5 -o <new-plan.json> --evidence <new-directory>`。

入口只从原图与核数作路由，不读取case编号、历史最优或成绩台。先以计算source数量和固定lane分区选择collector策略，再由stage完整tensor/算子/重复阶段守卫验证：恰好两个最大lane负载核时轮换，其余固定。只有一次stage构造；守卫不适用则完整委派原guarded策略。除声明不适用外的构造、评价、保存异常都会显式失败。

成功stage分支直接给一个候选并在线E0一次；未与旧anchor比较，因此不承诺相对旧策略全面不退化。其余图保留guarded的anchor与最多一个release候选、下界剪枝和严格改善接收，最多两次在线E0。原始方案、结果、评价调用账本和最终计划沿safe_solve保存；静态metadata里的official_e0_calls=0只描述构造，router与最终receipt另记实际在线次数。

新增10项零评分注入测试覆盖lane/core模式、严格守卫拒绝、guarded改善/相同/退化/剪枝/合法性失败、保存引用及异常传播。全Q3套件80项本地通过。路由本身尚未进行100图×5核端到端测量，历史子算法成绩不能直接改名为此入口成绩。阶段算法已有三图k4固定及k5轮换的完整E0证据；其它路由和核数仍需固定版本运行。

该入口用于下一轮统一协议下的质量—耗时验证，并非新增搜索。拟议attention row构造尚在研究，不包含在此入口。
