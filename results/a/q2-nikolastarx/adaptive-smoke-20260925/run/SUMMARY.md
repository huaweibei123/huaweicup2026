# Frozen adaptive-router smoke: six independent cells

Source `6e5099a35300133419990bf1f44f621f98850c21`; runner `08638ceb1ced999a1fe6024bbea61bc32657314f`.

UTC 2026-09-24T16:15:02.091982Z to 2026-09-24T16:15:44.823921Z; aggregate driver wall 42.731841292 s.

All six separately dispatched solver calls and six final official E0 calls succeeded. Online E0/E1/E2=0; scoring failures/retries=0. This postprocess added zero solver/evaluator calls. The initial missing-input preflight failed before scoring; original case bytes were linked and verified before the actual run (parent report).

| Case | k | Actual route | Makespan cycles | DDR B | Extra DDR B | Spill B | Solver s | Final E0 s |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| 008 | 3 | resource_word | 84303 | 2654424 | 0 | 0 | 0.190222 | 0.263972 |
| 014 | 4 | component_envelope | 4510101 | 68849500 | 58916760 | 29287824 | 1.182328 | 9.450118 |
| 025 | 5 | component_envelope | 942938 | 8328192 | 110592 | 0 | 0.648000 | 3.306249 |
| 016 | 1 | component_envelope | 7715523 | 393218 | 0 | 0 | 0.423934 | 5.186268 |
| 016 | 2 | dag_eft | 9260226 | 420227818 | 419834600 | 379715584 | 0.504127 | 5.846209 |
| 062 | 4 | dag_eft | 1607053 | 83630592 | 70228992 | 31706112 | 0.766003 | 7.076241 |

The routes are resource_word (one), component_envelope (three), and dag_eft (two). This frozen unified router does not include the subsequently developed tree_frontier/vector_lanes constructors. It is six selected smoke cells, not a whole-100 or 500-cell result; no global mean is reported.

Byte-for-byte plan equality and identical Makespan/DDR/extra/spill are confirmed against archived envelope 014-k4 / 025-k5 and direct 016-k2 / 062-k4. Old results are read only; the new six calls were explicitly required by the smoke protocol and really executed. Route-equivalence does not imply that the new timing difference is caused by shared-index reuse.

| Cell | Later specialist | Specialist Makespan | Frozen router Makespan | Router / specialist |
|---|---|---:|---:|---:|
| 016-k2 | vector | 4170750 | 9260226 | 2.220278 |
| 062-k4 | tree | 1008337 | 1607053 | 1.593766 |

These two negative comparisons are retained. Their earlier tree/vector improvements are not attributed to this router. Capacity-priority metadata is not a runtime spill certificate, as the nonzero spill results show.

Checked 84 per-cell manifest entries, 12 compressed JSON raw/stored hash-and-size roundtrips, 133 immutable originals and 18 completed process receipts. No recorded child PID is present at verification. All six original prechecks and the aggregate precheck are eligible locally; this is not central admission or independent scientific acceptance.

metrics.csv uses LF and includes matched official single-core denominators per cell. The P2 k=1 constructed result remains distinct from that denominator. Source/runtime/input/config/official hashes are checked against captured receipts and current original bytes; Git object verification and publication remain with the parent. No old scoring, Git command, message, network request, ledger write or mirror synchronization was performed by this script.

Publication: explicitly include the six nested final/official.log files (normally Git-ignored). Original batch/driver receipts retain their actual absolute interpreter paths and are not silently rewritten. Parent should review these paths before publication. Shared-machine before/after wall differences are descriptive, not causal speedup.
