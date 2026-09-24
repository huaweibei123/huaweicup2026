# Sink-exclusive suffix waves: 048/071 four-core probe

Both scheme quality and solver runtime below are actual observations on the frozen official E0; this is a selected development probe, not a complete100-case method score.

Solver `d89a6cbf1e292f2abc36b4fef89590d16ccb1ab2`; runner `52639f1a9975f8cb1fb696f79ad21bd8947f1e19`. Actual UTC 2026-09-24T15:06:49.325Z–2026-09-24T15:06:49.915Z. The1509Z text in the preallocated run ID is a label, not the actual start time.

| Case/k | New Makespan | bounded04 | fixed64 | Official singlecore | Solver wall(s) | External E0(s) | extra DDR(bytes) | spill(bytes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 048/4 | 116460 | 222220 | 226990 | 222220 | 0.128519709 | 0.239610833 | 730594 | 0 |
| 071/4 | 12078 | 18919 | 21586 | 18919 | 0.073576000 | 0.120555625 | 239546 | 0 |

Reference results are exact reused originals: bounded04 from `ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9`, fixed64 and official singlecore from `6664a63adc3464d28d1f835d907cdeaea23e6b35`. The exporter verifies their stored-byte hashes and feed/result Makespan equality. No reference was evaluated again.

048 emits20 waves/68 Tasks and reduces Makespan47.59% from bounded04;071 emits4 waves/16 Tasks and reduces Makespan36.16%. Both baseline plans had zero extra DDR and zero spill. The new plans add730594 and239546 bytes respectively but still finish sooner. This directly rules out treating zero extra DDR as a sufficient quality objective.

The result supports this complete coarse suffix construction on the two selected inputs. It does not isolate gates as the sole cause: partition boundaries, load distribution, FIFO order, memory schedules and release times all change. No monotonic theorem, globally optimal claim or unseen-case guarantee follows.

For context only, parent-provided Fang chain-wave reports were362034/43499 cycles, with report source `b73c4bfcb8a0629550fdbdf3f8b4f3631e8cbc77` (PR110). They were not rerun in this batch and are not used as the official singlecore denominator.

Budget and actual calls: {'solver': 2, 'E0': 2, 'E1': 0, 'E2': 0}; one worker; no retry, E1/E2, GPU or Colab. Each solver includes one complete inherited bounded04 construction and all wrapper/I/O/structural validation costs. Independent external E0 wall is not part of solver wall. Compression, export and precheck happen afterwards.

Resource window: parent received a temporary scoring pause from P3; P2 allowed at most1 worker, and the independent400-cell P1 batch allowed2 workers. These probes run sequentially, never simultaneously. Parent was notified immediately after all three cells finished so P3 could resume. Dispatch resource snapshots record a reclaimable-memory proxy above4GiB; peak RSS was not measured. Fresh interpreter per cell; OS file cache not flushed; host not exclusive; no controlled cross-machine runtime ratio.

Producer precheck: board-submission-v1 valid; eligible2/2, not a central-ledger receipt or independent rerun. See `precheck.json`, `verification.json`, `comparison.json`, `board-feed.json`, complete `cells/` and `references/`.

Reproduction uses the frozen runner and a NEW run ID; do not reuse this directory (the runner refuses). Any rerun requires a separate experimental authorization/budget. Export of these existing bytes is zero scoring:

```sh
uv run python -B src/q1_benchmarks/sink_probe_e0.py export 20260924T1509Z-sink2
```

Fixed Git-byte precheck also passed at `232b6eccee580053856b67f9edc22eb71d014698`; all plan/result/run/log/baseline references are in that commit. `git-precheck.json` is the read-only receipt. Official logs are explicitly tracked despite the repository log-ignore rule.
