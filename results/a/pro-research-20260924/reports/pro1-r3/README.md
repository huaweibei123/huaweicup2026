# 华为杯 A：结构构造小原型与完整新证据 / R3

这不是一份“已完成的比赛最优解”。它是以冻结官方评估器为裁判的独立研发交付，重点为：

**串行包上的小型 max-plus 响应 → 联合分核 → 固定核心归属后分阶段细化；P1 则补充覆盖边合并与出口保护。**

主要进展：`case_002`、Q2、四核，已有三个探测构造的最好值 111212 → 串行包矩阵 71904 → 固定归属窗口细化 66376 cycles。最后一步的五项搬运统计完全不变，均无 SPILL。该结果在随包重新解压的官方环境中完整 JSON 复跑一致。

边界同样重要：Q2 的 `case_044` 中，固定归属窗口细化可以从 74838 变为 105715；新两个基础构造在预列的八例验证组上是四改善、两相等、两退化，不能丢掉已有合法方案。

## 入口

- `RESEARCH_MEMO.md`：数学对象、推导、算法、证伪与下一步。
- `EVIDENCE_INDEX.md`：材料实读范围、GitHub固定提交、旧缺口、实验身份和失败记录。
- `analysis/RESULTS.md`：完整主实验表；`analysis/*.json` 为机器可读分析。
- `src/packet_construct.py`：结构包与3×3计算响应、分核、重入细化。
- `src/window_refine.py`：固定归属的参考拓扑窗口细化。窗口**不是**物理并发上限。
- `src/cover_fusion.py`：P1覆盖关系合并，含出口保护。
- `src/solve.py`：有限候选＋原样官方CLI确认；无LLM、无E2盲筛、无服务。
- `results/`：本轮原始方案、完整E0/E1结果、E2估计、元数据和日志。
- `dependencies/`：官方完整原ZIP、题面、此次DELTA与说明原件，未改字节。
- `prior/`：旧295份缺失记录的上轮索引，**不是找回的结果**。

## 本地复跑

本轮测试为 Linux/x86-64、Python 3.13.5、CPU。新算法只依赖标准库和随包官方代码；没有运行CUDA、Metal、Rust或C++。其他平台需独立复核。

先核验本包，再仅在本目录内解压依赖：

```sh
python VERIFY.py
python PREPARE.py
```

PREPARE不联网，不写仓库，不覆盖字节不同的文件。它将原件解压到 `vendor/team/data/raw/a/official`，按新source-manifest核对114文件、100案例及代码集合hash。

复跑一个已存档完整E0结果（新目录必须不存在）：

```sh
python REPLAY.py --out local_replay/case002
python REPLAY.py --run results/mechanism_probes/export_cover_fused_q1 --out local_replay/export
```

生成新的方案并由**原样官方CLI**生成结果、Trace、日志：

```sh
python src/solve.py vendor/team/data/raw/a/official/data/case_002.json \
  --official vendor/team/data/raw/a/official --problem 2 --cores 4 \
  --budget-seconds 300 --portfolio augment --with-window \
  --output-dir local_runs/case002_q2
```

`--portfolio legacy3` 为已有component/cut2/unit三个探测构造，`augment` 保留它们并增加少量结构候选；`--with-window` 再增加一个固定factor=8的候选。候选相同会去重，所有新候选的官方CLI成本计入。`run.json` 在方案外记录预算、选择、失败和重复；最终方案本身仍只有两个官方字段。结果和Trace整份复制自同一次获胜E0执行，不混拼。

**预算边界：**E0子进程可按剩余时间终止，构造器目前在候选之间检查时间，尚不是硬实时截止证明。若没有任何E0确认的合法方案，退出非零，不假报成功。只支持冻结配置，不偷偷重写配置。大图最坏耗时、全部100例、完整核数矩阵仍未验收。

已测完整CLI（单次，不是性能统计）：

|输入与模式|E0确认结果|完整墙钟|
|---|---:|---:|
|case002 Q2四核 legacy3|111212|2.985s|
|case002 Q2四核 augment|71108|8.287s|
|case002 Q2四核 augment+window|66376|8.948s|
|case026 Q2四核 augment|28637，保留旧cut2|7.693s|

上述均给30秒预算；候选数不同，不把结果归因于“相同评估次数下的纯算法优势”。

## 证据口径

- 293次主构造E0函数调用，覆盖15个正式case，均保存完整结果；这些是调用数，不是293个独立case或独立方案。
- 13次机制微图E0调用。
- 40次有效P1 E0/E1/E2成对诊断记录，按原始方案hash去重为37份；E1完整对象均相同。另有重复计时与包装器故障的原始产物，不能混为独立测试样本。
- 300个数学检查图，2400次响应核对、600次链/重入商图核对、1785次覆盖合并核对。只验证对应子模型，不是E0全域等价。
- 当前E1仅P1热点改写；本轮三例重复API计时1.85×/1.27×/1.48×，未到3×发布门槛。E2在新池仍明显偏差；没有用其点估计剔除主算法候选。
- 295份历史完整结果仍缺失；新增64份团队E0真值和本轮新结果均有独立身份。

`MANIFEST.json`覆盖原包payload，不覆盖PREPARE产生的vendor和用户后来新跑的目录。原始运行记录中的绝对沙箱路径是来源记录；复跑用上面的相对入口，不依赖该沙箱存在。
