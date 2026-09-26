# 单余量作业切分候选

`src/q3_yuanzhifang/wave_tail.py` 是独立研究入口。仅当 `wave_capacity.structure` 的严格同构串行作业守卫成立、`k≥2`、作业数 `J=qk+1` 且位置数 `L≥k` 时进入新构造。其他输入显式 `guard=false`，调用现有 `active_stages.build` 回退；实验 runner 应拒绝给回退评分。该候选没有在线 Step/E0、参数扫选或按 E0 择优。

前 `qk` 个完整作业按固定原图作业顺序轮流归给 k 核，每核恰好 q 个。最后一个作业是唯一跨核余量作业；在位置切点 `0=c₀<c₁<…<cₖ=L` 上，核 c 执行 `[c_c,c_{c+1})` 的连续段。每位置的 op/Pipe/正整数周期和私有 tensor 签名均来自原有守卫。令单作业各位置计算周期为 `m[p]`、`v[p]`，以 `O(kL²)` 动态规划最小化

`max_c max(q·Σm + Σ_{p∈segment_c}m[p], q·Σv + Σ_{p∈segment_c}v[p])`。

相同主目标下，按模型私有 tensor 在内部切点存活的字节和作次级代理；再相同则按固定遍历顺序确定结果。实现用两遍 `O(kL²)` DP：先求全局最小峰值 `T*`，再只允许每段工作量不超过 `T*`，求最小加性边界字节并重建切点。不能只给每个前缀保留一个 `(峰值,字节)` 状态，因为后续峰值可能抹平前缀峰值差。它不是实际跨核 DDR 流量、官方 Makespan 或 E0 分数。DP 不枚举候选交给 E0。

完整作业沿用 `wave_capacity.model` 的 `W/A/F` 长残差容量包络。以 `q+1` 为最大可能同波作业数得到 `bmax`，若 `bmax<2` 则回退。取 `wave_count=ceil((q+1)/bmax)`，将 q 个完整作业均衡分入这些 wave，较大的 wave 在前，最后一波有 `floor(q/wave_count)` 个完整作业，并仅在负责的切点区间加入余量作业，因此最后一波的局部作业数不超过 `bmax`。若无法形成非空完整作业 wave，也回退。每核按 `(wave,position,jobID)` 排列，所有 eligible compute 为 canonical singleton 子图；`derive_multicore_plan` 在冷构造内作静态合法性检查，输出只有官方 `node_to_subgraph`、`core_schedules` 两字段。

元数据记录完整作业归核、切点、余量作业段归属、波次大小、每核 M/V 计算工作量必要下界、DP 目标、F/A/W、容量、守卫与 `internal_e0_calls=0`。模型容量是构造代理；尾部跨核造成的 COPY、spill、Cache 与实际调度时间须由官方外部评估核查。完整作业版本的 `W×wave_count` 共享读取条件界**不无条件移植**到本候选。冷求解墙钟应从进程启动、图读取、索引、守卫、DP、构造、静态检查到计划落盘完整计量，外部 E0 另列。

合成验证覆盖 DP 与独立穷举、唯一尾部切分、eligible op 恰一次、每核顺序、计算工作量及不适用守卫。没有以官方真实图调参，也没有运行官方 Step/E0。
