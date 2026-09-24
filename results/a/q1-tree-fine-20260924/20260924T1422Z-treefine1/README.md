# P1 case002: one frozen frontier-granularity ablation

1. **Goal:** test whether smaller independent subtree packets improve worker
   balance enough to compensate for more boundary copies and tail work.
2. **Inputs:** solver `409886dd4b17b589643d3f5a13af9e94a9783d73`, runner
   `45cd9d5e467462c2ce952e964d4f346cdf119721`; case002, four cores,
   `--packet-factor 4`. Official source/config/graph hashes were verified.
   Factor1 evidence is reused from `75033cbf70cf3dd9a6f8b60e1277246bf29a8268`;
   singlecore/fixed64 from `6664a63adc3464d28d1f835d907cdeaea23e6b35`.
3. **Outputs:** same algorithm/variant, new solver SHA/parameters/run; v1 feed,
   exact plan, full official result/trace as gzip, diagnostics/run/logs;
   `ablation_comparison.json` and exact factor1 originals under `references/`.
4. **Limits:** one solver (30 s) + one external E0 (60 s), one active cell,
   no retry/E1/E2. This is an offline mechanism comparison, not online search.
   Neither previous batch was rerun; no new graph or other factor was tested.
5. **Verification:** actual one solver and one E0 call succeeded. Result JSON
   is scene A/four cores/positive Makespan. Preflight reports one eligible
   record. No blind independent algorithm acceptance or full-100 claim.
6. **Execution:** 2026-09-24 14:21:07.051–14:21:07.381 UTC; Apple M5 Pro,
   48 GiB, macOS 27 arm64, Python 3.12.13/locked dependencies. P2 had finished;
   Q3 could have a trailing worker. No cloud/GPU or exclusive-host claim.

## The single planned comparison

| Metric | Factor1, existing | Factor4, new |
|---|---:|---:|
| Official Makespan, cycles | 85702 | **73544** |
| Official singlecore/Makespan | 3.05646 | **3.56175** |
| Frontier packets | 7 | 25 |
| Worker Tasks + tail Task | 4 + 1 | 4 + 1 |
| Worker operation counts | 295/574/574/349 | 434/488/426/426 |
| PIPE_M work by worker, cycles | 39600/76800/76800/46800 | 58800/66000/57600/57600 |
| PIPE_V work by worker, cycles | 5868/11448/11448/6948 | 8568/9648/8424/8424 |
| Tail ops / PIPE_V work | 6 / 216 | 24 / 864 |
| Scheduled copy bytes | 1245696 | 1300992 |
| Extra DDR bytes | 21504 | 76800 |
| Spill bytes | 0 | 0 |

Makespan falls by 12,158 cycles (**14.186%**), with 55,296 additional DDR
bytes and zero spill. Largest worker PIPE_M work falls from 76,800 to 66,000
cycles while tail work grows. The observations support the granularity tradeoff
on this case; they do not establish monotonic improvement for larger factors,
an optimal factor, or general dominance.

The new plan also beats the historical 88,188-cycle refinement by 14,644 cycles
(about 16.61%). That historical refinement consumes a pre-existing plan;
its stage timing must not be compared to this solver's complete raw-graph
startup-to-exit wall as if both were full solver measurements.

New solver wall is **0.077639625 s**; independent official E0 is **0.239008541 s**.
The solver includes graph reading, fallback construction/validation, tree
construction and output publication. Each process is fresh; OS file cache is
not flushed. No exclusive-host speedup or latency distribution is claimed.
Exact input ZIP materialization is separately recorded (0.00127225 s shared).
Source/hash preflight and gzip/export are benchmark setup/postprocessing, not
hidden online scoring, training or case-specific algorithm precompute.

## Reproducible artifacts

The original commands were:

```sh
uv sync --locked
uv run python -B src/q1_benchmarks/tree_fine_e0.py run 20260924T1422Z-treefine1
uv run python -B src/q1_benchmarks/tree_fine_e0.py export 20260924T1422Z-treefine1
```

`run` refuses existing batches; these commands are a record, not a new
execution budget. `export` calls no evaluator. Preflight uses the shared
main-branch `src/benchmark_board/protocol.py --submission --repo <this-checkout>`
because the algorithm's historical base predates the board service.

`ablation_comparison.json` is a read-only derivation: for each non-COPY op in
frozen `data/case_002.json`, look up its Task in each preserved plan and sum
`cycles` grouped by `(Task, pipe)`. Counts/tail structure come from preserved
diagnostics; Makespan/DDR from the complete official results. Source commit,
paths and SHA256 of all reused factor1 originals are recorded in that file.
No evaluation was performed to produce this derivative comparison.

Process stdout/stderr replace personal workspace/temporary input roots by
public labels as documented in run receipts. Official result/trace bytes
remain complete under lossless gzip. Data and inference remain separate.
