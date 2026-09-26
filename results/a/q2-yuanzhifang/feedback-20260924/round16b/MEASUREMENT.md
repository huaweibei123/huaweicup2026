# round16b measurement (F1 snapshot; not full DDR FQ)

- Frozen solver source: `4a501d7f4a8b780263e097a963e12dcb66178e69`; spec commit `ed32a44447a07b60fa314fc60418f5303b71577f`; runner `fa6522a3266fe040379dd064092beb27c0b20a5e`; official E0 `45f647b395b84e9569f418fd33d62c2b8eb4d190`.
- New coordinated window preflight: **2,029,105,152 B** at 2026-09-24T20:58:17.7453697Z (≥1,610,612,736 B); no round16b task process was active. Earlier coordinator snapshots: P3 released at 2026-09-24T20:43:33.810454Z with 0 cold/0 E0; root measured 2,258,067,456 B at 2026-09-24T20:53:34.3988013Z. Windows 11 shared host; no exclusive-resource claim. Prior preflight stop remains unchanged.
- Runner T0/T1: **2026-09-24T20:58:25.193492Z / 2026-09-24T20:59:33.566269Z**, batch wall 68.373 s. Actual cost: **1 cold solver / 1 E0**; combined F1 total is 6/6. Export valid 1/1; audit passed, 2 gzip and 75785 trace operations verified.

| Case | E0 Makespan cycles | Spill bytes | Extra DDR bytes | Solver wall s | E0 wall s | stdout selected (base) | capacity_certified |
|---:|---:|---:|---:|---:|---:|---|:---:|
| 014 | 4,364,011 | 44,364,288 | 212,032,632 | 31.061421 | 32.917121 | frontier_gap_unresolved (base join_gap_packet) | False |

This is a two-cell F1 diagnostic snapshot, not a full DDR FQ. No retries.
