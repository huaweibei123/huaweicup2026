# Q3：只读 Cache 构造与官方对照

2026-09-24 后续用户已授权依据 Pro 与方案成绩台进行新一轮研发/子代理评测，并与 Fang 的 Q3 专项互通。
新阶段六字段和事前清单见 [反馈迭代01](../../docs/a/q3/FEEDBACK_ITERATION_01.md)；下文首批预算为历史，保持封存。

用户随后明确要求持续研发，当前推进[反馈迭代02](../../docs/a/q3/FEEDBACK_ITERATION_02.md)：
有证明的容量阈值子步骤及每核多片段分配，与旧树构造作独立在线对照。阶段交付不表示停止研发。

负责人：@NikolaStarx；session `nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc`。
分支：`codex/q3-core-nikolastarx`，起点 `6a7c678df58613445efaf89d9a5221702955fa22`。
沟通：[Issue 51](https://github.com/huaweibei123/huaweicup2026/issues/51)。
用户 2026-09-24 指派；Q1 为 s-8ee33、Q2 为 Fang s-25ac；公共 Atlas 由协调 s-a5bd 汇总。

1. **目标**：生成官方两字段 P3 合法方案，降低 Makespan cycles，另列搬运字节、按字节 Cache 命中率、输入到方案落盘的求解墙钟。先交有限、可证伪的构造基线，不宣称全题完成。
2. **输入**：`data/raw/a/official/data/case_{008,044,080}.json`、固定 `config.txt`、原版 code；源码清单 `docs/a/source-manifest.json`。公开开发图，非封存集；4 核。原件不改。Pro2 固定提交 `3a4505d4101e23d54580d15560da3820e02d05da` 的 `resource_word.py`、`construct.py` 提供构造假设，作者实验不当本机成绩。
3. **输出**：`src/q3/`、`tests/q3/`、`docs/a/q3/`、`results/a/q3-nikolastarx/pilot-20260924/`：精确计划、无损 E0 JSON、源文件及输入 SHA、命令、实际调用账、冷构造进程墙钟、官方复评墙钟、指标表、方法与论文局限段落。直接构造不在线打分；比较程序事后选胜者，不冒充完整求解器。
4. **限制**：同一 Pipe 负载分量分核；所有候选固定 op-core 与 singleton ID/字典顺序，只改核内优先级。候选 component、affine_eighth、受守卫 resource_word；后者只允许同构串行 M(a)→V*(b)→M(a)、b≤2a，其他图跳过不另加替代候选。仿射 1/8 是研究原件的单个事前固定参数，不扫描。最多18次 P2/P3 配对+3次 P3 复核，24总上限保留3次仅供明确故障恢复；首个失败停查，不自动重试/扩候选。1 worker，单次30秒；整批准备、构造、评估和输出300秒，软件开发时间单列。8组有限结构单测，0合成 E0。不使用云/新依赖/随机搜索。5～10分钟是建议，不能以低于该值宣布效率完成。
5. **验收**：官方 COPY 收缩保留依赖；候选同 op-core；结构/覆盖测试；所有实际正式方案通过原版 E0；P3优选完整结果独立复核；同计划 P2/P3 比较与跨计划收益分开；首次范围外/全100图/1～5核/独立平台均未验收。实验前提交源码和本卡，失败也入账。无收益同样交付反例和收缩方向，不凭命中率宣称变好。
6. **截止**：没有用户硬截止；先交本轮有限检查点（Asia/Taipei 2026-09-24），再据证据定下一阶段。

## 交付记录

执行入口：`uv run python -m unittest discover -s tests/q3 -v`；
`uv run python -m src.q3.experiment results/a/q3-nikolastarx/pilot-20260924`。

实验前固定源码 `c1ea79869f183dc4a7a830ecfd4dae27650e680b`；17次正式E0全部成功，
8组结构测试通过、0合成E0。完整实测、计时范围和局限见
[REPORT](../../results/a/q3-nikolastarx/pilot-20260924/REPORT.md)。
另交本任务图件 `figures/a/q3-nikolastarx/pilot-20260924/`，由 `src/q3/report.py` 读结果生成，
SVG/PDF/PNG和输入/输出哈希齐备；已查看PNG，三面板同零基准、文字/图例无遮挡，非科学独立验收。
本批仍为有限开发基线，不是最终问题三验收。PR发布后在Issue51交接。

### 在线路径增量

经Issue51评论5804808985单独安排，固定 `a278f78fdf98b90be9c43475474637589c8929e7`
新增3次P3路径检查，全部成功；旧批次不重写，累计20次正式E0、0合成E0。
`src/q3/solve.py` 从结构选一个构造，在线E0验证成功才发布计划；没有按旧成绩/文件名选方案。
完整进程wall含验证/写盘/退出约100–121ms；不能沿用仅构造的28–32ms作为这条路径的时间。
新增3组软件测试加原8组共11组通过。证据在
[online报告](../../results/a/q3-nikolastarx/online-20260924/REPORT.md)，
预登记及时间范围在[在线协议](../../docs/a/q3/ONLINE_PROTOCOL.md)。
