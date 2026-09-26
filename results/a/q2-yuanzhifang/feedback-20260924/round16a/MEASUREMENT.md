# round16a measurement (F1 snapshot; not full DDR FQ)

- Frozen solver source: `4a501d7f4a8b780263e097a963e12dcb66178e69`; spec commit `ed32a44447a07b60fa314fc60418f5303b71577f`; runner `fa6522a3266fe040379dd064092beb27c0b20a5e`; official E0 `45f647b395b84e9569f418fd33d62c2b8eb4d190`.
- This is a new coordinated window. RAM before dispatch was **2,313,510,912 B** (≥1,610,612,736 B); exact sample timestamp was not captured. Coordinator snapshots: P3 released at 2026-09-24T20:43:33.810454Z with 0 cold/0 E0; root measured 2,258,067,456 B at 2026-09-24T20:53:34.3988013Z. Prior stop record remains separate and unchanged. Windows 11 shared host; no exclusive-resource claim.
- Runner T0/T1: **2026-09-24T20:54:15.491892Z / 2026-09-24T20:55:43.811924Z**, batch wall 88.320 s. Actual cost: **5 cold solver / 5 E0** (task cap 6/6; one cell remains for round16b). Board export valid 5/5; audit passed, 10 gzip and 113027 trace operations verified.

| Case | E0 Makespan cycles | Spill bytes | Extra DDR bytes | Solver wall s | E0 wall s | stdout selected | capacity_certified |
|---:|---:|---:|---:|---:|---:|---|:---:|
| 008 | 84,303 | 0 | 0 | 1.026812 | 0.838935 | frontier_resource_word | true |
| 025 | 1,610,875 | 22,516,224 | 49,866,240 | 9.850137 | 17.001680 | frontier_gap_unresolved (base join_gap_packet) | false |
| 036 | 311,345 | 0 | 2,304 | 1.054269 | 1.859185 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | true |
| 072 | 7,844,564 | 53,360,576 | 201,600,624 | 17.451641 | 28.495287 | frontier_gap_unresolved (base join_gap_packet) | false |
| 095 | 357,591 | 0 | 0 | 1.441685 | 3.324161 | frontier_resource_word | true |

No failures or retries. Zero preflight dispatches from the preserved earlier stop are not algorithm failures and do not count toward these costs.
