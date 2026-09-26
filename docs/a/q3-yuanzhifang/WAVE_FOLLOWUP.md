# 波次候选的独立资源窗口补测

**状态更正：已冻结但取消启动，实际0cold/0E0。** 在等待资源时发现完整作业不可分割下界：067的71个作业各含829792个M周期，五核至少一核承载15个，故Makespan≥12446880，已大于同身份成绩台当前12237901。该界同时排除full/capacity两模式在此格超过当前主指标；不排除其DDR/求解耗时Pareto价值，也不适用于部分作业拆分。取消未启动的调用，不伪造失败运行或重用旧账。下一研究是仅拆分一个余量作业，另行冻结源码与预算。以下保留原预登记，a023787a2的零调用来源预检仍为历史事实。

第十六批固定05e83317f在首派前因RAM不足停止，实际0cold/0E0；全部原件保留。新批使用唯一run ID `yuanzhifang-q3-wave-followup-20260925`、唯一目录 `results/a/q3-yuanzhifang/wave-followup-20260925`，只为未测的067/k5两格取得首份数据，不重跑任何已测计划。

算法仍为2cf325fb717077cd902830e7f01c920d27cbf8ec，模式固定full再capacity。逐字节复用c42dbacf的测量runner、相同官方输入/config/E0/分母及同一预算：最多2 cold+4外部E0，1 worker，每调用60s、总300s、240s停派，RAM与磁盘均至少2GiB，首失败停、0重试/E1/E2。全量指标、合法性、P3条件界及COPY事件覆盖检查不变。导出器只增加实际wrapper入口的来源记录；旧feed不覆盖。

开始条件：与本机P1/P2协调新的资源窗口，并在准备期间至少两次只读资源快照（间隔至少30s）看到可用RAM≥2GiB；这不是在派发时替代固定2GiB门控或保证全程独占。快照不启动构造或评价；未满足时继续理论/代码工作，不循环启动runner。wrapper拒绝旧manifest不是已知0调用停止的情况，拒绝覆盖结果目录。完成或失败即释放窗口并保留新账。

```powershell
python -B src/q3_yuanzhifang/wave_followup_benchmark.py --check-only
python -B src/q3_yuanzhifang/wave_followup_benchmark.py --concurrent-work P1+P2
python -B src/q3_yuanzhifang/wave_export.py results/a/q3-yuanzhifang/wave-followup-20260925
```

只读预检0构造/derive/Step/E0。父研究者控制启动窗口；Luna medium只运行一次冻结命令与导出，失败交回，软token目标2000、实际用量不可用、无客户端硬token cap。
