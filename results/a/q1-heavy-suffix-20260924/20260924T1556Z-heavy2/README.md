# P1 heavy-component suffix: two frozen official probes

Producer: delegated P1 evaluation agent for `nikolastarx/s-6607cb2735304751b36662035723372b`.
Task: [Issue33](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5815486806).
Branch: `codex/q1-heavy-suffix-e0-20260924`.

1. **Goal**: Evaluate the fixed dominant-component suffix construction on049/k5 and088/k5, comparing official Makespan and DDR with previously frozen bounded04 plans. These two preselected mechanism probes are not an all-case score.
2. **Inputs**: Read-only `data/raw/a/official-cases.zip`, exact `data/case_049.json` and `data/case_088.json` bytes verified against `docs/a/source-manifest.json`; unmodified official P1 code and config. Algorithm `4c8c58866cc8ffa5a3fa468adc727f8a0800bd0f`, entry `src/q1/heavy_suffix.py`; fixed dominant_percent80/max_rounds64/max_sinks64. All dependencies and runner bytes have receipts in `batch.json`.
3. **Outputs**: `cells/` contains actual plan, complete E0 result and trace in lossless gzip, original `official.log`, diagnostics, process outputs and run receipts. `board-feed.json` is board-submission-v1; `comparison.json`/CSV preserve paired quality and timing. `references/` holds exact prior bounded04 plan/result and official singlecore bytes. `STRUCTURAL_CHECK.json` is an additional read-only legality check.
4. **Limits**: One worker; at most2 constructor+2E0 calls; constructor30s/E090s/batch300s; stop at first failure; zero retries/E1/E2. No cloud/GPU, sink8 execution, central-site changes or baseline reevaluation. Parent confirmed P2/P3 had no active scores and granted this window; host was not exclusively reserved.
5. **Acceptance**: Exactly the two declared cells, complete compute-node coverage, official derive/task-order checks, successful E0 with sceneA/5cores and positive numeric Makespan, complete original evidence and hashes, protocol preflight. Both cells passed; this is delegated measured validation, not blind scientific acceptance or a universal quality theorem.
6. **Deadline**: This explicitly authorized resource window; execution2026-09-24T15:56:16.955Z–15:56:18.645Z (UTC), controller wall1.689775s including preflight/preparation. No further experiment is authorized by this result.

## Quality and costs

| Case / simulated cores | Old bounded04 Makespan | Heavy-suffix Makespan | Old / new | Extra DDR old → new, bytes | Spill old → new, bytes | Constructor seconds | External E0 seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 049 /5 | 160260 | 62114 | 2.580095 | 0 →593240 | 0 →0 | 0.132651 | 0.453237 |
| 088 /5 | 202791 | 92700 | 2.187605 | 221184 →2029154 | 0 →0 | 0.129889 | 0.454409 |

Makespan is simulated cycles. The ratio compares same-case/same-core official quality, not program speed. Scheduled-copy totals increase152540→745780 bytes and2050982→3858952 bytes respectively. Improvement in Makespan therefore comes with higher additional DDR; zero spill does not mean zero transfer or dominance on every objective.

Both constructors selected `heavy-suffix`.049 has4303 compute operations:3952 in the dominant component and351 in minor components,10 waves and47 Tasks; PIPE_V is the dominant total-work pipe.088 has3309 compute operations:2798 heavy/511 minor,10 waves and43 Tasks; PIPE_M is dominant. These diagnostics explain what was submitted, not a proof that each mechanism independently caused the measured gain.

Actual budget consumption:2 constructor launches,2 independent external E0 launches,0E1/0E2/0retries. Every child exited successfully and cleanup was confirmed. Fresh Python3.12.13 processes on Apple M5 Pro/macOS, locked dependencies, OS cache not flushed. Constructor wall includes reading the graph, the existing fallback construction, the new construction, official structural validation, output/diagnostics publication and process exit. E0 wall is separate and includes result/trace/log output and exit. Runner checks, gzip and export are outside child timers. Old bounded04 timing came from a two-worker shared batch; these durations are observations, not a controlled speedup claim.

Memory snapshots before the two cells gave free+inactive+speculative proxies of11364073472 and11588845568 bytes. This is host availability sampling, not process peak RSS.

## Sources, validation and reproduction

- Frozen runner: `09851e40d79dfded6afebd97ceb2fa711b0ce6b8`, `src/q1_benchmarks/heavy_suffix_e0.py`.
- Comparison originals: `d63001eb01cc254a20bc60cae5e50b1eb1ee2808`, `results/a/q1-bounded-matrix-20260924/20260924T1459Z-bounded400/board-feed.json`; original bounded solver05f8. No prior plan or score was recomputed.
- Official source hash: `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`; config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`. Exact graph/plan/source hashes and argv are in the receipts.
- Main board docs were read at `b467cbc96df9e826551fa33c7599257c5f099752`. `PRECHECK.json` reports2/2eligible using the main checkout's read-only protocol checker (this algorithm worktree does not contain that module). No evaluator call is made by preflight.
- `STRUCTURAL_CHECK.json` independently reapplied unmodified official `derive_multicore_plan` and `validate_task_order` to the saved plans and original ZIP bytes: passed both. It is a structural check, separate from the actual complete E0 results.
- Execution command was `python -B src/q1_benchmarks/heavy_suffix_e0.py run 20260924T1556Z-heavy2`. Existing batch directories cannot be overwritten; do not repeat scoring to repair metadata.
- Read-only reexport: `python -B src/q1_benchmarks/heavy_suffix_e0.py export 20260924T1556Z-heavy2`. Full fixed-Git artifact verification uses `src/q1_benchmarks/bounded_matrix_verify.py` after commit.

No PR or push was performed by this agent. Parent handles integration, publication, mirrors and board submission. Untested: other graphs/cores, controlled repeated timing, hidden cases, general optimality and real-device performance.
