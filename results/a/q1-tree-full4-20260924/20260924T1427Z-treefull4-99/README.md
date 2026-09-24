# P1 factor4 coverage extension — stopped on case014 E0 timeout

**This batch did not complete 100-case coverage.** It produced 12 new official
successes, one timeout, and 86 explicitly unrun rows. Reusing the earlier
case002 gives 13/100 successful cases for this fixed method. No retry or
automatic continuation occurred; missing cases are not assigned zero scores.

1. **Goal:** test generalization and expose negative cases for the fixed
   factor4 direct construction, without online selection or parameter search.
2. **Inputs:** solver `409886dd4b17b589643d3f5a13af9e94a9783d73`, runner
   `c0fd34b5d9363a313e2cff9581d667888061db7a`, all cases 001–100/four cores
   except already measured 002. Constructor and `component_pack.py` dependency
   bytes matched solver Git blobs; all tracked worktree files matched runner
   HEAD; all official code/config/archive hashes matched the source manifest.
3. **Outputs:** `board-feed.json` contains only the 99 new planned rows:
   12 ok / 1 timeout / 86 not_run. Per-cell receipts, available plans/results,
   exact baseline references, logs and complete successful traces are retained.
   `full100-comparison.json/.csv` and `full100-summary.json` describe the
   requested 100-case grid with exact old case002 reuse, including unknowns.
4. **Limits:** new upper bounds 99 solver/99 E0, 1200 seconds for the batch,
   one active cell, per-process 30/60-second limits, no E1/E2 or retry. Stop at
   the first unexpected failure. **Actual:** 13 solver and 13 E0 starts;
   12 successes and one E0 timeout. Earlier budgets remain sealed.
5. **Verification:** v1 preflight reports `valid:true`, 99 records, 12 eligible,
   87 reported/failed. All failed/unrun statuses remain in the feed. This is
   format/available-byte verification, not independent algorithm acceptance.
6. **Execution:** 2026-09-24 14:25:13.212–14:26:33.187 UTC; Apple M5 Pro,
   48 GiB RAM, macOS 27 arm64, Python 3.12.13 with locked dependencies. P2/Q3
   reported stopped before execution; no exclusive-host reservation or
   controlled latency claim. No Colab/GPU used.

## Failure: what is measured and what remains unknown

Case014 constructor completed in **0.346023875 seconds**, exit 0, and emitted
a structurally validated plan. Its external official E0 ran **60.023412083
seconds** and timed out. The runner sent SIGKILL to the process group, waited
for the direct child, and recorded exit **-9** and `cleanup_confirmed:true`.
The batch then marked 015–100 `not_run` and exited. It was not resumed.

At the time of preservation:

| Artifact | Actual state |
|---|---|
| `case_014_multicore_res.json` | 347153 bytes; SHA256 `ec12cf31e850070bf0c683d1b67fe67f86b7ee077daabbd538ac6a689bd1c88a` |
| `diagnostics.json` | 952 bytes; SHA256 `116775d6bcfb26341ef8eaa7c5141c0dcfc74b31d508545e9a1c81c96e261734` |
| E0 stdout / stderr | Both present, 0 bytes |
| result / trace / official text log | Not produced; no partial file was present |
| Final Makespan / DDR / spill | Unknown; not inferred from the plan |

Diagnostics identify component-pack fallback: 35,705 compute ops in 1,340
weak components became four Tasks with 8890/8888/8969/8958 compute ops. Their
PIPE_M work is approximately balanced (4,308,312 / 4,308,312 / 4,306,044 /
4,303,080 cycles). These are structural/proxy observations, not E0 progress
measurements or a proof of the timeout cause.

No profiler stack, evaluator phase timing, CPU or peak RSS was sampled. The
available evidence therefore cannot identify whether time was spent in local
compilation, spill handling, global simulation, or another E0 stage. An
attribution to a particular hotspot would be a guess. In particular, the fast
constructor is not evidence that official evaluation of its plan is cheap.
No profiling replay was attempted under this closed budget. A future targeted
diagnostic or revised construction needs a separate fixed experiment.

## Partial observations only

The successful prefix is cases 001–013, with 002 reused from its original
attempt. Its arithmetic mean of official singlecore / candidate Makespan is
**3.0657754215 over n=13**, while fixed64 on those same 13 inputs averages
0.9915307306. All 13 beat this fixed64 version; 12 beat singlecore and one
equals it. All 13 show zero spill. **This biased completed prefix is not the
100-case mean, and says nothing about the 87 unavailable outcomes.**

Of those successes, 12 select component-pack and only 002 selects tree-frontier.
The newly tested 012/013 four-core Makespans are 17253/66982. Complete per-case
values and actual mechanism choices are in the JSON/CSV, preserving failures
and unrun cases rather than dropping them from the report.

Successful-constructor wall observations span 0.03863–0.13149 seconds (median
0.04143); case014's successful constructor separately took 0.34602 seconds
before its E0 timeout. These are one observation per graph on a non-exclusive
machine, not P95 or controlled repeated latency. Solver wall includes process
startup, graph reading, construction, validation and plan/diagnostics writing;
independent E0 wall is separate. OS file cache was not flushed. ZIP
materialization, source verification, gzip and export are recorded benchmark
setup/postprocessing, not online scoring or hidden training.

## Case002 reuse and provenance

Source commit `bf65aaca608e0c41493eb29c8482712c0a8d2c73`, feed
`results/a/q1-tree-fine-20260924/20260924T1422Z-treefine1/board-feed.json`.
It has the **same solver SHA, factor 4, input/config/official identity, and four
cores**, but its original run/attempt/timestamps and observed timings remain
unchanged. Exact original feed, plan, result, run, log, trace, baseline and
diagnostics are preserved in `references/reused-case002/`; source paths and
hashes are recorded in the aggregate summary. It is not exported again as a
new board attempt and costs **zero new solver/E0 calls** in this batch.

Other baselines and fixed64 comparisons are reused from
`6664a63adc3464d28d1f835d907cdeaea23e6b35`, with result hashes and values checked.
Raw official outputs are complete and only losslessly gzipped. Process
stdout/stderr replace personal roots by public labels as documented in
receipts. No result JSON was rewritten to satisfy the board schema.

## Commands and closed status

```sh
uv sync --locked
uv run python -B src/q1_benchmarks/tree_full4_e0.py run 20260924T1427Z-treefull4-99
uv run python -B src/q1_benchmarks/tree_full4_e0.py export 20260924T1427Z-treefull4-99
uv run python -B src/q1_benchmarks/tree_full4_report.py results/a/q1-tree-full4-20260924/20260924T1427Z-treefull4-99
```

These record original execution, not permission to restart. `run` refuses
existing directories. Export/report/preflight call no solver/evaluator.
`PRECHECK.json` retains all 87 noneligible reasons. Feed size is 734990 bytes,
below the 8 MiB bound, so it requires no shards. Board preflight used the shared
main-branch checker with this checkout as `--repo`; the old algorithm base
predates that checker. Data delivery, board admission and scientific review
remain separate states.
