# P2 direct structural pilot: fixed development cells

Solver `a6f09c585392573ce32b89f31011f436f6af70ef`; runner `e15111b836bc8c6e9f33e658296b71653450c2f2`.

Execution UTC 2026-09-24T15:51:16.631804Z to 2026-09-24T15:51:33.134449Z; matrix wall 16.501950750 s.

3 solver calls and 3 separate final official E0 calls succeeded. Online E0/E1/E2=0; scoring failures/retries=0. Verification adds zero solver or evaluator calls.

0-score preflight typo corrected: a plan-only precheck initially named a nonexistent SHA; no solver or E0 ran before the corrected plan/run. This note comes from the parent execution report, separate from per-cell scoring receipts.

| Case | k | Old Makespan | New Makespan | Change (cycles) | Reduction | DDR B | Extra DDR B | Spill B | Solver s | Final E0 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 062 | 2 | 2262944 | 1514488 | -748456 | 33.0744% | 13407744 | 6144 | 0 | 0.764416 | 4.701996 |
| 062 | 4 | 1607053 | 1008337 | -598716 | 37.2555% | 13426176 | 24576 | 0 | 0.744486 | 3.740051 |
| 062 | 5 | 1391629 | 673563 | -718066 | 51.5990% | 13444608 | 43008 | 0 | 0.926183 | 3.244201 |

Paired quality versus frozen direct pilot: {'win': 3, 'tie': 0, 'loss': 0}. All cells, including regressions, are retained. Old feed/result/run are read from Git data `81219bf923524fb60616e39b5ad2dced67aec3e2`; same case/core/graph/config/official identities were checked. No old solver was rerun.

Observed zero spill describes these final official results only; it does not prove the priority-interval certificates sufficient in general. DDR/extra/spill byte reductions do not imply a Makespan improvement. Algorithm detail fields are preserved in original solver.json and not generalized by this exporter.

These are selected development cells, not held-out or full-100 performance. The frozen Fang/history reference is timestamped in summary.json; history is a mix of winners, not one solver. All old/new byte and wall differences are available in metrics.csv. Shared-machine wall times include launch, input, construction, output and observation/cleanup; final E0 time is separate. Timing differences do not establish causal speedup.

All 42 per-cell manifest entries and 6 lossless compressed JSON round-trips verified; all original files unchanged. Process receipts have exit0/no survivors, and all 6 owned PIDs are absent at verification. Each feed and aggregate pass local producer precheck; central admission and scientific acceptance remain separate.

The original final/official.log files are Git-ignored and require explicit inclusion by the parent publisher. Raw stdout is unchanged except any runner-recorded redaction in archive.json. No Git mutation, central import or mirror synchronization was done by this exporter.
