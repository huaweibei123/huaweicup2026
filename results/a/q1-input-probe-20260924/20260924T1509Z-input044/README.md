# External-input windows: 044 four-core probe

Both scheme quality and solver runtime below are actual observations on the frozen official E0; this is a selected development probe, not a complete100-case method score.

Solver `d438d380326d9cfa3d38097f5ab60d35aa6e5df4`; runner `8ec63555b60ebae8a71b1f2e9ec302e459548495`. Actual UTC 2026-09-24T15:06:59.946Z–2026-09-24T15:07:00.216Z. The1509Z text in the preallocated run ID is a label, not the actual start time.

| Case/k | New Makespan | bounded04 | fixed64 | Official singlecore | Solver wall(s) | External E0(s) | extra DDR(bytes) | spill(bytes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 044/4 | 76519 | 124268 | 131407 | 154407 | 0.077290916 | 0.178907916 | 2912288 | 0 |

Reference results are exact reused originals: bounded04 from `ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9`, fixed64 and official singlecore from `6664a63adc3464d28d1f835d907cdeaea23e6b35`. The exporter verifies their stored-byte hashes and feed/result Makespan equality. No reference was evaluated again.

The candidate emits5 depth windows/20 Tasks, preserving core assignment. Official Makespan drops38.42% from bounded04. Extra DDR changes5678624→2912288 bytes and spill2887424→0; new partition-added bytes2912288 exceed the old2791200. Thus the actual E0 improvement includes a measured spill/boundary tradeoff, not a zero-cost window split.

The earlier profile-refine044 result114443 is also preserved and hash-checked from `8c8ba37b8db770c490423a88061a696e15cc445b`;76519 is33.14% lower. This is a same-cell comparison across two algorithms, not a revised full100 score or a rerun of the historical method. See `historical-profile-comparison.json`.

This supports the fixed input-window candidate for044. The external-input union threshold is not a capacity certificate; no guarantee follows for other graphs, configurations or numbers of cores. The frozen400-cell bounded04 batch remains a distinct algorithm experiment.

Budget and actual calls: {'solver': 1, 'E0': 1, 'E1': 0, 'E2': 0}; one worker; no retry, E1/E2, GPU or Colab. Each solver includes one complete inherited bounded04 construction and all wrapper/I/O/structural validation costs. Independent external E0 wall is not part of solver wall. Compression, export and precheck happen afterwards.

Resource window: parent received a temporary scoring pause from P3; P2 allowed at most1 worker, and the independent400-cell P1 batch allowed2 workers. These probes run sequentially, never simultaneously. Parent was notified immediately after all three cells finished so P3 could resume. Dispatch resource snapshots record a reclaimable-memory proxy above4GiB; peak RSS was not measured. Fresh interpreter per cell; OS file cache not flushed; host not exclusive; no controlled cross-machine runtime ratio.

Producer precheck: board-submission-v1 valid; eligible1/1, not a central-ledger receipt or independent rerun. See `precheck.json`, `verification.json`, `comparison.json`, `board-feed.json`, complete `cells/` and `references/`.

Reproduction uses the frozen runner and a NEW run ID; do not reuse this directory (the runner refuses). Any rerun requires a separate experimental authorization/budget. Export of these existing bytes is zero scoring:

```sh
uv run python -B src/q1_benchmarks/input_probe_e0.py export 20260924T1509Z-input044
```

Fixed Git-byte precheck also passed at `430f2ff73b450589314f9b43f0b8b163b0a04e06`; all plan/result/run/log/baseline references are in that commit. `git-precheck.json` is the read-only receipt. Official logs are explicitly tracked despite the repository log-ignore rule.
