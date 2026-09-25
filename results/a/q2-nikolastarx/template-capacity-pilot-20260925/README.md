# Capacity-constrained job pipeline: three independent E0 probes

Fixed constructor: `43da83c6f2fb3da7630403d6cf941d34f1826f9c`.
Fixed plans and runner: `c3c96f7de6c46a8d9d1f60c764797f9728cb5ac5` (the commit containing this directory's
manifest, input capsule, and `scripts/q2_fixed_plan_probe.py`). No case-specific
rules or stored scores enter the constructor; `old_M` only annotates comparisons.

| Case, K5 | Prior complete solver M | Capacity job pipeline M | Change in M | Spill |
| --- | ---: | ---: | ---: | ---: |
| 044 | 43,795 | 40,862 | −6.697% | 0 |
| 046 | 77,846 | 89,121 | +14.484% | 0 |
| 078 | 477,473 | 1,080,537 | +126.303% | 0 |

All three official results confirm the no-spill certificates, but the two
regressions prevent adopting this construction unconditionally. Compared with
the earlier stage-major priorities, job-major priorities with capacity-aware
cuts improve all three; ownership and cuts also change, so this is not an
order-only ablation. The official baseline comparison is against the frozen
previous solver, not the failed stage-major prototype.

This is a fixed-plan mechanism experiment, **not a complete algorithm score**.
It ran on a separate CPU Standard Colab instance with Python 3.13.15. Three E0
calls, zero E2, one worker, no retries; actual T0 2026-09-25T02:14:10Z,
evaluation batch 1.541 seconds. Plans were constructed locally in approximately
0.06–0.08 seconds each; those timings exclude graph file loading and are not
remote cold-solver timings. No dependencies were installed and no native E2
library was loaded. The official Python sources and every graph/config/plan
were checked against the frozen capsule hashes before scoring.

`capsule.zip`: 177,452 bytes, SHA-256
`496a671d61e4c96a192485f2321544a99a193bb668f23f8dbaa6e9805c49eaea`.
Downloaded `results.zip`: 316,571 bytes, SHA-256
`9530134ac1b732124f37d3e7c6b2ae3486c5584310eee40d78d95ccc7cd96781`.
The result ZIP retains plans, manifest, complete E0 outputs, traces and process
receipts. Local verification checked all three result hashes and scalar metrics,
successful exits and no surviving descendants. The independent VM was stopped
after download; no formal full500 was started or resumed by this probe.
