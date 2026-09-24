# P1 bounded-task matrix: 400 new attempts, preserved 100 k4 attempts

Algorithm `q1-bounded-component-tasks` / `frontier-then-independent-chunks` at `05f8fa0f7e52f5914f14815f6bdbcb851b631556`; packet_factor=4, trigger_ops=4096, chunk_ops=1024.

Frozen runner `8163b2a3464ed19b04cac3c2a280a9350367ca89`, `src/q1_benchmarks/bounded_matrix_e0.py` and manifest `src/q1_benchmarks/bounded_matrix_batch.json`. Read-only exporter `src/q1_benchmarks/bounded_matrix_report.py` reuses schema constants from same-method fixed commit `ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9`.

New batch UTC 2026-09-24T14:59:28.047Z to 2026-09-24T15:16:09.987Z; 1002.189 seconds controller wall (including preparation, source/resource checks, compression). Actual calls: `{'solver': 400, 'E0': 400, 'E1': 0, 'E2': 0}`. Status: `complete_with_candidate_failures`. No retry, E1, E2, cloud or GPU.

Budget: 400 constructors + 400 external E0 maximum, at most 2 active cells, 30 seconds per constructor, 60 seconds per E0, 1800 seconds whole batch. Candidate child failures/timeouts continue only after cleanup; source/hash/cleanup/disk/runner/resource failures stop dispatch. Four synthetic controller jobs validated a peak of two workers and candidate-failure continuation before freeze; a resource-failure fixture dispatched zero jobs. No solver/E0 was used for controller checks.

## Coverage and official quality

All 500 matrix slots are represented, with statuses `{'ok': 496, 'timeout': 4}`. A missing/failed score is not zero and is excluded from means; partial-core means do not claim a 100-case score. The 100 k4 records preserve their actual earlier attempts and do not appear in this batch's feed or new call count.

| Cores | Successful / requested | Mean official singlecore / Makespan | Fixed64 mean on same successful cases | Better / equal / worse vs fixed64 |
| --- | --- | --- | --- | --- |
| 1 | 99/100 | 1.002118002 | 0.948629257 | 75 / 0 / 24 |
| 2 | 100/100 | 1.747291878 | 1.041762070 | 100 / 0 / 0 |
| 3 | 100/100 | 2.388778144 | 1.073106715 | 100 / 0 / 0 |
| 4 | 100/100 | 2.949082318 | 1.088051407 | 100 / 0 / 0 |
| 5 | 97/100 | 3.396626621 | 1.073116627 | 96 / 0 / 1 |

Makespan is simulated cycles; solver and external E0 durations are seconds. Mean speedup is the arithmetic mean of per-case ratios. Complete original E0 movement fields, plan, result, run and optional diagnostics/trace/log are retained.

## Observed program time and resources

| Cores | Solver median / maximum seconds | External E0 total / maximum seconds |
| --- | --- | --- |
| 1 | 0.105223 / 0.896361 | 360.207 / 60.025 |
| 2 | 0.088126 / 0.881615 | 403.239 / 38.188 |
| 3 | 0.081286 / 0.891701 | 467.484 / 59.220 |
| 4 | 0.077456 / 0.836849 | 418.541 / 53.037 |
| 5 | 0.080750 / 1.030654 | 661.550 / 60.022 |

Fresh interpreter per cell, OS cache not flushed. Solver wall includes input read, construction, plan/diagnostic publication and process completion; external E0 wall includes official result/trace/log output and exit. Compression/export is outside both child timers. k4 used earlier one-worker runs; new cores use two shared workers. These are descriptive cross-case observations, not controlled timing speedups or repeated latency percentiles.

Host `Apple M5 Pro`, `macOS-27.0-arm64-arm-64bit`, Python 3.12.13, locked dependencies. Resource observations: `{'configured_worker_cap': 2, 'cell_interval_peak_overlap': 2, 'dispatch_samples': 400, 'minimum_available_memory_estimate_bytes': 12552077312, 'maximum_other_busy_project_processes_sampled': 2, 'memory_definition': 'vm_stat (free + inactive + speculative) pages; approximate host availability, not per-child peak RSS', 'load_definition': "ps CPU >=25 percent project processes excluding controller and this batch's children; dispatch-time samples, not continuous profiling"}`. No per-process peak RSS or phase sampling; no inference of evaluator bottleneck from a timeout.

P2 currently idle, later at most one worker; P3 currently idle, later one worker for a short small batch; both explicitly permit this two-worker shared-host batch. Pause dispatch on obvious memory pressure or excess other project load; never kill another session's process.

## Failures and research feedback

New unsuccessful cells: `[{'case': '041', 'cores': 5, 'status': 'timeout'}, {'case': '062', 'cores': 1, 'status': 'timeout'}, {'case': '079', 'cores': 5, 'status': 'timeout'}, {'case': '087', 'cores': 5, 'status': 'timeout'}]`. See `failed-cells.json` for exact costs, cleanup and retained file hashes. No retry or raised timeout.

There are 54 adjacent-core regressions among successful pairs for this fixed constructor. `full500-summary.json` lists them. They concern this constructor's outputs, not the optimum of the feasible core-budget problem. No online best-of selection was performed.

This is the public development set used for feedback, not blind independent acceptance or an optimality claim. The unbounded full4 batch's stop remains unchanged; this is a distinct bounded-task algorithm and separately authorized batch.

## Evidence and reproduction

- `board-feed.json` (or automatically numbered shards if >8 MiB) contains only these 400 attempts; `feed-manifest.json` lists exact hashes.
- `full500-comparison.json`/CSV and `full500-summary.json` combine the fixed method across actual runs, without changing earlier attempts.
- k4 source `ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9`: `results/a/q1-bounded-full4-20260924/20260924T1439Z-boundedfull4-99/full100-comparison.json`; original 014 source `4d374dc25b5698491ddbb92837789a23a4ad3102` is already preserved under the k4 source directory.
- Frozen official singlecore/fixed64 source `6664a63adc3464d28d1f835d907cdeaea23e6b35` reused without calls. `references/` holds baseline original bytes and historical records.
- Read-only export: `python -B src/q1_benchmarks/bounded_matrix_report.py 20260924T1459Z-bounded400`.
- `PRECHECK.json` stores the board-submission-v1 working-tree precheck. Fixed-commit precheck and every recursively referenced feed/run artifact are separately verified after commit; no central ledger writes.
- `PRECHECK_EARLY.json` preserves a read-only precheck attempted before export finished (feed did not yet exist); after export completed, the actual precheck was rerun without solver/E0 calls.
- The controller refuses existing run directories. Do not rerun this batch to repair export or metadata; export only reads preserved evidence.
