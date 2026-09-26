# 完整作业归核的容量波次候选

`src/q3_yuanzhifang/wave_capacity.py` 是独立研究入口，默认 `--mode capacity`，另有固定的 `--mode full` 对照。两种模式共用同一作业分核、canonical singleton 映射及输入守卫；full 每核只排一个包含全部作业的 wave，不根据 E0 分数选择模式。原图读取、索引、守卫、模型、构造、静态合法性检查和计划落盘均发生在该次冷 solver 进程内；没有在线 Step/E0 选优或离线针对当前图的参数表。

守卫要求至少 k 个完整独立作业。每个作业的 compute 长度、每位置 op/Pipe/正整数周期、依赖边型，以及私有 tensor 的空间、大小、compute 生产/消费位置和原始 COPY 连接签名都须相同。Compute 只能用 M/V Pipe；共同输入没有 eligible compute 生产者，每作业恰有一个同位置的 compute 消费者。允许共同权重由单个原始 `COPY_IN/PIPE_MTE2` 写入，但其来源必须是唯一且只连该 COPY 的 DDR backing；拒绝共同权重上的 COPY_OUT、多个写入者和异常 backing。私有 tensor 首版拒绝多个 eligible compute 生产者。私有原图输入只在首位置单次消费；最终输出只由末位置生产；无跨作业计算依赖、共享写或部分作业共享输入。原始 DDR COPY backing 本身不计入片上容量，直接与 compute 相连的 DDR tensor 在首版拒绝。任一守卫失败会生成已有 `active_stages.build` 的显式 `guard=false` 回退，后续 runner 不应评分该回退。

对每个空间 r 和单个作业，按私有 tensor 首末 compute 邻接位置 f、l 求 `F_r[h]=Σ size(t)`（`f<h≤l`）和 `A_r[p]=Σ size(t)`（`f≤p≤l`）；`W_r[p]` 是该位置共同输入大小。长残差的整个跨度参与 F/A。F/A 用每 tensor 常数次差分更新及长度 L 的前缀和计算，复杂度 O(T+L)，不逐 tensor 扫描跨度。取最大分核作业数为初始 bmax；各 r、p 计算 `H=capacity-W-A`、`D=max(F[p],F[p+1])`。`H<0` 拒绝，`D>0` 时更新 `bmax=min(bmax,1+H//D)`。不枚举候选宽度。k 核按固定作业顺序轮流分配完整作业；每核以 `q=ceil(n/bmax)` 个连续均衡 wave 排列，实际优先序为 `(wave,position,job)`。每个 compute 单独成子图，计划只含官方两个字段，并由 `derive_multicore_plan` 静态检查。

元数据记录守卫、F/A/W、bmax、分核 wave 大小、模型容量、`W_total × Σ wave_count` 条件性共享读取量，以及 `shared_L1 > k×L1_capacity` 是否成立。这个入口**不**用最后一项作为生产触发器。F/A 包络不证明官方零 spill；共享读量界依赖冻结 Step2 语义与守卫，尚未独立在 E0 验收；均不推出 Makespan、Cache 命中率或真机收益。Pro 归档第 4、6 节是构造来源，关键引理仍须以冻结源码和最小反例核查。

合成测试覆盖长残差 F/A、容量等号与差一字节、均衡 wave、singleton 覆盖、完整作业单核、同分核 full 对照、私有签名不一致、直接 compute DDR 和共同输入多位置拒绝。没有用真实 067 调参，也未调用官方图构造、Step 或 E0。
