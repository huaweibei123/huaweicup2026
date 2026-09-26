# Stage C: fork-stage-frontier / bounded comparison

Task: [Issue 98](https://github.com/huaweibei123/huaweicup2026/issues/98). Session: `yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117`.

Measurement UTC: 2026-09-24T15:24:00.501762Z to 2026-09-24T15:27:07.969211Z; 187.467937 s. Exactly 24 solver + 24 external E0, 0 E1/E2/retries, one worker; 23 successful official results and one E0 timeout. All 24 solvers succeeded. No unrun scenarios.

Solver `0bf12cfe3164b155b02cc85896dabdfee72f9d37` / `q1-fork-stage-frontier` / `chain-atomic-grain4`; captain baseline `05f8fa0f7e52f5914f14815f6bdbcb851b631556` / `q1-bounded-component-tasks` / `frontier-then-independent-chunks` (factor 4, trigger 4096, chunk 1024). Actual runner `0179332f79563a0bf378f05c50dad3eef6400383`. Report-only exporter fix `712500e5ca5e13698e7870a33a8260eb1f2373f2` preserves timeout null reasons; it does not rerun or alter raw solver/evaluator outputs.

## Per-scenario cycles and solver wall

| Case | k | Bounded cycles | New cycles | Bounded solver s | New solver s | New/old extra DDR bytes |
|---|---:|---:|---:|---:|---:|---:|
| 051 | 2 | 607628 | 357955 | 0.421255 | 0.742479 | 9045258 / 0 |
| 051 | 3 | 607628 | 291222 | 0.712791 | 0.816545 | 9045304 / 0 |
| 051 | 4 | 607628 | 254308 | 0.598893 | 0.584106 | 9045350 / 0 |
| 051 | 5 | 607628 | 253856 | 0.441886 | 1.062300 | 9045396 / 0 |
| 002 | 4 | 73544 | 73544 | 1.266661 | 1.647514 | 76800 / 76800 |
| 008 | 4 | 123060 | 179018 | 0.472268 | 0.598758 | 7962624 / 0 |
| 016 | 4 | timeout | 3241338 | 2.256294 | 1.532345 | 119555344 / unknown |
| 024 | 4 | 2555343 | 1072818 | 1.029275 | 0.919645 | 39327448 / 0 |
| 044 | 4 | 124268 | 81301 | 0.558777 | 0.415657 | 3267104 / 5678624 |
| 048 | 4 | 222220 | 161592 | 0.624122 | 0.539981 | 2022490 / 0 |
| 071 | 4 | 18919 | 20194 | 0.481285 | 0.546470 | 603796 / 0 |
| 080 | 4 | 111314 | 91774 | 0.784524 | 0.471160 | 2666496 / 4190208 |

Among 11 scenarios where both E0 calls completed, new method wins 8, loses 2, ties 1. The matched k4 subset has n=8 (051, 002, 008, 024, 044, 048, 071, 080), mean singlecore/multicore ratio 1.923882852 -> 2.306405916. This selected development subset does not establish the required full-100 mean or prove dominance.

051 new speedups at k2/3/4/5 are 1.697498289 / 2.086476983 / 2.389338912 / 2.393593218. The k5 plateau, 008/071 regressions, and increased extra DDR on 051/016/024/048 are retained. Quality improvements can trade against solver wall or bytes; separate metrics are in comparison.csv.

## Timeout and evidence

Bounded case016 k4 constructed a plan in 2.256294100 s. Its external E0 reached the frozen 90 s cap (observed 90.176585400 s) and was terminated/reaped by subprocess.run. No final Makespan is claimed for this attempt; plan, diagnostics, stdout/stderr and run receipt remain. New case016 completed E0 in 23.061675500 s at 3241338 cycles. No retry was performed.

The full official result and trace bytes for successful cases are preserved losslessly as gzip; run receipts contain raw and compressed SHA-256. Plans, diagnostics, complete stdout/stderr and text logs remain. Inputs/config and all ten official source files were checked against source-manifest.json before running, and solver dependencies checked against their frozen Git objects. Reused official singlecore results incur 0 new singlecore evaluation calls. `events.jsonl` records every launch/finish; `completion.json`, `rows.json`, `protocol.json`, `coordination.json` and `summary.json` record the separate batch.

Public development exposure, static prechecks, process/thread policy, hardware and timings are in protocol.json and the feed. Peak RSS is uninstrumented. Cold processes do not imply flushed OS caches or exclusive host reservation. Windows has no dot_clean; output metadata scans must be empty.

## Reproduction and board delivery

From an isolated checkout of the actual runner commit (and independent clean bounded checkout at its fixed SHA), with a fresh/nonexistent output directory and manifest-verified raw graphs:

```powershell
python -X utf8 -B src/q1_yuanzhifang/benchmark_c.py --baseline-root <bounded-checkout> --graphs <official-data-directory> --solver-commit 0bf12cfe3164b155b02cc85896dabdfee72f9d37 --execute
```

Execution is a new benchmark requiring its own authorized budget. Default invocation without --execute performs source/input preflight only. The Stage C budget is sealed.

Read-only export command (new output only):

```powershell
python -X utf8 -B src/q1_yuanzhifang/export_c.py --output results/a/q1-yuanzhifang/stage-c-20260924/board-feed-20260924T153000Z-stage-c.json
python -X utf8 -B src/benchmark_board/protocol.py results/a/q1-yuanzhifang/stage-c-20260924/board-feed-20260924T153000Z-stage-c.json --submission --commit <artifact-full-SHA>
```

The first precheck was issued while the asynchronous exporter was still running and reported missing feed; no evaluator was invoked. After export completion, filesystem precheck passed valid/submission true, records 24, eligible 23; the single timeout is retained and excluded from optimum selection. Fixed Git-object precheck receipt follows in a subsequent commit. Central board intake and scientific acceptance are separate states; no central API writes were made.

Fixed Git-object precheck succeeded at artifact commit `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a`: valid/submission true, 24 records, eligible 23; receipt `precheck-fixed-88e95e2.json`. Raw Windows CRLF is intentionally retained with `* -text`; ordinary diff --check reports these line endings as trailing whitespace. The same check with the per-command `core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol` passes; no raw output bytes were normalized.
