# P1 overload: remaining 16 declared activation probes

Producer: delegated P1 evaluation agent for `nikolastarx/s-6607cb2735304751b36662035723372b`.
Task: [Issue33](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5815486806).
Existing branch/worktree reused: `codex/q1-overload-probe-e0-20260925`; no additional checkout created.

1. **Goal**: Evaluate the remaining 16 statically activated k5 graphs, including quiet-pipe/retained-heavy-single-sink potential negative cases, after the separate 050/054 batch. Selection was declared before scoring. Compare each with old bounded04 and separately compare the five previous heavy-suffix results; preserve all regressions.
2. **Inputs**: Solver `3c6e41b938c764d207de45584fb526c64f4eb845`, unchanged `src/q1/component_overload.py`, frozen defaults64/64. Exact official ZIP bytes, source and config checked by manifest. No online E0 or parameter tuning.
3. **Outputs**: Complete original plans, full losslessly compressed E0 result/trace, original official.log, diagnostics and process receipts for16 cells; `board-feed.json` has exactly16 new attempts. `comparison.json`/CSV hold the new paired bounded comparison. `heavy-comparison.json` preserves heavy5 sources and original plan/result hashes. `activation18-comparison.json` and `activation-summary.json` combine these16 with referenced original050/054 attempts, without duplicating those attempts in the newfeed.
4. **Limits**: At most16 solver+16 external E0,1worker,30s constructor/90s E0/900s batch; first failure stops,0retries/E1/E2/baseline reruns. Explicit root EXECUTE and resource release reason are in `batch.json`: P3 code was not frozen,0calls and no reserved window; P2 released. Host nonexclusive; no Colab/GPU or central writes.
5. **Acceptance**: All16 constructors and E0 calls succeeded, full compute coverage and5core contract verified; all saved plans additionally pass official derive/task-order structural validation. Working-tree protocol16/16eligible. These are successful official evaluations with source evidence, distinct from independent scientific acceptance or proof of general quality.
6. **Deadline**: Granted finite window; UTC 2026-09-24T16:36:14.132Z–2026-09-24T16:36:47.483Z; controller 33.351302s. All32 child processes exited0 and cleanup_confirmed=true; resource release reported immediately, gatecomplete. No further scoring authorized here.

## Quality: keep the negative cases

New16 relative to bounded04: **12 improved,4 regressed,0tied**, all16successful. Arithmetic mean of per-case bounded/new ratios: 1.793965315. With original050/054, the full18activation set is **14 improved,4 regressed**, mean bounded/new 1.871540100. These are comparisons within a preselected18activation subset, not official singlecore acceleration and not an all100mean. The method is not replaced by a per-case best-of portfolio.

| Case / requested k5 | Bounded04 cycles | Overload cycles | Old/new | Extra DDR old → new,bytes | New spill bytes | Constructor s | External E0 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 003 | 539607 | 165184 | 3.266703 | 393216 → 4026936 | 0 | 0.563918 | 1.945742 |
| 009 | 92225 | 50248 | 1.835396 | 49152 → 545012 | 0 | 0.235695 | 0.669291 |
| 031 | 306213 | 325259 | 0.941444 | 8059392 → 8548106 | 1482240 | 0.186980 | 2.613621 |
| 032 | 10415 | 10939 | 0.952098 | 12360 → 84104 | 0 | 0.075387 | 0.123080 |
| 035 | 95460 | 55444 | 1.721737 | 0 → 529378 | 0 | 0.129901 | 0.510745 |
| 040 | 110337 | 94410 | 1.168700 | 66048 → 968026 | 0 | 0.132931 | 0.398345 |
| 043 | 269612 | 178035 | 1.514376 | 1062920 → 4260434 | 49160 | 0.345991 | 1.460869 |
| 049 | 160260 | 57111 | 2.806114 | 0 → 611708 | 0 | 0.175221 | 0.459590 |
| 053 | 492699 | 417165 | 1.181065 | 6918912 → 11178746 | 3337824 | 0.449911 | 1.582835 |
| 056 | 265764 | 77253 | 3.440177 | 0 → 1064220 | 0 | 0.389848 | 0.895061 |
| 057 | 16538 | 16736 | 0.988169 | 27936 → 143424 | 0 | 0.076511 | 0.130701 |
| 066 | 250449 | 99777 | 2.510087 | 29280 → 2410142 | 0 | 0.179600 | 0.874280 |
| 068 | 304058 | 133424 | 2.278885 | 1944 → 2939810 | 0 | 0.293224 | 0.772423 |
| 077 | 121081 | 140494 | 0.861823 | 172032 → 1249546 | 0 | 0.180237 | 0.816488 |
| 087 | 886373 | 869315 | 1.019622 | 13547520 → 23863502 | 4866048 | 1.139300 | 10.849795 |
| 088 | 202791 | 91469 | 2.217046 | 221184 → 2176610 | 0 | 0.175194 | 0.459648 |

The four bounded-relative regressions are031(+6.219854%),032(+5.031205%),057(+1.197243%) and077(+16.033069%). Every one is preserved with its submitted plan/result. 031's spill decreases1810944→1482240bytes while Makespan worsens; this rules out equating lower spill with faster overall execution. The other three remain zero-spill while extra DDR rises. No causal attribution to a particular scheduling stage is proved by these aggregate fields.

All16actually selected `overload-list`. Nonzero spill occurs on031(1482240bytes),043(49160),053(3337824),087(4866048). Original050/054were alsooverload-list; their independent runner/budget/run identities remain intact.

## Separate comparison with the original heavy5

| Case / k5 | Heavy-suffix cycles | Overload cycles | Heavy/overload | Extra DDR heavy → overload,bytes |
| --- | ---: | ---: | ---: | ---: |
| 003 | 169767 | 165184 | 1.027745 | 3842484 → 4026936 |
| 049 | 62114 | 57111 | 1.087601 | 593240 → 611708 |
| 056 | 81605 | 77253 | 1.056334 | 1072416 → 1064220 |
| 068 | 131234 | 133424 | 0.983586 | 2940458 → 2939810 |
| 088 | 92700 | 91469 | 1.013458 | 2029154 → 2176610 |

Four improve;068worsens131234→133424(+1.668775%), while its extra DDR falls by648bytes. 003/049/088gaincycles with higher extraDDR;056improves both. This distinction is retained rather than describing overload as a universal improvement. Oldheavy plans/results are copied byte-for-byte from `fe67740a90857e127c5d3996d1c444a083efcebc` (049/088) and `5e6db81204fd8dcf8c9557770c3d08882e8cf630` (003/056/068); all used solver4c8. Noheavy scorer was rerun.

## Calls, timing and sources

Actual new calls16solver+16E0;0E1/E2/retries. Adding the separate original050/054 produces18solver+18E0 for the declared activation set, without inventing new attempts. Other algorithm experiments are separate. The frozen child helper holds/waits realPIDs but does not serialize their numeric values; receipts preserve exit/cleanup/time and noPIDnumbers are guessed afterwards.

Constructor wall min/mean/max is 0.075387/0.295616/1.139300s. External E0 min/max/sum is 0.123080/10.849795/24.562516s. These are observed shared-host durations from fresh Python processes, including read/fallback/construction/structural validation/plan+diagnostics output/exit forsolver, and fullresult/trace/log/exit forE0. Audits, ZIP preparation(0.030791375s), gzip and export are outside childtimers. No exclusive timing, P95or controlled wall-speedup claim is made.

Machine: AppleM5Pro48GiB/macOS/Python3.12.13, uv locked deps; OMP/OPENBLAS/MKL each1, actualthreads andpeakRSSnotmeasured. Host availabilityproxy snapshots are inbatch; they are not processRSS.

- Frozenrunner `79d3f271ae63039e4fc969e08120f90c87e832db`, `src/q1_benchmarks/overload_activation_e0.py`; explicit matrix/budget in `overload_activation_batch.json`. Sixalgorithm files plushelpers/lock/controller/wrapper/manifest checked(13receipts). Samealgorithm SHA3c6throughout.
- Default bounded source `d63001eb01cc254a20bc60cae5e50b1eb1ee2808` from the old400run. **087/k5uses explicit frozen override** `f0dde725a047f1fb3bce03a30a3850d49b708463`, `results/a/q1-bounded-timeout-20260924/20260924T1524Z-timeout4/board-feed.json`: the old400attempt timedout; its later independent180s diagnostic succeeded with identical05f8algorithm and identicalplan bytes. Originaltimeout remains historical; this comparison does not revise it.
- Original050/054reuse `11491834c74b5d5930af11ea70e9e452d4f7666c`, `results/a/q1-overload-probe-20260925/20260924T1629Z-overload2`; newfeed excludes them.
- Officialcode `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`; config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`; archive `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`. Per-member/plan/artifact hashes inrunreceipts.
- Pre-freeze synthetic gate/firstfailure/export/source-selection tests invoked0actualsolver/E0. Temporaryfixture removed; receiptsinpreparation. Additional saved-plan derive/Task-order checks invoke0solver/E0.
- Boardprotocol fromrootHEAD `2922eb144d7fa64b12bb0a2eac6f6146bd04e160` returns16/16eligible. FixedGitchecks followcommit. `overload_activation_report.py` regenerates pairedreports and readonly structuralchecks fromsavedbytes; it neverconstructs a newplan or scoresE0.

Completedcommand: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -B src/q1_benchmarks/overload_activation_e0.py run 20260924T1636Z-overload16`.
Read-onlyexport: `python -B src/q1_benchmarks/overload_activation_e0.py export 20260924T1636Z-overload16`.
Read-onlyreport: `python -B src/q1_benchmarks/overload_activation_report.py results/a/q1-overload-activation-20260925/20260924T1636Z-overload16`.

Parent handles publication/mirror/boardintake. No push/PRorcentralwrite here. Other82graphs, othercores, hiddeninputs and hardwarebenefits remain outside thisbatch. The4regressions and068heavy-relative tradeoff guide futureanalysis; they do not authorize moreexperiments.
