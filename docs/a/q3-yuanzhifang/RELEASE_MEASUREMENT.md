# 第七批 release-order 有界测量

1. **目标 / 机制**：固定 JOIN 分核和每核 M/V FIFO 后，按增强计算 DAG 的最早开始稳定调整跨 pipe 优先序，检验官方 COPY 排序是否改善 Makespan。源码固定 `9c8bd47a53f3d68f4deefd460dbc8a361092f808`，算法说明见 [RELEASE_ORDER.md](RELEASE_ORDER.md)。计算下界不变不保证官方成绩改善。
2. **输入**：仅官方 069、请求 5 核、冻结配置与未修改 P2/P3 CLI。`release_benchmark.py --check-only` 读取并核全部 114 官方文件，以及算法依赖、运行辅助函数、既有单核分母和 JOIN 控制原件。控制固定 `ef80a88ed04b26e70465d56a54c373b0dcc5d00f`：069 P2=16742、P3=15221；不重跑控制，不由比值反推单核分母。
3. **输出**：新目录 `results/a/q3-yuanzhifang/release-order-20260924/`，记录真实 cold solver 与外评墙钟、实时硬件环境、plan、完整 result/trace/log、stdout/stderr、调用账、哈希、gzip 原字节、标准 feed 和固定提交预检。新的 runner/exporter 为 `src/q3_yuanzhifang/release_benchmark.py`、`release_export.py`；旧批次原件保持封存。
4. **限制**：独立预算 1 cold solver、至多 2 E0（同计划 P2/P3 各一次）；1 worker，单调用 30 秒、批 120 秒、90 秒后停派；首次失败/超时/守卫拒绝/清理异常立即停止，0 重试、E1/E2/GPU/云。runner 先提交，当前阶段仅允许只读 preflight；实际测量须等主会话确认 P2 释放窗口，不以瞬时进程空隙代替协调放行。
5. **验收**：生成后同时记录 plan 原字节相等和完整两字段 JSON 相等。JSON 比较包含完整 node_to_subgraph 映射与全部有序 core_schedules，仅忽略序列化空白和 JSON 对象键顺序，不把近似代理当等价。若与固定 JOIN 方案相等，记录本次真实 solver wall，引用旧 P2/P3 的原 run/attempt/time/hash，不调用 E0；标准 feed 的新成绩 records 为空，单独 `alias-reuse.json` 交代复用。否则仅运行本次两次 E0，保留改善或退化，P3 cache_pair 指向本次同计划 P2。旧 E0 时间不得作为新外评时间。
6. **时间 / 边界**：只有固定 runner 的 AST/只读身份校验属于准备，不计为 solver 或 E0；没有试运行本图 build/derive。父会话已报告两个合成正确性测试及全 suite 18 tests pass，属于另列研发成本。冷求解包含 JOIN 构造、最早开始计算、排序、输入输出及验证；外部 E0 独立列出。官方 5–10 分钟是效率建议，本批 120 秒是资源保护；局部证伪不代表全 100 图、独立验收或真机收益。

只读预检命令（不创建结果目录）：

```sh
python -B src/q3_yuanzhifang/release_benchmark.py --check-only --graph-dir ../huaweicup2026/data/raw/a/official-cases/data
```

实际放行后才可去掉 `--check-only`，并在结果提交后对导出 feed 运行 `protocol.py --submission --commit <完整数据提交>`。空 records 表示没有新的评分尝试，不能把“预检有效”解释为新增两条成绩。
