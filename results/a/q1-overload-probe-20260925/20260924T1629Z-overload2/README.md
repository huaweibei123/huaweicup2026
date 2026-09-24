# P1 component-overload: two official probes

Producer: delegated P1 evaluation agent for `nikolastarx/s-6607cb2735304751b36662035723372b`.
Task: [Issue33](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5815486806).
Branch: `codex/q1-overload-probe-e0-20260925`.

1. **Goal**: Measure frozen per-pipe component-overload/quotient ready-list construction on 054/050 × k5. These two declared mechanism probes compare to old bounded04 and do not establish all-case quality.
2. **Inputs**: Read-only original official ZIP members and config, validated by source manifest; unmodified E0. Solver `3c6e41b938c764d207de45584fb526c64f4eb845`, entry `src/q1/component_overload.py`; frozen CLI defaults max_rounds=64/max_sinks=64. All six algorithm files and helper/lock/runner sources have hash receipts. No online evaluator or parameter adjustment.
3. **Outputs**: `cells/` keeps complete plan/result/trace/log/run/diagnostics and child output. Full E0 result and trace are lossless gzip. `board-feed.json` contains 2 v1 attempts. Exact old bounded04 same-cell plan/result and official singlecore evidence are copied into `references/`; comparisons, structural checks and preparation receipts are retained.
4. **Limits**: 2 solver + 2 external E0 maximum, 1 worker, constructor 30 s/E0 90 s/batch 300 s, first failure stops remaining dispatch; 0 retry/E1/E2. No third graph, baseline recomputation, cloud/GPU or central-site writes. Root explicitly released execution after P2 finished and P3 was told to wait; original authorization is in `batch.json`. Host nonexclusive.
5. **Acceptance**: Both saved plans fully cover compute ops with exactly 5 core schedules; official derive/task-order checks and complete E0 evaluation passed. Working-tree board precheck 2/2 eligible; fixed-Git verification follows commit. These checks distinguish delegated execution, byte validation and independent scientific acceptance.
6. **Deadline**: Granted short resource window; UTC 2026-09-24T16:29:20.673Z–2026-09-24T16:29:25.655Z, controller wall 4.981626 s. Both cells completed, root immediately notified to release resource, gate now complete. No follow-on benchmark starts without a separate declaration and execute signal.

## Results and costs

| Case / cores | Bounded04 Makespan | New Makespan | Old / new | Extra DDR old → new, bytes | Constructor seconds | External E0 seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 054 / 5 | 518133 | 211904 | 2.445131 | 196608 → 2515734 | 0.607283 | 2.739122 |
| 050 / 5 | 108160 | 42597 | 2.539146 | 13824 → 521036 | 0.180317 | 0.604848 |

Makespan units are simulated cycles; the ratios compare same-case/same-core solution quality. Scheduled-copy totals rise 1802884→4122010 and 333200→840412 bytes for 054/050. All old/new spill counters are 0; the higher extra DDR therefore records a real cycle/transfer tradeoff and cannot be hidden behind zero-spill wording.

Both diagnostics select overload-list. Case054 splits one 15390-op component overloaded on PIPE_M and PIPE_V into 16 waves/79 Tasks, retains 23 independent components and submits 84 Tasks across 15751 compute operations. Case050 splits one 4011-op component overloaded on both pipes into 10 waves/49 Tasks, retains 22 independent components and submits 54 Tasks across 4555 compute operations. Soft chunking changes neither plan's Task count. Extra official structural readback finds 258/137 cross-core dependency pairs respectively.

The placement compute/gate proxy finish is 176873/37757, while E0 reports 211904/42597. These proxy observations do not prove individual mechanism causality, general performance bounds or optimality. The method's static fair-share trigger and valid Task DAG require separate empirical quality validation.

Actual calls: 2 constructor + 2 external official E0, 0 E1/E2/retries; 2 successes, no failures/timeouts/not_run. The driver ended successfully; all 4 child receipts have exit_code=0 and cleanup_confirmed=true from wait/poll. The frozen process helper does not serialize numeric PIDs, so historical PID numbers are not reconstructed or claimed. This limits PID-level provenance; it does not add a scoring retry.

Constructor wall spans fresh Python startup, graph reading, inherited fallback and new construction, structural validation, plan/diagnostics writing and process exit. External E0 includes result/trace/log creation and exit. Source/coverage audits, ZIP materialization (0.007020250 s), gzip and export remain outside child timers. Old bounded04 used two workers; current batch used one, so these observed walls do not establish controlled execution-speed improvements.

Environment: Apple M5 Pro, 48 GiB, macOS, Python 3.12.13; uv locked dependencies. OMP/OPENBLAS/MKL variables each 1; actual threads/peak RSS not sampled. Host memory free+inactive+speculative proxies before cells are 11209703424, 11103502336 bytes, not process peak RSS or guaranteed allocatable memory.

## Sources, checks and reproduction

- Runner frozen `1d238dedba5380c7d78e17c4b0ccf276300d356b`; `src/q1_benchmarks/overload_probe_e0.py` and `overload_probe_batch.json`. `finite_probe.py` reuses the exact shared-input controller bytes from `77e2234a443a580db1953138d4e5b7fee25774f9`.
- Fixed solver `3c6e41b938c764d207de45584fb526c64f4eb845`; code SHA is distinct from later runner/data commit. Source guard covers the component-overload entry and heavy/sink/bounded/tree/component dependencies, existing helpers, lockfiles, new runner and manifest (13 receipts).
- Old bounded04 originals from `d63001eb01cc254a20bc60cae5e50b1eb1ee2808`, `results/a/q1-bounded-matrix-20260924/20260924T1459Z-bounded400/board-feed.json`; copied bytes checked against old feed hashes. Baselines were not rerun.
- Official code hash `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`, config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`, ZIP `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`. Exact graph/plan/artifact hashes retained per cell.
- Synthetic controller checks exercised the closed gate, first failure → one remaining not_run, fixed-baseline byte export and budget preservation; real solver/E0 calls were 0. Temporary fixture outputs were deleted; check receipts remain in `preparation/`. Original wait gate and explicit EXECUTE transition are preserved by receipts.
- `STRUCTURAL_CHECK.json` separately reapplies official derive and task-order validation to saved plans and original graphs. It calls no constructor/evaluator.
- Board docs/protocol were checked unchanged from previously read root revision; protocol precheck used root `502bb20014ba3455c8224d1aa4fe5ca8ef62e76b` and returned 2/2 eligible. Fixed-Git checks run after data commit using board protocol `--commit` and `bounded_matrix_verify.py`.
- Completed command: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -B src/q1_benchmarks/overload_probe_e0.py run 20260924T1629Z-overload2`. The closed gate and existing batch guard prevent repeating this command.
- Read-only export: `python -B src/q1_benchmarks/overload_probe_e0.py export 20260924T1629Z-overload2`.

No push, PR or central update performed here; root handles publication, mirror and intake. Other graphs/cores, hidden cases, controlled repeated timing and hardware benefits are outside this batch. Following the new disk constraint, any later authorized batch will reuse this completed worktree instead of creating a full checkout.
