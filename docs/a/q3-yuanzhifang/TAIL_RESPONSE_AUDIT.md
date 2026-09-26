# 单尾阶段响应的一次真实图静态核验预算

本批只核验 `tail_response_model` 对 067/k5 已冻结首波阶梯计算次序的精确性；不修改次序，不选切点或参数，不调用计划 builder、derive、Step、E0/E1/E2，不生成可提交计划。输出目录为 `results/a/q3-yuanzhifang/tail-response-static-20260925/`，只允许一次新的分析进程、10 秒超时、1 worker、0 重试。原 cold/E0 的 2 GiB 门槛与预算完全不变。

执行前将本文、响应模型/合成测试、`tail_response_audit.py` 一并提交固定。首波模型及其八个源码依赖仍逐文件对照 `68fbe66e97f78161bfb6f4f9e83cd2f0977ce7a9` 原字节；官方 code/config 使用已冻结 source-manifest 的 SHA。记录当前 HEAD 作上下文，不能把另一个不改这些文件的提交视为源码改变。

图 SHA 为 `f49b5087689e18c6bf231843f8f3bbaca238a547ea5309b2492c76d5f170b542`；配置 SHA 为 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。067 图从本机既有只读原件通过 CLI 传入，不复制或硬编码本机绝对路径。共享命令形式如下：

```text
python -X utf8 -B -m src.q3_yuanzhifang.tail_response_audit <case_067.json> --cores 5 --config data/raw/a/official/data/config.txt
```

Supervisor 在派发前用 Windows GlobalMemoryStatusEx 核对可用物理 RAM 至少 1 GiB，输出盘至少 256 MiB；不足/未知时只保存停止回执，零派发且不轮询。这个轻量静态分析门槛沿用前次静态模型核验，与完整 solver/E0 分开。使用低优先级子进程并保留超时、失败、原始 stdout/stderr 压缩字节及双 SHA；输出目录存在回执时拒绝覆盖。记录解释器启动至退出的外层墙钟、实际资源、命令、源码/输入身份和调用账。

核验先按冻结 `tail_stair_model.analyze` 生成一次计算次序及完整 DAG 最长路参考，再进行新四系数响应压缩；另一个不删除任何尾跳跃边的完整 DAG 递推独立保留全部操作结束时间。比较总 bound、每核完成时间、每段尾结束时间、各核入尾时间、切点和跨核原边数量。预期旧参考为 cuts `[0,20,44,66,94,124]`、h=2、首波 `[2,3,4,5,6]`、bound=11856672；差异原样保留，不能改参数凑数。

这是一个静态样本核验，计入本例离线研发成本；未来 cold solver 必须重新完成全部在线预处理。模块内计时只用于定位成本，单次观察不声称性能优势。即使全部一致，也只验证固定零 COPY/零 lag 模型；实际搬运、容量、Cache 和官方 Makespan 均未由本批证明。
