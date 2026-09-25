# P1 general bridge static probe (2026-09-26)

This is a research-only structural prototype on branch `codex/p1-general-bridge-20260926`, parent HEAD `a1bb4451cd85c46b32bb928d57c81e22cfeca1a6`. The initial static v1 source SHA-256 was `a01a816e4b86992d696e976685bd2678f9486fd48f7e6738071a15a4e8d9a005`, test SHA-256 `101810f80d23d3aa22b4e7da057cf8c09c8745892be61f9e13269eefc462c705`. The later queue-screen v2 source SHA-256 is `283959aa95d67d66c95b770169eeb1ec5489f8839210ff5b4cc2f2d320da0cef`, test SHA-256 `0c65abf6817529ac5aca33073c3b6d9e24e9efa47664f3ab5bd8eaa6060ab21e`. Initial static construction used Python 3.14.5 on macOS; the later tests and official E0 used locked Python 3.12.13. The prototype and bounded runner were committed and pushed in PR #206.

The constructor reads only the current graph and supplied baseline. It examines all donor Tasks for the existing `branch_aid._witness` X/Y/J certificate, checks exact original Task coverage, ranks positive Task-local Pipe peak reductions, and inserts one X on a different core at a feasible slot. It checks the complete contracted Task data graph plus adjacent same-core order edges for acyclicity, then calls the official `derive_multicore_plan` and `validate_task_order`. The donor, helper, and slot are chosen by the recorded structural key: greatest Task-local Pipe peak reduction, least added static COPY service/bytes, least adjacent helper Pipe work, then stable Task/core/slot IDs. No case ID, saved result, Makespan, or evaluator score enters this rule.

Representative read-only inputs, chosen to include a baseline rejected by the old height rule and a known bridge-shaped larger graph:

| Cell | Original graph in frozen ZIP | Baseline plan source | Graph SHA-256 | Baseline plan bytes SHA-256 |
| --- | --- | --- | --- | --- |
| 068/K5 | `data/raw/a/official-cases.zip:data/case_068.json` | `results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500/cells/068-k5/originals/plan.json` | `dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d` | `b35d39058eb3a812e935a724f8451498cb4861ac108f4be1035d5bbc59adfb8d` |
| 085/K5 | `data/raw/a/official-cases.zip:data/case_085.json` | `results/a/p1-r6-pilot-20260925/official-085-k5/base-plan.json.gz` (decompressed JSON) | `b63169e9cd0f21dc2da6617e7138472e95937465c703b7e4bf4dbc80125ed4f6` | `e7b3e907ec10ef3d5acc55682200735c42c0f38e4b72da1372c2363b7f01c4d8` |

Reproduction from the repository root in zsh:

```sh
python3 -m unittest tests.q1.test_general_bridge_probe -v
python3 -m src.q1.general_bridge_probe --graph <(unzip -p data/raw/a/official-cases.zip data/case_068.json) --base-plan results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500/cells/068-k5/originals/plan.json --cores 5 --output-dir results/a/p1-general-bridge-probe-20260926/068-k5
python3 -m src.q1.general_bridge_probe --graph <(unzip -p data/raw/a/official-cases.zip data/case_085.json) --base-plan <(gzip -dc results/a/p1-r6-pilot-20260925/official-085-k5/base-plan.json.gz) --cores 5 --output-dir results/a/p1-general-bridge-probe-20260926/085-k5
```

The three tests passed. Timed runs with already extracted input files took 0.39 s for 068/K5 and 2.36 s for 085/K5 (`/usr/bin/time -p`, includes Python startup, JSON reads, structural selection, output writes). First unoptimized 085/K5 attempt reached the 10 s soft limit; reusing its quotient Task data edges across insertion slots reduced it to 2.36 s. A local test initially contained a mistaken expected schedule shape; corrected before final passing run. These were development attempts, not evaluator attempts.

| Cell | Static census | Chosen donor → helper/slot | Task-local raw Pipe peak decrease | Extra static COPY | Candidate plan SHA-256 |
| --- | --- | --- | ---: | --- | --- |
| 068/K5 | 61 old Tasks, 29 bridge witnesses, 281 acyclic slots | Task 38/core 0 → core 4/slot 5 | 4,008 cycles | 22,274 B; 381 normalized service cycles | `0b4b64cba1e0000220337bcee60cd94e206526f949ec3ba04cad02fb4d8b2720` |
| 085/K5 | 97 old Tasks, 50 bridge witnesses, 477 acyclic slots | Task 96/core 4 → core 3/slot 19 | 19,216 cycles | 20,738 B; 352 normalized service cycles | `ba9be0e9bea3ea3f23c0eda28c7fa6ce1d5787fa52624da8e54a9c61120cc054` |

Both plans contain exactly the official two keys and pass the official structural plan/order validators. The static COPY account excludes Task compilation and Step2 spill. Raw Pipe work reduction is a selection proxy, not a Makespan prediction. The static construction used zero E1/E0/E2 calls. A separately admitted one-call E0 check of 068/K5 is recorded below; 085/K5 remains unscored. Neither cell contributes to the fixed unified solver's formal 100×5 result.

## Official one-cell falsification: 068/K5

The coordinator admitted one local E0 call on the saved 068/K5 candidate, with no solver, standalone Task compiler, E1/E2, or retry. The locked Python 3.12.13 preflight checked frozen candidate, graph, archive, config, evaluator, and supervisor bytes before dispatch. The official evaluator internally compiled and scheduled the Tasks. Run `20260925T180611Z-068-k5` began at 2026-09-25 18:06:18.323 UTC and ended at 18:06:19.112 UTC; E0 exited 0 in 0.774 s with cleanup confirmed. The run is under `runs/20260925T180611Z-068-k5/`, including `batch.json`, `attempt.json`, the exact graph and plan, original official result, trace, log, and process output. The coordinator separately read back these artifacts and closed the gate.

| Same frozen 068/K5 graph/config/E0 | Makespan cycles | Scheduled COPY bytes | Spill bytes |
| --- | ---: | ---: | ---: |
| Fixed unified parent plan (full500 original) | 131,234 | 5,711,708 | 0 |
| General bridge candidate (one fresh official E0) | 142,142 | 5,733,982 | 0 |
| Candidate minus parent | **+10,908 (+8.3119%)** | **+22,274** | 0 |

The candidate loses despite a 4,008-cycle reduction in the Task-local raw Pipe peak proxy. The 22,274-byte extra COPY exactly matches the structural estimate. The official Task timelines identify the larger timing issue: old Task 38 on core 0 ends at 82,578 and successor Task 42 starts at 83,578. The split finishes the first part of 38 at 73,780, but the new helper Task 62 waits behind core 4's Task 46 until 85,062, ends at 87,013, and the new core-0 continuation Task 61 runs 88,013–94,984. Task 42 consequently starts at 95,084, **11,506 cycles later**. The final core-0 Task 56 starts 10,908 cycles later and has the same 22,159-cycle duration, explaining the final 10,908-cycle Makespan regression. The added COPY bytes and 1,000-cycle cross-core wait further constrain such placements; this single run does not apportion the full regression among those factors.

Result SHA-256 `a5dbf587ee34da887231bf87f0fbc1b913dd204b836b57d53d296100e167852c`; trace `11b94abfc73d1c34f232580cf0f814ba7a6bd03757618fe1142f1900adc08e9a`; log `901c82f9de1236733b278f885cf59492c2442fdf6ba7753e60559c25042c0c6b`. The fixed parent source is `results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500/board-feed.json`, record 068/K5, with plan SHA-256 `b35d39058eb3a812e935a724f8451498cb4861ac108f4be1035d5bbc59adfb8d`. This negative pilot must not be shown as a new unified benchmark or selected by the solver. The next prototype should reject helper insertions that delay the downstream Task start after accounting for its actual target-core queue and cross-core wait, before spending official evaluation calls.

## Static queue-screen diagnostic

The research-only `q1-general-bridge-static-queue-v2` variant adds a Task DAG plus core-order earliest-start projection. It uses original op Pipe-cycle peaks as Task duration estimates and the frozen configuration's same/cross-core waits; it does not use saved E0 timings. On the known bad 068 insertion (Task 38 to core 4/slot 5), it projects Task 42's start 8,848 cycles later and rejects the insertion. Four focused tests pass under locked Python 3.12.13, including that frozen counterexample and a no-scorer guard.

The full-500 baseline plans for nine research cases (005, 044, 048, 068, 069, 071, 075, 085, 097) were then checked without E1/E0/E2. All nine returned the baseline; exact graph/plan hashes, constructor SHA, slot counts and elapsed times are in `queue-screen-v2-census.json`. This **does not** show that no useful bridge exists. It shows this hard static filter is too conservative for use as a general quality selector: its Pipe-peak duration proxy omits intra-Task overlap, Task compilation, FIFO/memory interactions, and actual DDR contention. In particular, it rejects all 281 acyclic insertions in 068, including a different unscored insertion that tied the projected Makespan but added 22,274 COPY bytes. The next route is to generate a small graph-derived candidate family and use a separately budgeted, measured online evaluator gate rather than accept or reject by this proxy alone. No further official scoring window has been requested on the strength of this diagnostic.
