# P2 direct structural pilot: fixed development cells

Solver `e76ddc4c36374fb54d585be622bdf71dbde0fdb9`; runner `718bea935ed7b8afd71f3ae6e4422724f68f31f3`.

Execution UTC 2026-09-24T15:52:26.534023Z to 2026-09-24T15:52:43.334816Z; matrix wall 16.800049792 s.

3 solver calls and 3 separate final official E0 calls succeeded. Online E0/E1/E2=0; scoring failures/retries=0. Verification adds zero solver or evaluator calls.

No preflight issue reported. This note comes from the parent execution report, separate from per-cell scoring receipts.

| Case | k | Old Makespan | New Makespan | Change (cycles) | Reduction | DDR B | Extra DDR B | Spill B | Solver s | Final E0 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 016 | 2 | 9260226 | 4170750 | -5089476 | 54.9606% | 398094 | 4876 | 0 | 0.791484 | 4.143343 |
| 016 | 4 | 2250687 | 2552270 | +301583 | -13.3996% | 405406 | 12188 | 0 | 0.575939 | 4.014564 |
| 016 | 5 | 2240622 | 2243707 | +3085 | -0.1377% | 405402 | 12184 | 0 | 0.577217 | 3.884824 |

Paired quality versus frozen direct pilot: {'win': 1, 'tie': 0, 'loss': 2}. All cells, including regressions, are retained. Old feed/result/run are read from Git data `81219bf923524fb60616e39b5ad2dced67aec3e2`; same case/core/graph/config/official identities were checked. No old solver was rerun.

Observed zero spill describes these final official results only; it does not prove the priority-interval certificates sufficient in general. DDR/extra/spill byte reductions do not imply a Makespan improvement. Algorithm detail fields are preserved in original solver.json and not generalized by this exporter.

These are selected development cells, not held-out or full-100 performance. The frozen Fang/history reference is timestamped in summary.json; history is a mix of winners, not one solver. All old/new byte and wall differences are available in metrics.csv. Shared-machine wall times include launch, input, construction, output and observation/cleanup; final E0 time is separate. Timing differences do not establish causal speedup.

All 42 per-cell manifest entries and 6 lossless compressed JSON round-trips verified; all original files unchanged. Process receipts have exit0/no survivors, and all 6 owned PIDs are absent at verification. Each feed and aggregate pass local producer precheck; central admission and scientific acceptance remain separate.

The original final/official.log files are Git-ignored and require explicit inclusion by the parent publisher. Raw stdout is unchanged except any runner-recorded redaction in archive.json. No Git mutation, central import or mirror synchronization was done by this exporter.
