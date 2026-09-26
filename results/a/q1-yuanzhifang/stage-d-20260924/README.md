# Stage D: individual frontier subtree Tasks

Task [Issue98](https://github.com/huaweibei123/huaweicup2026/issues/98). Same producer session `yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117`.

Five new solver + five external E0 calls; all successful, no timeout/retry/E1/E2. T0 2026-09-24T15:55:48.271144Z; T1 2026-09-24T15:57:07.050112Z; batch 78.778999 s. One worker; solver cap 30 s, E0 cap 90 s, batch cap 600 s. The Stage D budget is sealed. All five Makespans regress relative to the frozen Stage C packed-frontier plans.

Solver `ec766d18ff0d20d813bd1d9b7c1d7faf1067cde1`; actual runner and exporter `0d0203700fb507cdd4066a21631a42461d4c0a80`. Algorithm `q1-fork-stage-frontier`, variant `chain-atomic-grain4-unit-tasks`, grain=4, frontier_tasks=unit. The whole frontier subtree becomes one Task; the reduction tail remains a whole Task. No parameter search or online scoring.

## Comparison with stored Stage C results

Stage C source artifact commit `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a`, new-family packed-frontier results only; exporter checked the fixed feed and results against Git bytes and graph/config/official identity. No old baseline was rerun. The Stage C bounded-016 timeout remains a timeout; it is not used as a numeric comparison. Official singlecore denominators are also reused, with zero new singlecore calls.

| Case | k | C cycles | D cycles | Increase | D solver s | D E0 s | C extra bytes | D extra bytes | D Tasks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 051 | 2 | 357955 | 425966 | 19.000% | 0.402197 | 0.991447 | 9045258 | 9045718 | 312 |
| 051 | 4 | 254308 | 333358 | 31.084% | 0.382869 | 0.943319 | 9045350 | 9045718 | 312 |
| 051 | 5 | 253856 | 317741 | 25.166% | 0.476543 | 1.776600 | 9045396 | 9045718 | 312 |
| 016 | 4 | 3241338 | 4232514 | 30.579% | 1.314164 | 60.936190 | 119555344 | 119560208 | 3965 |
| 024 | 4 | 1072818 | 1401810 | 30.666% | 0.690289 | 8.069571 | 39327448 | 39329048 | 1313 |

New solver wall sum 3.266063 s, median 0.476543 s. These cold-process observations are separate from simulated quality; prior Stage C timing was a different time window on the same host, with caches not flushed and no exclusive reservation. They do not establish a general speedup guarantee.

051 now has 312 Tasks at every measured core count; 016/024 have 3965/1313. All five have zero spill. Extra DDR rises slightly instead of decreasing. This five-point result rejects the hoped-for quality improvement of the frozen unit policy on this panel; it does not uniquely attribute regressions to gates, FIFO, or DDR, and it does not prove all possible finer partitions are inferior. Whole result/trace evidence is available for a separately scoped static analysis.

## Evidence and reproduction

Original two-key plan, diagnostics, raw stdout/stderr/log, run receipt, full official result and trace are retained. Large result/trace bytes are losslessly gzip-compressed with raw and compressed SHA-256 in each run. The official ten source files and all three graphs/config were checked before execution. `events.jsonl` contains every launch/finish and `completion.json` contains final counts. Peak RSS is uninstrumented; CPU/RAM, locked environment, worker/thread settings and development exposure are in protocol/feed.

`board-feed-20260924T155800Z-stage-d.json` is board-submission-v1, five records. Filesystem precheck passed valid/submission=true, eligible=5. Fixed Git-object precheck follows after the artifact commit. Central intake and scientific acceptance are separate; no central write or new Issue was sent.

Run command from a clean checkout of the actual runner, with verified raw input and a nonexistent output directory:

```powershell
python -X utf8 -B src/q1_yuanzhifang/benchmark_d.py --graphs <official-data-directory> --execute
```

A new execution requires a new authorized experiment budget. Without --execute, the script only preflights and consumes zero scorer calls. This completed output directory rejects reuse. Read-only report commands were:

```powershell
python -X utf8 -B src/q1_yuanzhifang/export_d.py --output results/a/q1-yuanzhifang/stage-d-20260924/board-feed-20260924T155800Z-stage-d.json
python -X utf8 -B src/benchmark_board/protocol.py results/a/q1-yuanzhifang/stage-d-20260924/board-feed-20260924T155800Z-stage-d.json --submission --commit <artifact-SHA>
```

Windows has no dot_clean; scoped metadata scan is empty. Raw Windows CRLF is preserved using `* -text`; diff whitespace check uses per-command cr-at-eol rather than editing official bytes.

Fixed Git-object precheck passed at artifact commit `a7f51f2d5ca7d735899addd8bc14900045484fc3`: valid/submission=true, records=5, eligible=5, no reported/failed rows. Receipt: `precheck-fixed-a7f51f2.json`.
