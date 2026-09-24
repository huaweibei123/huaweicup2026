# Separate diagnostic of four external E0 timeouts

Solver `05f8fa0f7e52f5914f14815f6bdbcb851b631556`; runner `0f091cbd9457ebe66d15510a6be5f44dcf2fd579`. Original matrix `d63001eb01cc254a20bc60cae5e50b1eb1ee2808` is unchanged.

UTC 2026-09-24T15:22:34.853Z to 2026-09-24T15:26:32.071Z, batch wall 242.338s; calls `{'solver': 4, 'E0': 4, 'E1': 0, 'E2': 0}`, status `{'ok': 4}`. Batch wall also includes preflight validation before the recorded batch started_at.

Budget: one worker, at most four new constructors and four new E0 calls, constructor30s/E0180s/batch1200s; stop at first new failure, no additional round. Reconstructed plan must exactly match old failed-plan SHA before E0.

| Case/core | Status | Same plan bytes | Makespan cycles | Constructor seconds | External E0 seconds |
| --- | --- | --- | --- | --- | --- |
| 041/k5 | ok | True | 1196379 | 0.25131658400641754 | 59.05002345799585 |
| 062/k1 | ok | True | 2854809 | 0.437258624995593 | 42.475883917009924 |
| 079/k5 | ok | True | 6075976 | 0.3048129999951925 | 66.33977458300069 |
| 087/k5 | ok | True | 886373 | 0.7790404159750324 | 66.3568066659791 |

Keep original 496 successes; fill only old E0-timeout slots using successful new attempts from the four-cell predeclared diagnostic with exactly equal plan SHA. No best-of scores. Old original 496/500 table and all four failed attempts remain unchanged.

| Cores | Valid / requested | Mean singlecore / Makespan |
| --- | --- | --- |
| 1 | 100/100 | 1.002096822 |
| 2 | 100/100 | 1.747291878 |
| 3 | 100/100 | 2.388778144 |
| 4 | 100/100 | 2.949082318 |
| 5 | 100/100 | 3.440854034 |

Different run and new attempts with a broader external E0 window and fewer workers. Does not establish concurrency caused original timeouts. Solver output must be byte-identical to original failed attempt before E0.

Prior two-worker 400-cell batch is finished. This diagnostic uses one worker; P2 and P3 may each use at most one shared external worker. No exclusive host claim, cloud or GPU.

Original k4 used one worker; original 400 used two; this diagnostic uses one with longer E0 cap. Keep times by actual run; do not infer a controlled speedup or cause of old timeout.

Against same-core fixed64, k1 has 25 regressions; k2/k3/k4 have none; k5 has 1. All negative cases and 54 adjacent-core regressions are retained in `quality-regressions.json` and the full comparison. Full coverage is not dominance over every comparator. No cross-core fallback was applied; adjacent regressions do not prove worse core-budget optima.

`board-feed.json` contains only new diagnostic attempts. `full500-filled-*` is a declared follow-up evidence view; `full500-comparison.json` in the original matrix directory retains the first-pass missing scores. Fixed-method cumulative calls: `{'solver': 504, 'E0': 504, 'E1': 0, 'E2': 0}`, including all original failures; no baseline rerun.

Original fixed64/singlecore evidence remains inherited in this commit. `PRECHECK.json` is the read-only v1 precheck; fixed Git artifact hashes are checked separately after commit with `src/q1_benchmarks/bounded_matrix_verify.py`. No central ledger write or publication by this agent.
