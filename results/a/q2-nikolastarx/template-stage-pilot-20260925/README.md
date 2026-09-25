# Contiguous template ownership, stage-major order: negative mechanism probe

Constructor `7f7583ea8d4d1b183bb1cac491ed2d9c689c068d`; three fixed plans,
official graphs/config, five cores. This is not a cold full-grid algorithm run.

| Case | Previous selected M | Stage-major M | Extra DDR bytes | Spill bytes |
| --- | ---: | ---: | ---: | ---: |
| 044 | 43,795 | 77,638 | 188,672 | 0 |
| 046 | 77,846 | 216,457 | 491,520 | 0 |
| 078 | 477,473 | 2,056,224 | 724,992 | 0 |

Three E0 calls, zero E2, no evaluation retry, one worker. Actual dispatch was
2026-09-25T01:46:32Z; total evaluation batch wall 1.304 seconds. All processes
exited successfully with no surviving descendants. Input identities, source,
construction timings and unchanged plans are in `manifest.json`; complete
official outputs/receipts are in `results.zip`, 307,194 bytes, SHA-256
`4a3b60e354dafb386619ec29b36034eeddd4f3d50676324c35251f0f68b27294`.

The exact no-spill interval certificates held, but lower replication did not
produce better Makespan. The official compute intervals for 044 show successive
core starts at 60, 13,318, 32,047, 50,049 and 68,425 cycles; preceding core compute
ends were 14,234, 32,314, 51,039, 69,355 and 77,473. Most work is therefore nearly
serial across stages. This is evidence against processing all jobs at one
template position before moving forward, not against every possible template
partition or job pipeline.

One earlier **zero-score preflight** attempt ran in the notebook's default Python
and was rejected by the native build/runtime identity guard before E0 dispatch.
The same fixed plans were then evaluated once in the capsule's locked venv.
No identity guard was weakened. The unrelated COPY-event full500 started later
and contains none of these plans.
