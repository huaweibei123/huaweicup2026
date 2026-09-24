# P1 静态 Makespan 下界

本文件及 `src/q1/lower_bounds.py` 只分析原图、核数和显式 DDR 带宽，不构造方案、不调用 solver/E0/E1/E2。下界适用于冻结 P1 的成功执行方案，单位为模拟 cycle；不是方案成绩、可达性证书、求解时延或真机性能。最终方案仍由未修改 E0 验证。

## 来源与范围

以实现基点 `2cf3951af50be1e35ff78acb91629f2d0207bd82` 中以下文件为准；扫描产物另记录实际代码提交及逐文件 SHA-256，避免文件名相同而语义不同：

- [`schedule_step3.py` L28–30、L74–91](../../data/raw/a/official/code/schedule_step3.py)：每核四条 Pipe，每条 1 slot；普通操作时长 `max(1, cycles)`；COPY 按搬运张量大小、带宽逐操作向上取整，至少 1 cycle；只有带 DDR 端点的 COPY 加入共享带宽池。
- [`multicore_cut_evaluate_problem_1.py` L110–171](../../data/raw/a/official/code/multicore_cut_evaluate_problem_1.py)：去除原 COPY 后重建 Task；每个符合边界谓词的张量各生成一个 COPY；原 DDR 本地副本改为 UB。
- 同文件 L239–287、L318–329、L381–409：DDR 以独占带宽所需 cycles 为服务工作，所有活跃请求公平分享同一个总量为 1 的服务池；Task 门控只增加等待；普通操作依次占用本核对应 Pipe。
- [`stub_multicore_cut_and_schedule.py` L114–152、L188–240](../../data/raw/a/official/code/stub_multicore_cut_and_schedule.py)：每个非 COPY 原操作恰好属于一个 Task；不同 Task 的计算依赖进入 Task DAG。

固定配置为每核 L1 524288 B、UB 131072 B，DDR 60 B/cycle，同核 Task 等待 100 cycle、跨核 1000 cycle。本下界不使用容量或等待以加强结果，因而不会把某个候选的 Task 数/分核当作全局限制。函数 `lower_bounds(graph, cores, bandwidth)` 的核数和带宽均无隐式默认值；CLI 从显式 `--config` 读取带宽。它验证官方原图域，接受 1–5 核和正整数带宽。

这是整数资源/因果语义的下界论证，适用当前官方公开数据数值范围；没有为任意超大整数输入或修改版运行时提供浮点异常行为保证。DDR 全局实现有 binary64/EPS/ceil，不能把本方法称为跨任意数值域的形式化程序验证。

## 1. 不可省略的工作量

令 V 为全部非 COPY_IN/COPY_OUT 操作，`d(v)=max(1, cycles(v))`。Pipe 由原 `pipe` 字段确定，不按操作名称猜测。

对原张量 t，P(t)、C(t) 分别为其直接相邻的非 COPY 生产者、消费者。若存在原 COPY_OUT 消费者，记 H(t)=true。

```
I = {t | P(t) 为空且 C(t) 非空}
O = {t | P(t) 非空且 (C(t) 为空或 H(t))}
b(t) = max(1, ceil(size(t) / bandwidth))
```

每个 I 张量至少被一个 Task 读取；每个 O 张量至少被一个生产者所属 Task 写出。官方逐张量生成边界 COPY，因此它们对应不同的必要服务实例。原始位置为 L1/UB 不取消边界读写。多个消费者/生产者分 Task 可能增加实例，但下界只计其中一个。

**不能直接累加全部原 COPY。** 只在 COPY 之间流动、未触及非 COPY 操作的张量可能完全不进入重建 Task；原 COPY 也不原样保留。下界通过上述官方谓词重新计算，原 COPY cycles 不参与累计。SPILL 和额外分割 COPY 不在必要工作中。

```
D = sum(b(t), t in I) + sum(b(t), t in O)
W[p] = sum(d(v), pipe(v)=p)
       + (p=MTE2 ? sum(b(t), t in I) : 0)
       + (p=MTE3 ? sum(b(t), t in O) : 0)
L_ddr  = D
L_pipe = max_p ceil(W[p] / K)
```

DDR 总资源不随核数增加，不能除以 K；每 Pipe 有 K 个 slot，可以除以 K。必须先对每个必要 COPY 取整再求和，不能只对总字节除以带宽。零字节 COPY 仍有 1 cycle。所选必要工作只是完整执行工作的子集，因此忽略更多实例、竞争延迟、等待不会把界抬高到最优值之上。

## 2. 放松的关键路径

只保留两种计算边：非 COPY→非 COPY 的原直接边，以及非 COPY→原 tensor→非 COPY 的边。不穿越被排除的原 COPY 做传递收缩。

同 Task 的这两类边由官方局部图保留，不同 Task 由前驱 Task 完成门控保留。故它们对每个合法成功方案都成立。原输入图已验证为 DAG，其保留子图也为 DAG。

概念上为每个 I 张量添加权重 b(t) 的输入节点，连到 C(t)；为每个 O 张量添加权重 b(t) 的输出节点，由 P(t) 连接。实际实现不生成官方 Task，也不编译这些虚拟 COPY，只做 DAG 最长路。

对操作 v 定义必要释放时间 r(v) 和完成后的必要尾部 q(v)：

```
r(v) = max({0}, {b(t): t in I, v in C(t)},
           {r(u)+d(u): retained edge u->v})
q(v) = max({0}, {b(t): t in O, v in P(t)},
           {d(w)+q(w): retained edge v->w})
L_cp = max_v (r(v)+d(v)+q(v))
```

这些是因果下界而非预测开始时间。多个实际输入 COPY 不妨碍证明：每个消费者都需要一个至少 b(t) 的读取；多个输出 COPY 时，每个生产者都必须完成相应必要写出。没有声称不同 Task 共用一个真实 COPY。

**COPY 桥反例**：原图 `M100 -> x -> COPY_IN -> y -> V100`，x、y 各 60 B。两计算放在同一个 P1 Task 后，原 COPY 被移除，得到 `M100 -> COPY_OUT(x)` 与 `COPY_IN(y) -> V100` 两条独立路径。操作级关键路径下界是 101，而非把桥收缩后得到的 200。单测检查这一静态反例，不声称执行过其 E0。

基础下界：`L0 = max(L_pipe, L_ddr, L_cp)`。不能求和，因为资源之间能够重叠。

## 3. 简单释放时间/尾部强化

资源上的必要工作表示为 `(r, d, q)`。普通操作使用上节计算值。必要输入 t 选取服务于最大后续尾部消费者的一次真实读取，使用：

```
(0, b(t), max_{v in C(t)}(d(v)+q(v)))
```

必要输出 t 选取最大必要释放时间生产者对应的一次真实写出，使用：

```
(max_{v in P(t)}(r(v)+d(v)), b(t), 0)
```

这些不同张量各对应至少一个不同真实 COPY，即使实际计划有更多副本。对某资源全部所选工作，记 `rmin=min r`、`qmin=min q`、`W=sum d`、容量 c。全部所选执行/服务都发生在 `[rmin, M-qmin]` 内，故：

```
M >= rmin + ceil(W / c) + qmin
```

每 Pipe 取 c=K，全局 DDR 取 c=1；空工作集取 0。最终 `lower_bound_cycles` 为 L0 和各资源强化值的最大值。这里**没有实现**完整双阈值资源窗口或区间树扫描；不能使用另一个完整版算法算出的更强数字冒充本文件输出。

在 op 邻接已经形成后，最长路与资源归约为 O(n+m)，空间 O(n+m)。从原二部图展开边还包含每个张量生产者×消费者的成本，官方输入验证与确定性初始化也有排序开销；不把对任意原二部图的完整 CLI 笼统称为严格线性。

## 4. 与官方成绩对照时的解释

给定同图、同核数、同配置下通过官方验证的成绩 U，及本下界 L：

```
L <= OPT <= U
U/OPT - 1 <= U/L - 1                 # 相对最优值误差的上界
(U-OPT)/U <= 1-L/U                   # 当前时长最多还能降低的比例
```

U/L 接近 1 时，可报告“相对最优值的差距至多……”。U/L 很大不能证明对应空间必然可实现，可能是下界松。不得把下界当新方案提交成绩台，不替代官方单核分母，不用下界相除冒充官方平均加速比。完整分量同核的限制、已选划分的 Task 数和独立 Task 时长，也不能擅自加进全局下界。

## 5. 复核与静态扫描

```
uv sync --locked
uv run python -B -m unittest tests.q1.test_lower_bounds -v
uv run python -B src/q1/lower_bounds.py \
  --scan-zip data/raw/a/official-cases.zip \
  --config data/raw/a/official/data/config.txt --cores 1 2 3 4 5 \
  --output results/a/q1-lower-bounds-20260924/static_bounds.json
```

先提交代码冻结实现，再运行静态扫描。输出保存 ZIP/每个 JSON/config/相关官方文件/实现/锁文件的 SHA-256、实际代码提交、Python 版本、每图每核各组成项，以及明确的 `solver/E0/E1/E2=0`。`kind=static_makespan_lower_bounds_not_performance`。这些身份字段说明来源，不代表做过 evaluator 等价验证。输出拒绝覆盖；重新生成必须使用另一路径。

单测范围：零周期、并行 Pipe 工作量、串行关键路径、输入/输出释放尾部强化、DDR 逐 COPY 取整及全局资源、被删除 COPY 桥、无计算消费者的原 COPY、多生产者输出，以及参数/原图校验。所有测试均不执行 evaluator。
