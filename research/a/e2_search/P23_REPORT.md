# P2/P3 E2 适配交付记录

负责人：NikolaStarx / session s-55b66a31d7bd49019122a179563dc1d2；分支 codex/e2-p23-20260924。

1. **任务目标**：解决仅支持P1、Q2/B无法接入的问题；P2固定检查点后扩展P3，不外推P1性能。
2. **输入文件**：冻结官方code/config及case004、case005；源码清单hash de11a83d…ce0。图/计划/配置和实测源码哈希逐轮见run.json、as-run-source.zip。无数据划分训练或拟合。
3. **输出要求**：SceneBEvaluator/problem=2|3、显式有界Batch、JSONL与完整官方CLI；代码/结果在research/a/e2_search及results/a/proxy/e2-p2-20260924、e2-p2-localopt-20260924、e2-p3-20260924、e2-p23-final-20260924、e2-p23-resources-20260924。吞吐/P95/CPU/RSS表见后者metrics.csv。详细入口/限制见P23_HANDOFF.md。
4. **限制条件**：原E0/E1、P1 f4分支、旧生产E2、Q2生成器/证据均未改。C++17/Python锁定环境；16MiB保留缓存预算/worker，非硬RSS；不内启线程。T0本地05:31，首阶段90分钟，各问题≤64唯一正式候选/≤160正式E0；本次各32唯一，正式总调用116/76、零失败。合成回归另列，不能把192正式调用声称为全部研发调用。
5. **验收标准**：各自官方E0完整候选对照，错误/回退/事件/缓存/并发检查。P2三字段/全部操作时间一致，P3另含完整缓存事件/最终条目一致；28组综合回归过，后续pool开关7组定点过。仅macOS作者验证。缺少对应问题优化E1，≥10×E1门槛不可验；冷全流程仅约1.5–1.6×E0，未满足超高速目标。Windows补丁待原独立测试者定点复核，LYX原测试保留。
6. **截止时间**：本轮07:01+08首阶段上限；实际开发在此之前收束，以Git固定提交和Issue回执为准，不自动延长实验。

## 交付记录

实际命令：

```sh
uv sync --locked
python3 scripts/a_materials.py --extract
uv run python -m research.a.e2_search.build_native --problem 2
uv run python -m research.a.e2_search.build_native --problem 3
uv run python -m research.a.e2_search.verify_b --problem 2 --output NEW_P2_DIR
uv run python -m research.a.e2_search.verify_b --problem 3 --output NEW_P3_DIR
uv run python -m research.a.e2_search.resources_b --output NEW_RESOURCE_DIR
uv run python -m unittest research.a.e2_search.tests.test_search research.a.e2_search.tests.test_scene_b research.a.e2_search.tests.test_resources -v
```

重复实测需使用各轮as-run-source.zip对应版本；不能用最新代码假装复现旧性能。
verify_b一次额外40 E0，resources_b一次各32 E0，复跑前由任务协调分配新预算。
源码阶段：25370d0 P2首版；7a33492局部优化；09ce468 P3；0e9bb98官方CLI；51f462d Windows控制修复。
后续资源开关/报告另一个提交，不改原实测身份。

失败/重试：开发微例先发现CompiledB字段名误用并修正；第一次AST改写测试遇ast.Dict.values列表被当函数，6组初始化报错（零该轮oracle调用），修正后通过；两轮P2首池冷性能差保留。正式E0三轮主验证、资源补测和8次新胜者双复核全部成功。此前合成迭代的fallback/worker/被终止在途调用未做统一逐次聚合，已知显式参考计数在测试输出，不能虚报完整研发调用总数；最终控制回归的完整日志与实测源码快照保留。

结论：P2/P3可进入独立接入测试，冷编译性能仍待突破。已实现和未验收边界独立记录。
未验证：Windows真实修复复核、全100图/所有2–5核矩阵、第三方盲测、同问题优化E1门槛、正式大规模搜索收益与Rust对比。
PR：https://github.com/huaweibei123/huaweicup2026/pull/46 （Draft，依赖PR42；未合main）。

新补充逐事件证据在 e2-p23-traces-20260924：P2/P3各32原生记录与既有E0逐项一致，胜者每图两份完整官方输出已保存；不是补造旧日志。每问题另4 E0，无新候选。Git换行规范化后交付清单按Git blob字节核查（派生CSV用LF），不改原始实测证据。

论文方法候选段落（开发验证范围）：我们将问题2与3的任务构建和官方语义验证保留在隔离模块内，使用原生事件回放计算搜索指标，并对不支持输入回退对应问题的未修改官方评估。P3独立维护DDR与只读FIFO缓存的共享带宽。两个给定图上的32份方案分别对照官方评分、操作时间及缓存事件一致；同worker、含启动与收尾的case005小批对照取得约1.5–1.6倍评分工程提速。该结果尚不证明全部用例正确性、最终方案质量改善或完整求解器提速，局部编译仍是主要开销。
