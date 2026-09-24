# Component-envelope P2 pilot: six fixed cells

Source `919c82370a42eca9fcff444bef4c1e1e3ea78282`; runner `aa714b3811fa3722e5e126be12268917af0da93f`.

UTC 2026-09-24T15:22:29.614307Z to 2026-09-24T15:23:25.003957Z; execution batch wall 55.388923917 s.

All six solver and final E0 calls succeeded. Zero online E0; six external E0; E1/E2=0; zero retries, failures or replacement. All 12 owned child PIDs had exited when checked.

| Case | k | Old Makespan | New Makespan | Reduction | Old spill B | New spill B | Old extra DDR B | New extra DDR B | Solver s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 014 | 2 | 13097894 | 8869498 | 32.28% | 200693760 | 40607328 | 352177120 | 50500536 | 1.225271 |
| 014 | 4 | 8292269 | 4510101 | 45.61% | 137943552 | 29287824 | 364308140 | 58916760 | 1.213502 |
| 014 | 5 | 7364271 | 3666823 | 50.21% | 144884736 | 28088664 | 383256184 | 63322632 | 1.185783 |
| 025 | 2 | 4251120 | 2351860 | 44.68% | 100832256 | 0 | 100859904 | 27648 | 0.657650 |
| 025 | 4 | 2585433 | 1177396 | 54.46% | 91075584 | 0 | 95342592 | 82944 | 0.643117 |
| 025 | 5 | 2279371 | 942938 | 58.63% | 88224768 | 0 | 92617728 | 110592 | 0.655173 |

All six new Makespans, spill totals and extra-DDR totals decreased relative to the same-case/core frozen dd9d8991 direct pilot. The old feed/result bytes were compared to Git data commit `81219bf923524fb60616e39b5ad2dced67aec3e2`. Old records were not re-executed. All paired graph/config/official identities match.

025 has zero official spill in these three runs; 014 retains positive spill. The envelope metadata is a priority-order certificate only, not a zero-spill proof or a runtime feasibility theorem. Multiple algorithm choices changed together, so the measured reductions do not identify a single causal mechanism.

This is a selected development sample, not the full 100-case result. End-to-end solver wall includes process launch, input, construction, output and observation/cleanup; the independent final E0 wall is separate in metrics.csv. Shared P1 load may be present, and wall timing is nonexclusive. RSS polling can miss short peaks.

Verified 84 per-cell manifest entries and 12 lossless compressed JSON round-trips; six independent feeds and the aggregate feed pass producer precheck. All original per-cell evidence remains unchanged. No central import, Git commit/push, mirror sync or broader acceptance was performed.

Official `final/official.log` files are Git-ignored and must be explicitly included by the parent publisher. Raw stdout backup path was emitted by the runner and sent to the parent; shared redactions, if present, are recorded in archive.json.
