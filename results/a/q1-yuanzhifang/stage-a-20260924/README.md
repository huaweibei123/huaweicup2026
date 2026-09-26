# P1 Stage A: antichain packing, Windows, 2026-09-24

This is a public development pilot on eight graphs at four cores, not a held-out or full-100 validation. All 24 one-candidate plans completed successfully under unchanged official E0. No calls were retried. The feed passes local submission/evidence checks for all 24 records; the central board still needs its owner to register and import this source. Local eligibility is not independent rerun or scientific acceptance.

1. **Goal**: compare the fixed component-pack and chain-wave constructors against fixed64-propose, recording official Makespan separately from cold-process end-to-end solver wall. Task: [Issue 98](https://github.com/huaweibei123/huaweicup2026/issues/98), [task card](../../../../tasks/a/Q1-RESEARCH-YUANZHIFANG.md).
2. **Inputs**: frozen graphs 001, 002, 008, 010, 026, 044, 051, 094 and config; input SHA256, all ten official source hashes and their prescribed combined hash are in `protocol.json`. Existing official singlecore results are reused from `results/benchmark-board/official-singlecore-20260924/`, with matching graph/config/source identity. No new singlecore evaluation.
3. **Outputs**: each attempt has the original plan, full unmodified E0 result and trace compressed losslessly as `.json.gz`, official text log, complete process stdout/stderr, and a run receipt. `comparison.csv` has all 24 rows, `summary.json` derived statistics, and `board-feed-20260924T141300Z-stage-a.json` is the submission snapshot. Result/trace gzip hashes and uncompressed hashes are both recorded.
4. **Limits**: 24 solver + 24 external E0 maximum, 0 E1/E2, 20 s per solver, 40 s per external E0, one serial worker, 600 s batch budget, no retry. Actual: 24 + 24, 0 failures/timeouts, 82.9444258 s total, UTC `2026-09-24T14:11:07.438084Z` to `2026-09-24T14:12:30.382673Z`. Baseline runs precede component-pack and chain-wave. No measured score selects parameters or chooses a submitted candidate.
5. **Checks**: source and input hash checks passed before launch; all plan keys and four-core lengths checked; all 24 E0 calls exited 0. Every result/trace gzip was decompressed and compared byte-for-byte before removing only its new uncompressed output. Board precheck: `valid=true`, `eligible=24`, no reported/failed rows. Final fixed-commit precheck receipt is `precheck-fixed-commit.json`. Parent performs structural tests and algorithm interpretation independently; this subagent is exposed to the development hypothesis and is not a blind reviewer.
6. **Delivery**: branch `codex/q1-wave-benchmark-yuanzhifang-20260924`; fixed solver `29a5f96459546a7bcfb2a5f769c33e570ac7dd67`, baseline `4dff90ef699fd51845cf482951e8477066f5f566`, actual benchmark runner and original feed exporter `046c83228c63afe1af6a31edff1f57dbb883a63c`, post-run report-only exporter `c86957a`. Producer session `yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117`, [registration](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5815673553). Parent coordinates PR and central receipt.

## Results

| Case | fixed64 cycles | component-pack cycles | chain-wave cycles |
| --- | ---: | ---: | ---: |
| 001 | 250003 | 58984 | 58984 |
| 002 | 255464 | 261945 | 88110 |
| 008 | 436414 | 123060 | 248154 |
| 010 | 81965 | 29919 | 46290 |
| 026 | 106263 | 42866 | 75692 |
| 044 | 131407 | 124268 | 135220 |
| 051 | 634666 | 607628 | 324823 |
| 094 | 100704 | 27634 | 70331 |

| Method | Mean official singlecore/current ratio (n=8/100) | Solver P50 / P95 / max seconds |
| --- | ---: | ---: |
| fixed64-propose | 1.018052765 | 1.588438 / 2.270589 / 2.359060 |
| component-pack | 2.476489458 | 0.810041 / 1.511328 / 1.552347 |
| chain-wave | 2.055138436 | 0.637840 / 1.015590 / 1.073383 |

P95 uses linear interpolation at `0.95*(n-1)`; ratios are the arithmetic mean of per-case ratios, not a ratio of sums. This small exposed set is not the official 100-case average. Both new methods beat fixed64 Makespan in 7/8 cases, but component-pack regresses on 002 (261945 versus 255464), and chain-wave regresses on 044 (135220 versus 131407). Component-pack has lower cycles on 008/010/026/044/094, chain-wave on 002/051, with a tie on 001. This retrospective comparison does not constitute a measured online portfolio.

Hardware: Windows, AMD Ryzen 5 5600H with Radeon Graphics, 12 logical CPUs, 17,024,741,376 bytes physical RAM, Python 3.12.14, no GPU used. Full OS/version/lock hash are in `protocol.json`. One worker and single-thread settings refer only to this batch. No exclusive host reservation; P2's new batch was coordinated to wait, but other host tasks may be active. No repeated timing trials, peak process RSS measurement, or OS cache flushing; differences are descriptive single-run observations.

Solver timing starts immediately before `subprocess.run` and ends after the process exits, including imports, graph reads, construction, structural validation, plan write and required diagnostics. fixed64's official local Task compilation is included in solver time; it does not invoke a full online `evaluate_scene_a`, E1 or E2 score. Separate E0 timing covers its full CLI/result/trace/log process. Dependency installation is outside the batch and reported: independent `uv sync --locked`, 14 packages, installer reported 43.79 s. No training, compilation, or case-specific offline precomputation. The official 5–10 minutes is a recommendation, not a hard cutoff or the end of efficiency work.

## Reproduction and read-only checks

In a fresh worktree with an absent output directory, use the fixed runner and solver source above. Set `BASELINE_ROOT` to a clean checkout at the baseline SHA and `GRAPH_DIR` to the verified official data directory. Environment paths are local choices; no personal absolute path is embedded in these commands.

```powershell
uv sync --locked
uv run python -X utf8 -B src/q1_yuanzhifang/benchmark.py --baseline-root $BASELINE_ROOT --graphs $GRAPH_DIR
uv run python -X utf8 -B src/q1_yuanzhifang/export_board.py --output results/a/q1-yuanzhifang/stage-a-20260924/board-feed-NEW-UNIQUE.json
uv run python -X utf8 -B src/q1_yuanzhifang/export_board.py --report-only
uv run python -X utf8 -B src/benchmark_board/protocol.py results/a/q1-yuanzhifang/stage-a-20260924/board-feed-20260924T141300Z-stage-a.json --submission
```

The first command after environment sync is an actual new scoring run and needs its own budget; do not rerun to check these artifacts. The runner refuses an existing output directory, and exporters refuse existing output files. Read-only verification uses only the last command, optionally with `--commit <full artifact SHA>`. `--report-only` derives CSV/summary from existing receipts and refuses to overwrite them; it performs no scoring.

The initial full worktree checkout failed for C-drive space and Git removed the failed directory. The successful setup uses sparse checkout and an independent environment on another local drive. No other worktree/process was modified or stopped. `dot_clean` is unavailable on Windows; the output metadata scans found no `._*`, `.DS_Store`, or `__MACOSX` files/directories.

All failures and negative results are retained (there were no execution failures). Remaining work: parent interpretation, scientific review, and central source registration/receipt; no claim of board visibility or acceptance is made here.
