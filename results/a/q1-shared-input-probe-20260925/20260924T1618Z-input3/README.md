# P1 shared-input budget: frozen three-cell probes

Producer: delegated P1 benchmark agent for `nikolastarx/s-6607cb2735304751b36662035723372b`.
Task: [Issue33](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5815486806).
Branch: `codex/q1-shared-input-probe-e0-20260925`.

1. **Goal**: Measure the fixed shared-input construction on 044/046/090 × requested 5 cores, comparing official quality and DDR with previously frozen bounded04 originals. The three graphs were preselected mechanism probes; no all-case generalization or online scorer selection is claimed.
2. **Inputs**: Read-only official ZIP members checked against the source manifest, original config and official code. Algorithm `288dd520caa5c7baaa1413e4021eb2d4221b6e66`, entry `src/q1/shared_input_budget.py`, input_budget_bytes=262144, activation_bytes=524288, max_phases=32. Static metadata for at most K active-core configurations belongs to the constructor timer. The bounded constructor is invoked once by the algorithm; E0 is external only.
3. **Outputs**: Complete official two-field plans, full result and trace as lossless gzip, original official.log, diagnostics, child stdout/stderr and process receipts in `cells/`. `board-feed.json` contains 3 new v1 attempts. `references/` preserves exact old bounded plans/results and official singlecore evidence. `comparison.json`/CSV, `STRUCTURAL_CHECK.json`, `precheck.json` and preparation receipts make scope and verification traceable.
4. **Limits**: At most 3 constructor + 3 external E0 calls; 1 worker; constructor 30 s / E0 90 s / batch 420 s; first failure stops; 0 retries/E1/E2. No baseline reevaluation, other graphs/candidates, cloud/GPU or central service changes. The runner was prepared with wait-P2 gate; root's explicit release after P2/P3 completion is preserved in `batch.json.execution_authorization`. Runtime gate now complete, preventing accidental repeat.
5. **Acceptance**: 3/3 successful E0 scene A, requested 5 cores, positive numeric Makespan; full compute-node coverage; official derive/task-order check; saved-plan active-core count and absence of cross-core Task dependencies checked. Working-tree protocol precheck 3/3 eligible. Independent scientific acceptance remains distinct from delegated execution and byte precheck.
6. **Deadline**: The explicit short resource window. Execution UTC 2026-09-24T16:18:29.886Z–2026-09-24T16:18:31.523Z, controller wall 1.636703 s. Owned child processes completed, resource release reported immediately; no further score run follows automatically.

## Official quality and measured cost

| Case / requested cores | Bounded04 Makespan | New Makespan | Old / new | Extra DDR old → new, bytes | Spill old → new, bytes | Active cores | Tasks | Constructor seconds | External E0 seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 044 / 5 | 132892 | 64624 | 2.056388 | 6196032 → 1051488 | 2474432 → 0 | 2 | 10 | 0.078590 | 0.182366 |
| 046 / 5 | 131039 | 103846 | 1.261859 | 5013664 → 3143456 | 1292064 → 0 | 4 | 20 | 0.075345 | 0.130865 |
| 090 / 5 | 542638 | 319844 | 1.696571 | 21724704 → 8838528 | 13130784 → 0 | 5 | 60 | 0.074526 | 0.240996 |

Makespan is simulated clock cycles, and old/new is a same-case quality ratio. Every declared probe improves both Makespan and total extra DDR. Spill becomes zero in these three saved results. This is evidence for the combined static core-selection/window construction on this finite set; it does not isolate the effect of each component or establish a general spill certificate or optimum.

Scheduled-copy totals decrease 7171488→2026944, 6075136→4204928 and 23953056→11066880 bytes for 044/046/090. The original requested 5-core output contract is preserved with unused core schedules empty: actual active cores are 2/4/5. This must not be reported as a 2/4/5 requested-core experiment or mixed into those board cells.

The selected static proxy cycles are 40984/70280/195068, compared with actual E0 cycles 64624/103846/319844. Their ordering motivated the choices; they are neither exact performance estimates nor universal lower bounds. For these probes only, selected partition-copy proxy bytes equal observed extra DDR because observed spill is zero. Diagnostics retain every static configuration and the chosen one; they contain no extra official evaluations.

Actual calls: 3 fresh constructor processes + 3 independent official E0 processes, 0 E1/E2/retries; 3 successes, 0 failed/timeout/not_run. Every child exit and cleanup_confirmed is preserved. Constructor wall includes read/validation, static metadata for all active-core choices, selected base construction, input windows, structural validation, plan/diagnostics writing and exit. E0 wall includes evaluation and complete result/trace/log output through exit. Source checks, ZIP preparation (0.002810958 s), gzip/export and extra structural audits are outside child timers.

Machine: Apple M5 Pro, 48 GiB, macOS, Python 3.12.13, uv locked dependencies. OMP/OPENBLAS/MKL environment variables each set to 1; actual threads and process peak RSS not sampled. Host free+inactive+speculative proxies before cells: 11145052160, 11086168064, 11084759040 bytes. The host was shared/nonexclusive; old bounded04 used two workers, this batch one, so wall values are observations rather than a controlled program speedup.

## Sources and checks

- Frozen runner/manifest: `77e2234a443a580db1953138d4e5b7fee25774f9`; entry `src/q1_benchmarks/shared_input_probe_e0.py`, `shared_input_probe_batch.json`, reusable `finite_probe.py`. Source receipts check the entry and its three algorithm dependencies against `288dd520caa5c7baaa1413e4021eb2d4221b6e66`, helper/lock bytes, controller/wrapper/manifest and tracked source cleanliness.
- Old bounded04 evidence: `d63001eb01cc254a20bc60cae5e50b1eb1ee2808`, `results/a/q1-bounded-matrix-20260924/20260924T1459Z-bounded400/board-feed.json`. Each old attempt and saved plan/result hash remains in `comparison.json`. No prior score was recomputed.
- Official source `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`; config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`; input archive `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`. Per-graph/plan/diagnostic/process-log hashes are in run receipts.
- Preparation syntax/declaration tests, wait-P2 gate refusal, first-failure dispatch fixture and read-only export fixture passed with zero real constructor/evaluator calls. Synthetic fixture data was deleted; it is excluded from this feed. Their check receipt and source receipt are in `preparation/`.
- Additional official `derive_multicore_plan` and `validate_task_order` on saved plan bytes and original graphs passed all three: 1364/992/1664 compute operations, 10/20/60 Tasks, 0 cross-core dependency pairs. No solver/E0 was called by this check.
- Board protocol checker used from current root checkout (HEAD `502bb20014ba3455c8224d1aa4fe5ca8ef62e76b`), because the frozen source worktree predates that module: `precheck.json`, valid with 3/3 eligible. Fixed-Git byte and protocol checks are performed after data commit.

Execution command (already completed; do not repeat to repair metadata):

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -B src/q1_benchmarks/shared_input_probe_e0.py run 20260924T1618Z-input3
```

Read-only reexport: `python -B src/q1_benchmarks/shared_input_probe_e0.py export 20260924T1618Z-input3`. Fixed-Git verification uses the board protocol with `--commit` and `src/q1_benchmarks/bounded_matrix_verify.py`.

Parent handles integration, publishing, mirror and board intake. No push, PR, external message or central write was performed by this agent. Other graphs/cores, full-method averages, controlled latency repetitions, hidden cases and real hardware performance remain outside this batch.
