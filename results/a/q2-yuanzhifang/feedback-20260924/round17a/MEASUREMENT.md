# round17a measurement

- Frozen algorithm source: `4a501d7f4a8b780263e097a963e12dcb66178e69`; spec commit: `aa540d3aa5ebdc1995461c58fcaa8afd033dde1d`; runner: `fa6522a3266fe040379dd064092beb27c0b20a5e`; official E0: `45f647b395b84e9569f418fd33d62c2b8eb4d190`. This is F1, not full DDR FQ.
- New coordinated window. Preflight RAM: **1,915,219,968 B** at **2026-09-24T21:08:46.4799500Z** (required ≥1,610,612,736 B). P1 coordinated 0-scoring window; P3 has no active E0. Windows 11 shared host, so no exclusive-resource claim.
- Runner T0/T1: **2026-09-24T21:08:56.477080Z / 2026-09-24T21:13:03.997903Z**; batch wall 247.521 s. Actual cost: **33 cold / 33 E0**. Board export valid 33/33; audit passed, 66 gzip artifacts and 252774 trace operations verified.

| Case | E0 Makespan cycles | Spill bytes | Extra DDR bytes | Solver wall s | E0 wall s | stdout selected (base) | capacity_certified |
|---:|---:|---:|---:|---:|---:|---|:---:|
| 001 | 47,502 | 0 | 4,608 | 0.655844 | 0.947061 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | True |
| 002 | 56,081 | 0 | 608,256 | 1.171382 | 2.165676 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | True |
| 003 | 205,295 | 0 | 9,845,480 | 11.183115 | 14.936781 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 004 | 86,693 | 110,592 | 2,626,560 | 1.132263 | 1.648686 | frontier_gap_unresolved (base join_gap_packet) | False |
| 005 | 47,017 | 0 | 2,346,552 | 4.109240 | 3.562912 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 006 | 25,613 | 0 | 800,540 | 1.663090 | 1.128418 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 007 | 197,112 | 0 | 110,592 | 3.613336 | 2.513153 | frontier_gap_capacity_repair (base join_gap_packet) | True |
| 008 | 52,291 | 0 | 0 | 2.001148 | 1.213572 | frontier_resource_word | True |
| 009 | 54,517 | 0 | 1,604,936 | 4.304618 | 4.332270 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 010 | 24,256 | 0 | 1,014,156 | 1.363643 | 1.127536 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 011 | 46,777 | 0 | 811,008 | 0.891241 | 1.289405 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | True |
| 012 | 17,257 | 0 | 419,568 | 1.653843 | 1.800741 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 013 | 54,363 | 0 | 32,768 | 1.748551 | 1.609499 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | True |
| 015 | 52,362 | 0 | 2,114,000 | 2.559810 | 2.763904 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 016 | 2,091,375 | 0 | 411,496 | 12.074770 | 14.487198 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 017 | 38,576 | 0 | 1,142,720 | 1.901416 | 1.296171 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 018 | 215,524 | 0 | 6,437,960 | 2.392947 | 1.510641 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 019 | 21,398 | 0 | 985,456 | 0.961357 | 0.651077 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 020 | 477,078 | 11,681,792 | 25,894,912 | 3.793001 | 3.283937 | frontier_gap_unresolved (base join_gap_packet) | False |
| 021 | 1,247,227 | 3,555,328 | 10,620,928 | 1.373754 | 2.227081 | frontier_gap_unresolved (base gap_guard_capacity_fallback) | False |
| 022 | 24,088 | 0 | 1,120,790 | 1.326116 | 0.919594 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 023 | 33,864 | 0 | 1,541,988 | 0.827238 | 1.036451 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 024 | 695,607 | 0 | 399,256 | 4.260215 | 2.954656 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 025 | 1,122,490 | 19,342,848 | 44,037,120 | 9.895255 | 13.129775 | frontier_gap_unresolved (base join_gap_packet) | False |
| 026 | 38,416 | 0 | 1,599,356 | 0.955207 | 0.707812 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 027 | 558,753 | 0 | 3,317,760 | 0.787030 | 1.690861 | frontier_gap_certified_unchanged (base gap_guard_capacity_fallback) | True |
| 028 | 8,294,722 | 28,629,504 | 80,862,720 | 13.679557 | 12.842080 | frontier_gap_unresolved (base join_gap_packet) | False |
| 029 | 17,941 | 0 | 586,516 | 1.478718 | 0.980231 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 030 | 562,386 | 815,104 | 7,831,552 | 2.544147 | 5.356256 | frontier_gap_unresolved (base gap_guard_capacity_fallback) | False |
| 031 | 423,515 | 502,784 | 21,595,228 | 5.061067 | 5.554795 | frontier_gap_unresolved (base join_gap_packet) | False |
| 032 | 12,568 | 0 | 379,604 | 1.160603 | 1.303227 | frontier_gap_certified_unchanged (base join_gap_packet) | True |
| 033 | 463,501 | 476,160 | 23,435,472 | 3.094160 | 2.871369 | frontier_gap_unresolved (base join_gap_packet) | False |
| 034 | 255,779 | 0 | 12,490,440 | 3.944065 | 3.518002 | frontier_gap_certified_unchanged (base join_gap_packet) | True |

No retries. The earlier zero-dispatch resource preflight is not an algorithm failure and is excluded from cost.
