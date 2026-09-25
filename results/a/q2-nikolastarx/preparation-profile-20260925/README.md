# P2 preparation profile — completed once on Linux

The admitted CPU Standard run completed one preparation and no E0/native
evaluation, with no retry or unknown preparation. `run/` contains the downloaded
original archive, extracted report/function table/receipts, hash verification,
and actual stop + empty-session readback. The independent 10-minute cleanup
guard was released after readback. T0 before creation was 04:00:51Z; the child
ran from 04:02:01.695603Z to 04:02:56.551663Z on 2026-09-25.

Profiled preparation took 52.521 s: task building 51.188 s, validation 0.000039 s,
and packing 1.333 s. The largest measured self-time was 69,181 `list.index`
calls, 24.301 s (46.27% of the profiled total). Most came from the unchanged
official task builder's COPY placement lambdas at lines 165 and 187, which
repeatedly search `core_orders[core]`. A per-core subgraph-position lookup is
a concrete optimization candidate for E2's local preparation layer. It must
preserve frozen official behavior and pass differential verification before
use. These are profiler timings, not a measured speedup of a replacement.

Environment setup took 4.702 s for uv bootstrap and 6.600 s for locked sync.
The supervised child wall was 54.856 s; sampled worker tree peak RSS was
757,719,040 bytes (867,635,200 including its observer). The 28,399,387-byte
prepared snapshot is retained inside the original archive for later equality
checks. No new solver score or full500 result was generated.

The infrastructure session has received this evidence and owns any public E2
optimization; this P2 branch does not modify the shared evaluator in parallel.

## Original frozen protocol

Purpose: explain the measured 29–41 seconds spent preparing a new plan by fixed
E2 `603b0741e21c449d3db652ebd67c94f2dc014cc9`, before optimizing the compiler.
This is not an algorithm score or a resumed full500 batch.

The input is the archived, already evaluated 014/K1 selected plan from solver
`295ec9cf4351b77f5c6fffe8fbb23e8bc8d2f323`. `manifest.json` pins its graph,
plan, config, all 50 E2 source files and both profile scripts. The existing Linux
native binary is retained only for identity; it is **not loaded or executed**.
`prepared.json` identifies the 1.31 MB local capsule and its full SHA-256.

The single allowed preparation attempt runs `_build_scene_b_tasks`,
`validate_execution`, and `_native_b.pack`. Runtime guards reject calls to
`evaluate_scene_b`, `_native_b.score` or `_native_b.get_lib`. There is no public
`evaluate_record` call and no fallback path. The attempt is reserved before
the supervised child starts. Budget: one worker, one preparation, zero E0 and
native evaluations, zero retries; 180 seconds and 4 GiB sampled process-tree
RSS. An internal 150-second signal preserves a partial profile on timeout.
Each output file has a 64 MiB hard file-size limit; the prepared object is
additionally capped at 32 MiB. No graph worktree or full dataset is duplicated.

Execution requires the coordinator's exclusive CPU Standard Colab window,
plus an independent fixed 10-minute VM termination guard. No runtime or scoring
was started at this freeze. The locked Python 3.12 environment is prepared
separately and its wall time is reported. The profiler perturbs time, so its
measurements diagnose functions; they are not direct unprofiled speed claims.

The raw profile, compact function table, process receipt, source/input hashes
and one prepared-object snapshot will form the result. A semantic optimization
would require a separate differential check and budget before deployment.

Validation at freeze: Python syntax and Git whitespace checks; bounded Luna
read-only review of the call boundary and existing process-tree supervisor.
The review found an environment-setup error-state reporting gap; the controller
now records `failed` and the exception before archiving and rethrowing it.
