# 错开尾段波次的只读模型

`tail_phase_model.analyze` 是研究用次序模型，不是 solver 或正式成绩入口。它复用冻结 `wave_capacity.structure/model` 与 `wave_tail.partition_tail`，只在 `J=qk+1`、`q≥k−1`、`k≥2`、`L≥k` 且 `bmax≥2` 的同构串行作业上分析。原图索引、守卫、模型与切点仍是 case-specific 分析成本；如果未来用于在线求解，必须完整计入冷墙钟。本模块不生成或写官方两字段 plan，不调用 derive、Step 或 E0。

规则没有候选枚举。核 c 沿固定 round-robin 作业顺序先做 c 个完整作业；这些作业按 `bmax` 均衡分波，c=0 时没有前缀波。随后是一个包含核 c 所负责尾段的波，其中完整作业数为 `min(bmax−1,q−c)`；余下完整作业再按 `bmax` 均衡分波。尾段在该波自己的位置区间内、同位置完整作业之后出现。所有 k 核完整作业数仍为 q，尾部单作业只按固定连续切点跨核，每波局部作业数不超过 `bmax`。

输出每核 eligible compute ID 次序、每核完整作业波宽与尾波索引、切点、容量参数、原 M/V 计算工作量峰值及 `tail_fifo_bound.longest_path` 的零额外跨核 lag 必要界。该界只加原 eligible compute DAG 和每核 M/V Pipe FIFO 相邻边，忽略 COPY、spill、Cache 与跨核传输时间；关键路径及边分类有助于识别固定次序的等待。`共同输入字节×全核波数` 仅作共享波次的账面代理，**不是**尾部切分时的读取量保证。

纯全 M 的理想化前缀算术可解释相位意图：若每完整作业总工作为 W，核 c 与 c+1 在尾波前的完整作业前缀相差 W，而前一个尾段自身工作至多 W。因此，仅从这两个前缀释放时刻看，错开量足以容纳前段工作。实际尾段夹在同位置完整作业之后，且可有 M/V 交错、COPY 和跨核等待；此算术不是官方无等待证明，也不说明 Makespan 改善。应先看零 lag 下界，再决定是否值得开发可提交构造并做外部 E0 测量。

当前仅用合成输入验证全 eligible 覆盖、相位差、宽度和 `q` 守卫；没有运行真实 067、计划构造落盘、derive 或 E0。

根会话冻结后，只对067/k5用CLI执行一次候选次序静态分析（最长20秒、0重试）。沿用tail-fifo-audit的12份官方身份与12237901同身份比较记录，不请求新成绩台；全进程墙钟单列。入口 `python -B -m src.q3_yuanzhifang.tail_phase_model GRAPH --cores 5 --incumbent 12237901` 不输出提交JSON，也不进行在线或外部评分。这是独立研究小步，不重启此前资源停止的E0批。
