# Shared-wave pilot receipt: three cells

Source `ee1b8fd39efab8c8ed8140bbebe4c08e778052b9`; runner `774cfe8474dad18315d08368db02d030387d6b6d`; historical comparison read from `571536962b3f6ad9468584a0e5ae04398e684543`. Each cell has one solver and one external E0, with zero online E0/E1/E2. All selected process receipts and live PID checks indicate exit; manifest/feed hashes, gzip roundtrips, input hashes, and unique operator coverage passed.

| Case / cores | Makespan old → new | Change | Extra DDR old → new | Spill new | Solver / E0 seconds |
|---|---:|---:|---:|---:|---:|
| 044 / 4 | 124,268 → 66,901 | 46.16% lower | 5,678,624 → 2,791,200 B | 0 B | 0.179 / 0.239 |
| 083 / 4 | 450,029 → 210,367 | 53.25% lower | 14,977,600 → 2,791,200 B | 0 B | 0.222 / 0.476 |
| 092 / 4 | 1,927,728 → 997,263 | 48.27% lower | 67,180,384 → 6,264,608 B | 3,473,408 B | 0.562 / 2.354 |

Each new plan preserves the old node-to-subgraph partition and operator core assignment; only core order differs. This controls the submitted-plan change, but aggregate totals alone do not identify the individual queue or credit mechanism. The 092 result retains substantial spill. These are three single-cell observations, not a full-suite score. Audit performed no solver or evaluator run and adds zero scoring.
