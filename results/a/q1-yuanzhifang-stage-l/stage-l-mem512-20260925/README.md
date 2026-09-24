# Stage L: shared-pipeline diagnostic cells

Runner: `aa66a805551a2f2225795f2ec5b2db444ba35b28`; solver source: `5c64b4057cb9b2f2af5426bd1efdd579b9df5559`; session: `yuanzhifang30-sudo/s-7748b08eb22a449797a2417ad7825aaa`.

Run T0: `2026-09-24T22:07:52.148724Z`. Run T1: `2026-09-24T22:08:08.851017Z`; batch wall: 16.703258 s. Budget: 2 cold solver + 2 new E0, 0 E1/E2/retries, 1 worker, 120/90/300 s. Both owned Jobs closed with zero active processes; Job memory cap was 536,870,912 B. Pre-cell available RAM was 2,380,935,168 B for k3 and 2,135,826,432 B for k4.

| Cell | E0 Makespan (cycles) | scheduled copy bytes | extra DDR bytes | spill bytes | solver wall (s) | E0 wall (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 044/k3 | 84,041 | 2,932,000 | 1,956,544 | 0 | 7.0336955 | 0.8484066 |
| 044/k4 | 82,479 | 2,957,344 | 1,981,888 | 0 | 7.7344650 | 0.9378048 |

Both cells succeeded. Raw plans, diagnostics, online events, stdout/stderr, E0 results/traces/logs, receipt and manifest are retained under `run/`. Submission-v1 feed: `board-feed.json`. These are two diagnostic cells, not a full P1 average.

## Comparison with the fixed v4 same-cell E0 reference

The approved v4 full500 feed at commit `9c5f87548cc7588465a638e032993969b5cac891` reports 044/k3 and 044/k4 at 64,624 cycles each (scheduled DDR 2,026,944 B; extra DDR 1,051,488 B). Stage L is worse on both cells: k3 is +19,417 cycles (+30.05%) and +905,056 scheduled/extra DDR bytes; k4 is +17,855 cycles (+27.63%) and +930,400 scheduled/extra DDR bytes. Treat these as negative diagnostic results; no causal claim is made beyond the same graph/core/config/E0 comparison. No further scoring or retries were run.
