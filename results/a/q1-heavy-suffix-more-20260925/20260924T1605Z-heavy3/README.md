# P1 heavy-component suffix: three-cell extension

Producer: delegated P1 evaluation agent for `nikolastarx/s-6607cb2735304751b36662035723372b`.
Task: [Issue33](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5815486806).
Branch: `codex/q1-heavy-suffix-more-e0-20260925`.

1. **Goal**: Evaluate the frozen heavy-suffix construction on 003/056/068 × k5, comparing official Makespan and DDR with fixed bounded04 originals. This separate extension does not rerun or alter the previous 049/088 batch and does not constitute all-case evaluation.
2. **Inputs**: Read-only `data/raw/a/official-cases.zip`, exact members verified against `docs/a/source-manifest.json`; unmodified official P1 code/config. Algorithm `4c8c58866cc8ffa5a3fa468adc727f8a0800bd0f`, entry `src/q1/heavy_suffix.py`, dominant_percent=80/max_rounds=64/max_sinks=64. Entry and four algorithm dependencies match that commit; runner/helpers/lockfile also have exact source receipts in `batch.json`.
3. **Outputs**: Complete plan/result/trace/log/run/diagnostics and child stdout/stderr in `cells/`; lossless gzip for result/trace. `board-feed.json` contains exactly 3 new board-submission-v1 attempts. `comparison.json`/CSV preserve paired comparison; `references/` preserves previous bounded plans/results and official singlecore originals. `STRUCTURAL_CHECK.json` adds read-only official legality checks.
4. **Limits**: 1 worker; at most 3 constructor + 3 E0 launches, constructor 30 s/E0 90 s/batch 420 s; first failure stops remaining dispatch; 0 retries/E1/E2. Parent reports P2/P3 each explicitly confirmed zero active scoring and allowed this short window. Host nonexclusive; no cloud/GPU, no sink8 execution, no baseline reruns or central-site changes.
5. **Acceptance**: All 3 cells succeeded with complete compute coverage, official derive/task-order legality, positive scene A/5-core E0 Makespan, complete evidence and hashes. Working-tree protocol precheck: 3/3 eligible. Delegated evaluation and byte validation do not replace independent scientific acceptance.
6. **Deadline**: Authorized short window; actual UTC 2026-09-24T16:05:38.533Z–2026-09-24T16:05:44.245Z, controller wall 5.712195 s including preflight/preparation. Resources released immediately after evaluation; no follow-on experiment runs automatically.

## Official quality and measured costs

| Case / simulated cores | Old bounded04 Makespan | Heavy-suffix Makespan | Old / new | Extra DDR old → new, bytes | Constructor seconds | External E0 seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 003 / 5 | 539607 | 169767 | 3.178515 | 393216 → 3842484 | 0.455452 | 1.961966 |
| 056 / 5 | 265764 | 81605 | 3.256712 | 0 → 1072416 | 0.290494 | 0.942186 |
| 068 / 5 | 304058 | 131234 | 2.316915 | 1944 → 2940458 | 0.182513 | 0.934325 |

Makespan units are simulated cycles; old/new describes same-case, same-core official quality. Additional DDR rises on all three cases. Scheduled-copy totals are 1677480→5126748, 221600→1294016 and 2773194→5711708 bytes respectively. Both old and new spill bytes are 0 for these three cases; zero spill therefore does not imply zero additional transfer. These probes show a cycle/transfer tradeoff and do not establish a universal quality bound.

- 003: 13455 compute operations (13194 heavy / 261 minor), 14 waves, 67 Tasks, dominant PIPE_M; selected `heavy-suffix`.
- 056: 7678 compute operations (7464 heavy / 214 minor), 14 waves, 69 Tasks, dominant PIPE_V; selected `heavy-suffix`.
- 068: 5351 compute operations (4176 heavy / 1175 minor), 14 waves, 61 Tasks, dominant PIPE_M; selected `heavy-suffix`.

All 3 actual constructors selected heavy-suffix. Their diagnostics describe submitted construction and cannot independently assign causality to each submechanism.

Actual budget: 3 constructor + 3 independent external E0 launches, 0 E1/E2/retries, 3 successful cells, 0 failures/timeouts/not_run. Child exits and cleanup confirmed in each `run.json`. Each constructor is a fresh Python process; timer includes input reading, fallback construction, heavy-suffix construction, structural validation, plan/diagnostics writing and exit. E0 timer includes external official evaluation and result/trace/log writing through exit. Source checks, ZIP materialization, gzip, export and additional structural checks are outside child timers. ZIP preparation took 0.008541958 s. Old bounded04 ran in a two-worker batch, while this batch used one; timings are descriptive, not a controlled speedup.

Machine: Apple M5 Pro, 48 GiB, macOS, Python 3.12.13, uv locked environment. OMP/OPENBLAS/MKL thread environment variables each set to 1; actual thread counts and peak RSS were not sampled. Host free+inactive+speculative memory proxies before cells were 11601854464, 11558141952, 11662065664 bytes; this is not process RSS or guaranteed allocatable memory.

## Fixed sources and reproduction

- Runner/manifest frozen before execution: `08945a78250b2657ee2ecba00a6dc3ced6223fa2`; entry `src/q1_benchmarks/heavy_suffix_more_e0.py`, declaration `src/q1_benchmarks/heavy_suffix_more_batch.json`. Shared controller generalized explicit cell list/batch timeout; old two-cell data remains at its original frozen runner/source.
- Constructor source `4c8c58866cc8ffa5a3fa468adc727f8a0800bd0f` remains unchanged. Source receipts include all five algorithm files plus helpers, lockfile, controller, wrapper and manifest.
- Prior bounded04 originals: `d63001eb01cc254a20bc60cae5e50b1eb1ee2808`, `results/a/q1-bounded-matrix-20260924/20260924T1459Z-bounded400/board-feed.json`; no prior solver or E0 rerun. The exact old attempt and copied original hashes are recorded per comparison.
- Official source hash `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`; config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`; archive `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`. Exact member/plan/source hashes are in receipts.
- Current main board entry/protocol reread before execution; protocol checker used from root (root HEAD at precheck `a36cbcab441ece5df55f104c983e3341265f9f4e`). `precheck.json`: 3/3 eligible. Precheck is read-only and has 0 solver/evaluator calls.
- Before freezing: syntax/declaration checks and a temporary synthetic controller first-failure fixture passed (1 mocked process request, 0 actual solver/evaluator calls; 1 synthetic failed + 2 not_run). It is excluded from real benchmark counts and feed.
- Additional read-only `derive_multicore_plan` + `validate_task_order` passed all saved plans using original ZIP bytes. One initial audit command referred to the wrong receipt field name, then was corrected to `cleanup_confirmed`; this did not invoke a solver or evaluator or alter run data.
- Execution: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -B src/q1_benchmarks/heavy_suffix_more_e0.py run 20260924T1605Z-heavy3`. Existing output directories are refused.
- Read-only export: `python -B src/q1_benchmarks/heavy_suffix_more_e0.py export 20260924T1605Z-heavy3`. Fixed-Git checks use the board protocol with `--commit` and `src/q1_benchmarks/bounded_matrix_verify.py` after data commit.

Parent handles publication/mirror/board intake. This agent performed no push, PR, external message or central write. This batch does not evaluate other graphs/cores, repeated controlled timings or real-device performance.
