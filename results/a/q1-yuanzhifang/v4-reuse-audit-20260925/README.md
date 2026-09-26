# P1 v4 full500 k4 reusable-result audit

Archive commit: `9c5f87548cc7588465a638e032993969b5cac891`  
Source solver: `a0537aeb72dc702af86d67d3194587d581ac207c`  
Runner: `85b99a74101e3a7981b60566ad7937bcc8dc5426`  
Feed: `results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json`  
Feed SHA-256: `4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764`

Zero-score audit; no solver or evaluator ran. The JSON index contains the 100 k4 rows and per-artifact hashes.

Coverage: 100/100; unique cases 100/100; feed statuses {'ok': 100}.
Mean Makespan: 793556.040000 cycles; mean baseline: 3124793.730000 cycles; arithmetic mean of per-case baseline/Makespan ratios: 3.453039755×.
All 100 plan/result/run/baseline byte checks and result/trace decompressed raw-hash bridges completed; exceptions/non-reusable: 0; identity/hash errors: 0.

## Reuse condition

Reuse archived E0 only if the new case/k4 candidate plan is byte-identical to the archived plan. The public archive contains actual plan, compressed E0 result, compressed trace, and derived run receipts. The audit does not replay E0 or independently prove all schedule constraints; successful E0 status and matching result identity are recorded evidence. Historical solver timings are not new-run timing.

Per-case evidence: `reusable-index.json`.

Producer: Luna medium, continued session
`yuanzhifang30-sudo/s-7748b08eb22a449797a2417ad7825aaa`; parent read the
summary and reusable index. A supplementary protocol check over all 500 feed
rows was interrupted in its own process tree after exceeding the parent's
bounded wait while lazy-fetching Git blobs. That protocol check is **not**
reported as passed; it does not invalidate or extend this completed 100-row
byte audit. Solver/Task-compiler/E0/E1/E2 calls in this audit all remain zero.
