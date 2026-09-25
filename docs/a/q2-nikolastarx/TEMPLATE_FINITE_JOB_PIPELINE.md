# 有限 job 标量流水切分原型

`template_finite_job_pipeline.build(graph, cores, config)` 是独立入口，不改变现有 stage-major 或容量 job-major 默认算法。复用严格同构 job 识别和 `S_shared+P_private` 两池容量上界；只在容量合格的连续模板区段上切分，生成每核 job-major priority，并用独立 `zero_spill_intervals.certify` 复核。输入 `cross_core_copy_delay_cycles` 必须为非负整数。

对某个切分的第 `r` 段，取绝对标量服务时间 `d_r=max_p Σ_{u∈段,pipe(u)=p} max(1,cycles_u)`。令相邻段固定延迟 `δ`、同构 job 数 `J`，理想串行阶段系统满足 `C[r,j]=max(C[r,j−1],C[r−1,j]+δ)+d_r`；它的末 job 完成时刻为

`F = Σ_r d_r + (J−1) max_r d_r + (k−1)δ`。

此等式对**每段一台标量服务器、各 job 依次通过所有段、固定边界延迟**的模型精确。它不是官方 E0 的 Makespan 公式：每核四 Pipe 可重叠、COPY 工作及跨核传输个数随切点变化，共享 DDR、Step3 重排和实际 release 也未进入 `d_r`。因此 F 只用于构造目标，不是官方上界或下界，也不能声称吞吐收益。

DP 状态是 `(已用段数, 模板前缀末端)`；标签为 `(累计 d, 最大 d, 切点)`。同一最大值只留最小累计值，再取最小字典序切点。不同最大值之间，较小最大值的标签只有在累计值严格更小，或累计值相等且切点字典序不大时，才能支配另一标签；累计值相等、较大最大值却有更小切点时须保留，因为后续段可能使两者最大值相同。对保留标签和每个容量合格区段作转移，最后在所有 `1≤k≤min(cores,S)` 中最小化 F，等值时先少核再按切点字典序。每个状态的最大值最多有 `D≤S(S+1)/2` 种（所有区段的 `d`），故标签数至多 D。区段上界预计算 `O(S I log S)`，DP 最坏时间 `O(K S² D log(SD))`、含切点元组的空间 `O(S²+K² S D)`；`I` 为一个模板的 tensor touch 数。固定拒绝边界为 `S>256` 或超过 2,000,000 次可行标签转移；无容量可行切分也显式拒绝。

合成测试命令：`python3 -m unittest tests.q2_nikolastarx.test_template_finite_job_pipeline -v`。4 项通过：独立递推与闭式逐切分相等、异 Pipe 绝对周期的穷举切分与 DP 一致、边界延迟使少于可用核数最优、容量与预算拒绝。等值反例 `[1,1,2,3]` 单 Pipe、两 job 中，切点 `(0,1,3,4)` 与 `(0,2,3,4)` 都得 F=10，前者是全局字典序最小切点。此轮没有构造真实 case 计划或运行 E0/E2。
