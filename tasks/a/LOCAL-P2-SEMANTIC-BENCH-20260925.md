# P2 unified semantic 500-cell benchmark

负责人：@NikolaStarx；执行会话 `nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc`

分支：`codex/p2-semantic-bench-s59ee-20260925`

1. **任务目标**：测定固定 P2 unified semantic 算法在 100 个官方图、1–5 核上的全部 500 个坐标。原 6e5099 版本不续跑；历史最优组合不等于本算法成绩。
2. **输入文件**：`data/raw/a/official/data/case_001.json` 至 `case_100.json`、冻结官方配置及代码、固定源码 `b7c05cf2205bd42ec23680e618a10796b37562f6` 的 `src.q2_nikolastarx.adaptive_semantic`。完整坐标、资源与停派规则见 `src/local_benchmarks/s59ee_p2_semantic_manifest.json`。
3. **输出要求**：独立目录 `results/a/q2-nikolastarx/semantic-benchmark-s59ee-20260925/<run_id>/`；每格保留计划、零在线评分账、独立官方 E0 的结果/trace/log、过程收据与 SHA-256，生成标准 feed，交专责成绩台会话导入。
4. **限制条件**：最多 500 solver、500 E0、零 E1/E2、零自动重试；每格 solver 30 秒、E0 120 秒，整批 3600 秒。前 4 格 2 workers，随后 12 格 4 workers，再至多 8 workers；每个子进程组采样 RSS 上限 4 GiB，启动前可用内存至少 6 GiB。首个求解/E0/证据/资源/清理异常停止新启动，已在途收尾。不要与 P1/P3 的高并发批次重叠。
5. **验收标准**：运行前 runner、manifest、固定 solver、114 份官方输入哈希一致；500 个坐标均有成功、失败、超时或未启动终态和真实调用账。成功格需官方 E0 成功、plan/E0 原件哈希一致；均值以同版 `n/100` 为分母展示，缺失不补零。固定 Git 原件通过成绩台接收后才称已上台。
6. **截止时间**：无用户设定的日历截止；P1 小批和 P3 研发评分窗口释放后尽快开始。

代码与结果提交、实际 T0/T1、运行环境及未验证项在完成后补充，不能用本任务卡代替结果收据。
