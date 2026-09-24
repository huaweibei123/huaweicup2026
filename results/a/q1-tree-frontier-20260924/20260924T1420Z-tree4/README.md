# P1 weighted subtree-frontier: four frozen development cells

1. **Goal:** expose parallel reduction subtrees in a connected in-tree while
   keeping a short final tail, and record the constructor's actual fallback.
2. **Inputs:** solver `40c3c093d15ac6bd57f1f0b06472c8a09e1e7d79`, runner
   `5d5c4ef59c6f5e36ede44a3317782842a8812b7f`; cases 002/008/010/051, four cores.
   All use the frozen official source/config/input bytes. Baseline and fixed64
   outputs are reused from `6664a63adc3464d28d1f835d907cdeaea23e6b35`.
3. **Outputs:** board-v1 feed, comparison, per-cell exact plans, full official
   results and traces as lossless gzip, run receipts, diagnostics and logs;
   exact singlecore baseline copies and selected fixed64 source rows.
4. **Limits:** 4 constructor + 4 external E0 starts maximum; one active cell;
   30/60-second timeouts, no retry/E1/E2/search; stop on unexpected failure.
   The previous eight-cell component-pack experiment was not rerun.
5. **Verification:** four parsed official scene-A successes; 4 solver/4 E0,
   zero failed/unrun/retried cells. v1 preflight reports valid, 4 eligible,
   no reported/failed entries. This establishes available evidence, not a
   blind independent algorithm review or a full-100 score.
6. **Execution:** 2026-09-24 14:16:27.265–14:16:28.299 UTC on Apple M5 Pro,
   48 GiB RAM, macOS 27 arm64, locked Python 3.12.13. P2 reported finished;
   Q3 may have had a trailing single-worker run. No exclusive-host performance
   claim. Run ID is an identifier; receipts hold exact actual UTC times.

## Complete results

Makespan is in simulated cycles; extra DDR and spill are bytes. Displayed
wall times are rounded; original precision is retained in JSON.

| Case | Actual mechanism | Makespan | Existing fixed64 | Official singlecore | Baseline speedup | Extra DDR | Spill | Solver wall s | External E0 wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 002 | tree-frontier | 85702 | 255464 | 261945 | 3.0565 | 21504 | 0 | 0.076735 | 0.232904 |
| 008 | component-pack | 123060 | 436414 | 487605 | 3.9623 | 0 | 0 | 0.075027 | 0.176389 |
| 010 | component-pack | 29856 | 81965 | 86969 | 2.9129 | 96768 | 0 | 0.038379 | 0.125341 |
| 051 | component-pack | 607628 | 634666 | 607628 | 1.0000 | 0 | 0 | 0.040787 | 0.232451 |

All four beat this fixed64 version. This does **not** mean all beat historical
best solutions: case051 remains much worse than the prior 336057-cycle
profile-refinement result.

- **002:** 7 disjoint frontier packets, 4 worker Tasks and one 6-operation
  tail Task; tail pipe work is 216 cycles. The previous one-Task component
  plan gave 261945. The new plan gives 85702 with zero spill and only 21504
  extra DDR bytes. It is 2486 cycles (about 2.819%) below the historical
  88188-cycle refinement, whose extra DDR was 1118208 bytes. The historical
  confirmation is in `results/a/q1-profile-refine-20260924/case002/summary.json`
  at solver source commit above. That old procedure takes an existing seed;
  its stage wall excludes seed production and must not be compared as a
  complete raw-graph solver runtime against this 0.0767-second construction.
- **008/010:** already have 108/36 weak components, so the wrapper deliberately
  selects the frozen component-pack mechanism. `parameters.selected` and
  diagnostics record this; the feed additionally identifies the selected
  child algorithm/source SHA. These are not evidence that the tree splitter
  improved those graphs.
- **051:** one weak component is not an in-tree forest, so fallback uses only
  one core. It equals singlecore 607628 but loses to historical refinement
  336057 (`results/a/q1-profile-refine-20260924/case051/summary.json`). A more
  general legal decomposition remains necessary.

## Structural inspection and measurement boundary

Read-only source inspection agrees with the structural argument: outdegree at
most one means rooted predecessor subtrees are nested or disjoint; maximal
subtrees beneath the threshold form an antichain, and no residual tail node
can precede a selected subtree node. Thus every crossing edge enters the
tail. Per-core ordering adds only worker-to-tail edges. This inspection is
separate from performance; it does not prove memory safety, balance, DDR
monotonicity or optimality. This agent inherited the parent design and is not
a blind reviewer.

Each solver timer covers fresh process launch, graph read, the fallback
constructor/validation, tree logic, plan/diagnostics publication and exit.
The external official E0 timer includes result/trace/log generation and exit.
The OS file cache was not flushed. Source/hash validation, exact ZIP byte
materialization (0.002148 s shared), gzip and board export are separate
benchmark setup/postprocessing, not hidden online score calls. No training,
cloud/GPU execution or case-specific offline algorithm precompute occurred.

Source and runner bytes were frozen and verified before execution. The
exporter checked reused baseline and fixed64 result SHA256 and read the actual
historical result Makespan. Successful CLI exit was not used alone: result
existence, valid JSON, positive Makespan, scene A and four-core identity were
checked. Complete official JSON bytes were only losslessly compressed.
Public stdout/stderr replaces personal workspace/temporary input roots by
labels; this derivation is recorded in each run receipt.

## Execution record

```sh
uv sync --locked
uv run python -B src/q1_benchmarks/tree_frontier_e0.py run 20260924T1420Z-tree4
uv run python -B src/q1_benchmarks/tree_frontier_e0.py export 20260924T1420Z-tree4
```

These are the original commands, not authorization to rerun. `run` refuses an
existing batch. `export` and board preflight execute no evaluator. Preflight
used the shared main-branch `src/benchmark_board/protocol.py`, because the
algorithm's base predates the board implementation, with this checkout as
`--repo`. `PRECHECK.json` preserves the actual successful output.
