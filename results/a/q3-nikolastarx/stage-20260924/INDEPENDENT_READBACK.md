# Stage 三格独立证据回读

审计 UTC：2026-09-24T15:42:24.634397+00:00；审计者 root/q3_cache_feedback，与构造/执行分开。新增 E0/E1/E2 = 0，未运行 solver，未改既有证据，未提交。

执行源码 `b525f9116fa8ce203b5aee3b4206f69768445b36` 与本工作树 HEAD、feed solver/evaluator/runner SHA 一致。旧同图四核对照及官方单核分母来自 `ba99b74b523f93a4002cd88970ec7164076d8008`。逐字节核对 35 个源文件/输入快照；按 source-manifest 规则重算 10 个官方代码文件的组合哈希，得到 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，与 feed/batch 一致。17 个不同 feed 原件引用全部匹配；旧 result、旧 plan/receipt 及分母逐个 git show 固定原件校验。新 plan/result 与 receipt、seed 原件一致。

## 原计算与时序

| case | 阶段 | 旧四核 | 新四核 | 下降 | L500 | 官方减 L500 | solver wall(s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 051 | 24 | 607628 | 178800 | 70.5741% | 176284 | 2516 | 0.178830834 |
| 024 | 101 | 2555343 | 746444 | 70.7889% | 743466 | 2978 | 0.710989750 |
| 016 | 305 | 7715523 | 2250332 | 70.8337% | 2246130 | 4202 | 3.335013500 |

完整新/旧 JSON 均逐个检查原计算 op：每个恰一次，op/pipe/cycles 保持原图值；新 owner 与时间线 core 一致，同 PIPE_V 区间不重叠。原算子总工作为 607080 / 2554795 / 7714975，全部属于 PIPE_V。旧 affine_eighth 将整个弱连通分量放 core0，新计划每核 1 Task，把同样工作分摊到 4 核，没有改变工作量。

| case | 核 | 原计算数量 | 原计算 work | 首 start | 末 end | 含启动 idle=end−work | tail |
|---|---:|---:|---:|---:|---:|---:|---:|
| 051 | 0 | 480 | 153408 | 2188 | 178799 | 25391 | 1 |
| 051 | 1 | 312 | 151224 | 2188 | 178230 | 27006 | 570 |
| 051 | 2 | 312 | 151224 | 2188 | 178231 | 27007 | 569 |
| 051 | 3 | 312 | 151224 | 2188 | 178232 | 27008 | 568 |
| 024 | 0 | 2020 | 645592 | 2188 | 746443 | 100851 | 1 |
| 024 | 1 | 1313 | 636401 | 2188 | 745874 | 109473 | 570 |
| 024 | 2 | 1313 | 636401 | 2188 | 745875 | 109474 | 569 |
| 024 | 3 | 1313 | 636401 | 2188 | 745876 | 109475 | 568 |
| 016 | 0 | 6100 | 1949560 | 2188 | 2250331 | 300771 | 1 |
| 016 | 1 | 3965 | 1921805 | 2188 | 2249762 | 327957 | 570 |
| 016 | 2 | 3965 | 1921805 | 2188 | 2249763 | 327958 | 569 |
| 016 | 3 | 3965 | 1921805 | 2188 | 2249764 | 327959 | 568 |

每行 work+idle+tail 等于该图 Makespan。idle 是原 PIPE_V 的空档，不意味着已经逐个归因到唯一前驱。core0 完成最终归约，最后 1 cycle 是结果 COPY_OUT。每阶段 core0 原计算 6392 cycles，其他核各 6301，合计 25295。

所有阶段根 end 已逐个回读：第一阶段根完成 9243，后续相邻阶段根完成差恰为 7372，末尾 COPY_OUT 1 cycle。三份轨迹因此均满足 C(n)=7372n+1872。现存静态产物 L500(n)=7366n−500，残差=6n+2372。这是 n=24/101/305 的完整轨迹观测，不宣称任意 n 的通式已获证明。下界只回读核对，未重跑 pipe_bound，亦不是所有合法计划最优值。

## COPY 与 Cache 按字节复算

| case | transfer数 | 新增COPY(B) | hit(B) | miss(B) | 字节命中率 |
|---|---:|---:|---:|---:|---:|
| 051 | 213 | 852 | 92 | 393550 | 0.02337149% |
| 024 | 906 | 3624 | 400 | 394628 | 0.10125864% |
| 016 | 2742 | 10968 | 1216 | 397484 | 0.30499122% |

已由全部 cache_events 独立加总 size_bytes，复算 hit/(hit+miss)，与 cache_stats、receipt、feed 一致，没有混用命中次数比例。全部跨核 tensor 为 2 B：每个非 collector 核每阶段向 core0 送 2 条，共 6n gather；core0 向 3 核每个后继阶段各发 1 条，共 3(n−1) broadcast。transfer=9n−3；每条官方包含 2 B COPY_OUT 与 2 B COPY_IN，新增搬运=4(9n−3)=36n−12 B，准确得到 852/3624/10968。原图 COPY 固定 393218 B；scheduled=原图COPY+新增COPY；三格 spill=0。这是调度字节，不冒称物理 DDR 流量。

逐条核对 copy_in_release=copy_out_end+500、copy_in_start≥release；Cache hit 没有取消该释放约束。每个 broadcast 后两次读取 hit，共 hit_bytes=4(n−1)。各图只有 12 次 32768 B 大输入导入，均 miss，每个 immutable input 只导入一次。官方 memory_peak_by_core 均为 L1 每核 98304 B，UB 依次 65540/65538/65540/65538 B，不随阶段数增加；这是官方准备阶段峰值字段，未冒称最终多核轨迹重建峰值。

证据支持主要收益来自计算分摊与输入驻留复用；没有同计划 P2 无 Cache 对照，不能量化 CacheGain。剩余等待与逐阶段 gather/broadcast 释放吻合，但没有消融或逐边归因全部 idle。此处仅三图四核，不扩张为全100图/1–5核提升、独立平台验收或一般最优性。

## 精确来源指纹

以下 SHA 对原存储字节计算；result 为 gzip 原字节，未重新压缩。其余 receipt/run/manifest 路径和 SHA 见 [完整 feed](board-feed-20260924T1531Z-complete.json)。

### 051

- graph_sha256: `884e8b12ac1f7a9b569958909680e8c2f6055966a59c9f929ffd5cee48aae43b`
- new_plan_sha256: `dd52351c11cd448c7a062ce5614093d7592a98f55bfa53fe696b32e1f2249c89`
- new_result_sha256: `1ad4b8333d46bbf21801e40e1e6c15688e9fcce6e0fa7b7e31d628ebcff7e846`
- old_plan_sha256: `49c587469320b7624621398c651e4b8463ae1869b2e185f9f8e9867ccb4ee70c`
- old_result_sha256: `a9485ddc48e98ed2908f4b91c863938f895e9d5494587fc57f741b3c29b221d6`
- baseline_sha256: `9c62a3dec13b1628b296c4847691f252e716a475677f807c80b0b06ef5c58c3f`
### 024

- graph_sha256: `f974fbf1a23b4a145b5f8c9c691eb1b247f93d8785d98bb46a9cdd8626399aec`
- new_plan_sha256: `379fceab38141acf66275655346306045cdfe833d6ddf3c98034a0a625f9fc5f`
- new_result_sha256: `2836ba85ca9ed9f62d835e149e7182ed659cbb3abf4184256f8f7bdb005930ac`
- old_plan_sha256: `6aaf6ae4786cadae07a4bfa37a8e05294adf0b552971f324bf351f7956d39455`
- old_result_sha256: `0a2efe26a59b893bc1c43a6ed13b2bc5a67abe29751a81be8820aaeb64fa2404`
- baseline_sha256: `0b8f7446004cce0a19cb2356e5d138e09d498a3464446051414dee3196e60af8`
### 016

- graph_sha256: `76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef`
- new_plan_sha256: `68f25a6d2e077fb0312f98870601f03b8fe2932ccf967beac00e9d0ea76ba9cf`
- new_result_sha256: `3fe8706ec0a606b7606104b9b2d842772b7f94aa071a02ecdc4fb456904ce018`
- old_plan_sha256: `234ddbd612672f135d375fd6df9eaf2a69b7f5856605c369ce69837ad9296be8`
- old_result_sha256: `2eef2cbae57486fb5ae3b7a68512f00c0418672c6f87f7643dcb1865311171ac`
- baseline_sha256: `a161e763c0166f60b6f890528a96bcea8284bee60a13d3116b04cf5e0260bb55`

config SHA256：`dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。feed SHA256：`d95802ec8c2a9ac790fd7eee68bda7e529daa392857846a19cfaa26584167500`。

## 成绩台零评分预检

入口核对自执行版本 tests/q3/test_board_export.py::test_against_available_shared_submission_protocol 与主项目统一交付协议。调用共享 protocol.py，不用合成测试夹具代替真实三格：

```sh
python3 /Users/nikolastar/Projects/huaweicup2026/src/benchmark_board/protocol.py results/a/q3-nikolastarx/stage-20260924/board-feed-20260924T1531Z-complete.json --repo . --submission
```

实际 cwd 为此执行工作树根。共享工具所在主项目 HEAD `c22708c5ae52a6046bbb252853d5884464b8420e`；protocol.py 字节 SHA256 `0fd859db6ab64790ba4979eaffb36789197378df11c53a02454daae7f4236a51`。退出码 0，原样 stdout 见 [preflight.json](preflight.json)：

```json
{
  "eligible": 3,
  "records": 3,
  "reported_or_failed": [],
  "scope": "format and available bytes only; no solver/evaluator execution or production write",
  "submission": true,
  "valid": true
}
```

预检只在系统临时目录校验格式和现存字节，不写中央库、不联网、不执行 solver/evaluator。eligible=3 表示本地证据准入，不是已推送、中央已收、网页已显示或独立复跑。执行证据共有 3 次 E0，每格 evaluations.json 1 条，未见评分重试；本审计核对文件一致性，不从文件代签真实进程执行过程。

只新增本报告和 preflight.json；审计前后原有 48 个文件 SHA 全部保持一致。
