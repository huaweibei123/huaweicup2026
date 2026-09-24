# P2 adaptive direct：全域结构覆盖，非性能成绩

统一候选入口：`src/q2_nikolastarx/adaptive_direct.py`。每次只构造一个方案，按以下固定优先级路由：

1. 现有齐次 M–V*–M `word_descriptor()` 守卫满足，走 `resource_word`；
2. 否则，弱连通组件数不少于核数，走 `component_envelope`；
3. 否则，走现有 `dag_eft`。

只读取原图、核数、固定配置。没有 case ID 表、历史计划、成绩表、训练参数、网格或在线评价；word guard 以外的构造错误不会被吞掉再试另一方案。每次仅创建一个 `DAGIndex`，三条分支复用它。

父会话授权对 `component_envelope.py` 作唯一最小提取：原 `build(graph,cores,config)` 创建索引后调用新增 `build_from_index(index,cores,config)`，原批构造主体保持不变。`helper-equivalence.json` 比较已经完成的014/025 × 2/4/5六格：完整计划字节和完整函数 detail 均相同；没有重跑官方评价。原CLI的计时/日期不作逐字等同声明。

## 证据文件

- `check.py`：本次单worker静态检查脚本，不修改原件；已有证据文件存在时拒绝覆盖。
- `rows.jsonl`：固定100图 × 1–5核逐格状态、路由、原图哈希、完整计划序列化哈希、计划大小、官方结构校验、原始子图DAG合并核内次序的无环检查；未保存500份计划原件，可由固定源码和输入重建。
- `coverage.json`：完成后的总计、按核数路由覆盖与case清单、源码/配置/脚本哈希、冻结官方manifest核对、源文件运行前后哈希、局限。
- `helper-equivalence.json`：上述六份已完成原件的等价性核对。

复现命令，在工作树根目录执行（既有证据需先保留并使用新的审计目录，脚本不自动覆盖）：

```sh
PYTHONPATH=. .venv/bin/python -B results/a/q2-nikolastarx/adaptive-static-20260924/check.py
```

测试命令：

```sh
.venv/bin/python -B -m unittest \
  tests.q2_nikolastarx.test_adaptive_direct \
  tests.q2_nikolastarx.test_component_envelope \
  tests.q2_nikolastarx.test_dag_direct \
  tests.q2_nikolastarx.test_direct_solve -v
```

已执行27个测试、全部通过。其中路由/CLI的无评价测试以及本次静态全覆盖，把官方 E0 入口、task compilation 和 subprocess launcher mock为一旦调用就失败；这部分检查calls=0不只依赖算法自报。其余手工结构测试也不调用评价器。只读子agent核对了路由条件、API分支、异常边界及helper提取，没有发现具体问题；它继承了开发上下文，不称隔离盲审。

CLI符合matrix direct契约：graph/config/cores/output/evidence/wall；只输出合法结构的双字段JSON，独立证据中单attempt为`adaptive_direct`，包括selected、plan_sha256和全部为0的E0/E1/E2 calls；已有output拒覆盖。真实进程端到端墙钟需要未来正式runner测量。

## 解释边界

本目录没有官方 Makespan、DDR 或性能加速比。函数构造计时不含解释器启动、读取输入/配置、序列化和方案落盘，且机器不独占，不能当作完整求解耗时。整个静态审计耗时另外记录，含重复结构验证、等价性检查和哈希。

100×5结构通过也不证明P2执行图通过Step2/Step3/跨核联合约束，更不能证明优于Fang或达到图片平均指标。`component_envelope` 的证书仍只覆盖原tensor priority前沿，未满足充分条件的singleton保留为uncertified，不声明零spill。

016-k2和062的组件内部内存/切割瓶颈仍然存在；在组件数少于核数时，本路由有意保持已知一般DAG行为。word守卫只是计算结构的窄域条件，不包括完整容量证明。这个版本的用途是交给中央批次获得统一、可追溯的全域官方反馈，静态覆盖不能代替该环节。

## 本次完成结果

500/500通过，0失败、0 E0/E1/E2。路由总计：component_envelope 421，dag_eft 64，resource_word 15；resource_word为008/084/095各1–5核。静态审计总墙钟约106.71秒，口径见coverage.json。

| 核数 | component_envelope | dag_eft | resource_word |
|---|---:|---:|---:|
| 1 | 97 | 0 | 3 |
| 2 | 81 | 16 | 3 |
| 3 | 81 | 16 | 3 |
| 4 | 81 | 16 | 3 |
| 5 | 81 | 16 | 3 |
