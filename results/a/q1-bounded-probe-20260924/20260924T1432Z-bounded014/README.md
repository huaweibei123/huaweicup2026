# P1 case014: bound independent-component Task groups

1. **Goal:** test a distinct direct construction after the four-Task case014
   plan timed out in external E0. Bound large groups along independent internal
   component boundaries, without cutting those components or changing cores.
2. **Inputs:** solver `05f8fa0f7e52f5914f14815f6bdbcb851b631556`; runner
   `2d7ffe70e376387d817225970e7f25ddcdde8a44`; case014/four cores,
   packet factor4, trigger4096 ops, chunk1024 ops. The entrypoint and both
   `tree_frontier.py`/`component_pack.py` dependencies matched fixed Git blobs,
   all tracked files matched runner HEAD, and official input/code/config
   hashes matched the frozen source manifest before execution.
3. **Outputs:** v1 feed for `q1-bounded-component-tasks` /
   `frontier-then-independent-chunks`; exact plan, full result/trace under
   lossless gzip, diagnostics/run/logs, fixed64/singlecore original references,
   and the prior timeout's plan/diagnostics/run with source hashes.
4. **Limits:** new single-cell budget: one constructor 30s and one external
   E0 60s, one worker, no retry/E1/E2. Does not reuse any of the stopped
   99-cell batch's unspent budget. No later case is started by this runner.
5. **Verification:** actual one solver and one E0 start; both exit 0 and real
   result JSON parses as scene A/four cores with a positive Makespan. Preflight
   reports one valid/eligible record. This is not independent algorithm
   acceptance or a full-100 benchmark.
6. **Execution:** 2026-09-24 14:32:25.053–14:32:52.352 UTC on Apple M5 Pro,
   48 GiB, macOS 27 arm64, locked Python 3.12.13. P2/Q3 had reported stopped;
   no exclusive-host reservation or controlled speed claim. No cloud/GPU.

## Observed result

| Metric | New bounded construction | Existing fixed64, same case/k4 |
|---|---:|---:|
| Official Makespan, cycles | **4517065** | 9393843 |
| Official singlecore baseline, cycles | 17698626 | 17698626 |
| Singlecore / candidate Makespan | **3.91817** | 1.88407 |
| Scheduled copy bytes | 112336732 | 508522264 |
| Total extra DDR bytes | **102403992** | 498589524 |
| Spill bytes | 12537744 | 1697280 |
| Observed constructor wall, seconds | 0.836848500 | 12.816766375 |
| Independent E0 wall, seconds | 26.232943500 | 25.182243334 |

The new Makespan is about **2.07963 times lower** than this fixed64 result.
Total extra DDR decreases while spill increases, demonstrating why spill alone
is an insufficient objective. The two wall observations use different runs
and concurrency/polling circumstances; no controlled solver-speedup claim is
made from this table.

The original four groups are split into **36 Tasks, nine per core**, with
chunk sizes 741–1024 compute ops and no oversized indivisible component.
All 35705 compute ops remain assigned to their original cores. `diagnostics`
records every replacement and chunk size; the official plan validator and
complete E0 run accepted the resulting schedule. New plan bytes 372753,
diagnostics 2972, full compressed result 1170917, trace 824737.

The preceding unbounded plan's E0 timed out after 60.023412s and produced no
result or trace. It has **unknown Makespan and DDR**, so no quality ratio to
that plan is calculated. This new plan completed within the same 60s cap in
the observed run. Neither experiment sampled evaluator phase timings or
profiler stacks, so the evidence does not identify the old timeout's hotspot
or prove a particular compilation/spill mechanism caused it. The structural
change is useful evidence for the next design decision, not a phase profile.

## Timing and evidence

Solver wall covers fresh interpreter startup, graph read, frontier/fallback
construction, independent-component chunking, validations, plan/diagnostics
publication and exit. External E0 wall covers its own launch, evaluation and
complete result/trace/log publication. OS file cache is not flushed. Source
hash checks, exact ZIP input materialization, compression and board export are
benchmark setup/postprocessing, recorded separately rather than hidden
online evaluations. There is no training or case-specific precomputation.

`references/fixed64-records.json` and exact singlecore gzip bytes originate at
`6664a63adc3464d28d1f835d907cdeaea23e6b35`, verified by SHA256 and result-value
readback without rerunning. `references/prior-timeout-source.json` points to
the original timeout at `6e612b36aa010589b9d630499f7e5d94de84f242`. Complete
official JSON bytes were not edited; gzip round trips were verified. Process
stdout/stderr public-root substitution is recorded in each receipt.

## Execution record; batch closed

```sh
uv sync --locked
uv run python -B src/q1_benchmarks/bounded_probe_e0.py run 20260924T1432Z-bounded014
uv run python -B src/q1_benchmarks/bounded_probe_e0.py export 20260924T1432Z-bounded014
```

These record the completed original execution, not a new budget. `run`
refuses existing outputs. Export and preflight execute no solver/evaluator.
Preflight used main's board checker with this checkout as `--repo`; this
historical algorithm base predates the board implementation. Further coverage
requires a separate explicit batch. This agent inherited the design context
and therefore does not claim a blind independent review.
