# P2 2–5核，100图完整原件

固定算法 `0b58c123cccf02fc993b741d79dcd8511e4dd38f` 的 `src/q2/construct.py`；每格一次确定性构造和一次冻结官方 P2 E0 CLI。100图×4核共400格，全部成功；400次solver、400次E0、0次E1/E2、0重试。首12格（001/002/044×2–5核）4 worker成功后，其余388格8 worker完成。T0=`2026-09-24T13:25:27.866Z`，最后一格=`13:27:02.591Z`。平台Apple M5 Pro/macOS/CPython 3.12.13/48GiB；求解外层wall中位0.279秒、最大0.838秒，E0外层wall中位0.551秒、最大8.337秒。E0子进程采样最大RSS565.1MiB；采样不是总批精确峰值或硬内存限制。完整命令、每格耗时、失败字段及身份见各 `cells/<case>/k<k>/run.json` 与 `batch.json`。

`board-feed-first12.json`是首批固定快照；`board-feed-full400.json`含全部400条及已复用官方单核分母。两者重叠的12个attempt/revision内容相同，接收时可只导入完整feed。每格保存方案、官方原始结果与Trace的无损gzip、官方log、运行收据；`result.json.gz`是官方CLI完整result的原字节gzip，不是推导的CSV数字。

预检：

```sh
python3 src/benchmark_board/protocol.py results/a/local-p2-multicore-20260924/20260924T1325Z-s59ee/board-feed-full400.json --submission
```

实际工作树检查返回`valid:true,records:400,eligible:400,reported_or_failed:[]`。这是交付协议、冻结身份和原件检查，不是独立复跑或算法优越性验收。复现需新建批次目录、固定solver干净工作树和不同attempt身份；本完成目录不得重跑。
