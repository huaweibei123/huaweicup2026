# round17b measurement

- Frozen algorithm source `4a501d7f4a8b780263e097a963e12dcb66178e69`; spec commit `aa540d3aa5ebdc1995461c58fcaa8afd033dde1d`; runner `fa6522a3266fe040379dd064092beb27c0b20a5e`; official evaluator `45f647b395b84e9569f418fd33d62c2b8eb4d190`.
- Preflight RAM: 2,224,652,288 B at 2026-09-24T21:28:37.4331545Z (threshold 1,610,612,736 B). Shared Windows host; no exclusive-resource claim.
- Runner T0/T1: 2026-09-24T21:28:46.010926Z / 2026-09-24T21:33:09.667184Z; wall 263.656 s. Calls: 33 cold solver / 33 E0; no retry.
- Export CLI returned successfully for 33/33; success-return observation upper bound (same shell, sampled immediately after CLI returned): **2026-09-24T21:34:00.6351286Z**. Do not substitute feed `created_at` for this observation.
- Last per-run E0 `finished_at`: **2026-09-24T21:33:08.977721Z**. Audit passed: 66 gzip artifacts and 336332 trace operations verified. This is F1, not full DDR FQ.

| Case | E0 Makespan cycles | Spill bytes | Extra DDR bytes | Solver wall s | E0 wall s | stdout selected (base) | capacity_certified |
|---:|---:|---:|---:|---:|---:|---|:---:|
| 035 | 43,168 | 0 | 1,359,334 | 2.726362 | 2.577565 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 036 | 187,182 | 0 | 4,608 | 1.100668 | 1.799784 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | True |
| 037 | 43,545 | 0 | 942,080 | 0.592749 | 1.140237 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | True |
| 038 | 332,049 | 0 | 15,812,228 | 4.677236 | 3.433693 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 039 | 373,369 | 4,276,224 | 16,572,416 | 1.777966 | 2.852192 | frontier_gap_unresolved (base gap_guard_capacity_fallback) | False |
| 040 | 78,024 | 0 | 3,264,296 | 2.225771 | 2.060824 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 041 | 1,507,431 | 9,783,296 | 71,115,976 | 11.549220 | 12.196092 | frontier_gap_unresolved (base join_gap_packet) | False |
| 042 | 341,131 | 0 | 11,596,144 | 3.937906 | 2.397486 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 043 | 208,889 | 0 | 10,459,268 | 5.675029 | 6.577500 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 044 | 85,648 | 0 | 3,954,560 | 1.465824 | 0.849020 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 045 | 101,085 | 466,944 | 5,443,584 | 1.461156 | 1.329389 | frontier_gap_unresolved (base join_gap_packet) | False |
| 046 | 107,265 | 0 | 4,862,336 | 0.933626 | 1.083409 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 047 | 103,379 | 0 | 4,295,736 | 8.798727 | 10.206396 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 048 | 95,213 | 0 | 863,926 | 1.569783 | 1.281716 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 049 | 66,201 | 0 | 3,242,496 | 2.569905 | 2.715368 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 050 | 54,745 | 0 | 2,675,604 | 3.441902 | 2.782298 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 051 | 168,773 | 0 | 394,636 | 1.488383 | 1.027546 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 052 | 48,765 | 0 | 1,909,190 | 1.818202 | 0.897189 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 053 | 383,506 | 0 | 15,785,380 | 7.867094 | 7.284670 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 054 | 257,626 | 0 | 12,142,020 | 9.523695 | 12.425111 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 055 | 32,137 | 0 | 1,111,702 | 1.007584 | 0.866678 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 056 | 96,280 | 0 | 4,863,236 | 5.092360 | 6.228369 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 057 | 20,991 | 0 | 828,068 | 1.420515 | 0.982938 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 058 | 1,072,409 | 22,691,840 | 41,074,688 | 3.908728 | 10.199552 | frontier_gap_unresolved (base gap_guard_capacity_fallback) | False |
| 059 | 150,736 | 0 | 2,072,576 | 1.390947 | 1.893933 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | True |
| 060 | 294,941 | 139,264 | 14,800,388 | 4.641251 | 3.059847 | frontier_gap_unresolved (base join_gap_packet) | False |
| 061 | 19,263 | 0 | 422,952 | 1.367265 | 0.878549 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 062 | 656,558 | 746,496 | 10,813,440 | 4.452176 | 14.944432 | frontier_gap_unresolved (base gap_guard_capacity_fallback) | False |
| 063 | 232,306 | 15,360 | 3,078,144 | 1.931906 | 4.431305 | frontier_gap_unresolved (base gap_guard_capacity_fallback) | False |
| 064 | 11,274 | 0 | 93,940 | 0.717335 | 1.076864 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 065 | 13,912 | 0 | 403,922 | 0.753346 | 0.547859 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 066 | 110,787 | 0 | 4,679,184 | 4.304711 | 3.407421 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 067 | 13,215,355 | 180,084,736 | 219,647,488 | 4.724432 | 4.636636 | frontier_gap_unresolved (base join_gap_packet) | False |

No `capacity_certified=true` case has nonzero official spill.
