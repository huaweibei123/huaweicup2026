# P1 bounded component Tasks: full100 at four cores

The fixed method now has **100/100 successful official E0 results at four
cores**, using 99 new attempts plus the exact earlier case014 attempt. The
arithmetic mean of official singlecore Makespan / this method's Makespan is
**2.9490823180**. This is one method at K=4, not a mix of historical winners,
not a 1–5-core aggregate, and not a proof of optimality.

1. **Goal:** establish full-case coverage and expose quality/runtime limits
   of the bounded independent-component construction following the case014
   mechanism probe, with no online search or per-case parameter changes.
2. **Inputs:** algorithm `q1-bounded-component-tasks`, variant
   `frontier-then-independent-chunks`, solver
   `05f8fa0f7e52f5914f14815f6bdbcb851b631556`; packet_factor=4,
   trigger_ops=4096, chunk_ops=1024, four simulated cores. Runner frozen at
   `5933f8870b6604226f596f694b2df7d5ae468ed0`. All frozen official code/config/
   graph hashes were checked; entrypoint and both algorithm dependencies
   matched source Git blobs, and tracked worktree matched runner HEAD.
3. **Outputs:** `board-feed.json` has **99 new records only**, each with full
   plan/result/run and optional trace/log evidence. `full100-comparison.json`
   and `.csv` contain one row per case; `full100-summary.json` gives exact
   aggregate calculations and source references. Reused 014 originals and
   original feed remain under `references/reused-case014/` with unchanged
   original identity/timestamps and no duplicated board attempt.
4. **Limits:** a new 99-solver/99-E0 budget, single active cell, solver 30s,
   external E0 60s, whole-batch 1200s, no retry/E1/E2. This batch's policy permits
   child nonzero/timeout to continue only after confirmed cleanup; source,
   hash, cleanup, disk or runner failure stops the batch. The older stopped
   factor4 batch remains unchanged. **Actual:** 99 solver + 99 E0, all success;
   zero failures/timeouts/retries/E1/E2, no unrun cells.
5. **Verification:** all 99 new raw E0 results parse as scene A/four cores with
   positive Makespan. v1 preflight reports 99 records / 99 eligible. No full
   independent rerun was performed by this agent; inherited design context
   means this is not a blind independent review. Format/evidence checks do
   not substitute for algorithm acceptance.
6. **Execution:** 2026-09-24 14:38:55.685–14:45:45.653 UTC, about 409.97s for
   the new 99-cell batch. Apple M5 Pro, 48 GiB RAM, macOS 27 arm64, Python 3.12.13
   and locked dependencies; P2/Q3 had reported stopped, but no exclusive-host
   reservation. No cloud/GPU. Exact times and calls are in `batch.json`.

## Quality evidence

| Metric, same 100 cases and K=4 | Bounded method | Existing fixed64 |
|---|---:|---:|
| Mean of per-case official singlecore/Makespan | **2.9490823180** | 1.0880514073 |
| Successful E0 cases | 100 | 100 |
| Lower Makespan than the other method | **100** | 0 |
| Faster / equal / slower than official singlecore | **87 / 13 / 0** | See original fixed64 feed |
| Nonzero-spill cases | 32 | Not used as selection objective |

The fixed64 reference is the exact method/commit feed at
`6664a63adc3464d28d1f835d907cdeaea23e6b35`, not the board's history-best view.
Every denominator is a preserved frozen official singlecore result. The mean
is an arithmetic mean of 100 ratios, **not** total singlecore cycles divided
by total multicore cycles. Observed speedups range 1.0–4.4784089927. Ratios
above 4 are relative to this particular singlecore schedule, not a proof of
superlinear speedup against an optimal singlecore computation.

The base construction is component-pack on 97 cases and tree-frontier on 002,
062 and 063. Twenty-seven cases enter large-Task processing; only 12 actually increase
Task count (43 original Tasks split, 210 additional Tasks), while 18 report an
indivisible component beyond the chunk target. This is a report of exact
mechanism choices, not a claim that all graphs were improved by tree splitting.

## Remaining weaknesses

Thirteen cases still use one Task on one core and exactly equal official singlecore:
**005,016,024,047,048,051,064,069,071,075,082,085,086**. Each has one weak
component. Preserving all its internal dependency structure does not expose
parallelism; bounded chunking cannot split such an indivisible component.
Low-speedup cases with multiple components include 056(1.0434),003(1.1170),
068(1.1914),088(1.2021),049(1.2249),044(1.2425). The detailed row features
show component sizes, actual Task count, split counts and spill amounts.

Beating fixed64 everywhere does **not** mean beating all previous work:

| Case | This method | Historical profile-refinement | Interpretation |
|---|---:|---:|---|
| 002 | 73544 | 88188 | New direct construction improves quality |
| 044 | 124268 | 114443 | Historical refinement remains better |
| 051 | 607628 | 336057 | General connected-DAG decomposition remains a major gap |

Historical summaries are under `results/a/q1-profile-refine-20260924/` at
the solver-source commit. Those refinements use prior seed plans; their stage
wall is not a complete raw-input solve time and is not mixed into this
method's runtime or score. These cases and the 100 inputs are public
development data, not a held-out generalization test.

## Program cost is separate from Makespan

Across the 100 recorded solver calls, fresh-process startup-to-exit wall has
observed median **0.077456313s**, range **0.038867125–0.836848500s**. The maximum
is the reused case014 observation; the sum is 15.337999374s. Each includes
JSON read, online graph work, fallback/frontier/chunk construction, validation,
plan and diagnostics publication, and process exit. No evaluator is called
inside the algorithm. These are single observations across different graphs
on a non-exclusive host, not controlled repeated latency or a P95 estimate.

External E0 is separately measured: its 100-call sum, including the previous
case014 call, is 418.541034874s. The longest observed E0 is case 087 at 53.0372s,
followed by 085 at 28.7851s and 041 at 26.6550s. These are close enough to the
60-second experimental cap on 087 that the present success is not a universal
runtime guarantee. No evaluator phase or peak-RSS profiling was collected;
specific hotspot claims would be unsupported.

OS file cache was not flushed. Source/hash preflight, exact ZIP materialization
(0.146783500s shared), gzip and board/report export are benchmark setup and
postprocessing, not hidden online scoring or training. Environment records
explicitly leave unmeasured thread count and peak RSS unknown. The 13/100
partial result and case014 timeout of the earlier unbounded variant remain
separate historical evidence; no old failure status or budget was rewritten.

## Provenance, protocol and execution

Case 014 comes from `4d374dc25b5698491ddbb92837789a23a4ad3102`,
`results/a/q1-bounded-probe-20260924/20260924T1432Z-bounded014/board-feed.json`.
It uses identical solver SHA/parameters/input/config/official identity.
Its source attempt and run remain intact. The new batch therefore executes 99
calls, not 100. Exact originals plus preservation mappings are in the full
summary. All 99 other baselines and fixed64 comparisons are verified read-only
copies from existing evidence; no baseline was recomputed.

Official result/trace JSON is complete and only losslessly gzipped. Public
stdout/stderr replaces private filesystem roots with labels, documented in
run receipts. Largest stored original is 1222608 bytes. Feed 884605 bytes is below
the 8 MiB limit and needs no shards. `PRECHECK.json` is the actual board checker
output. The board checker verifies format/available bytes and does not rerun
the solver or assess scientific acceptance.

Original commands:

```sh
uv sync --locked
uv run python -B src/q1_benchmarks/bounded_full4_e0.py run 20260924T1439Z-boundedfull4-99
uv run python -B src/q1_benchmarks/bounded_full4_e0.py export 20260924T1439Z-boundedfull4-99
uv run python -B src/q1_benchmarks/bounded_full4_report.py results/a/q1-bounded-full4-20260924/20260924T1439Z-boundedfull4-99
```

`run` refuses existing output. Export/report/preflight make no evaluator
calls. Before the real batch, synthetic child-process checks covered exit 3,
timeout kill/reap and spawn failure without a false start count; these were
not P1 solver/evaluator calls. Their final outcomes are recorded separately.
This batch is complete and closed; no other core counts or new variants were
run. Delivery to the board, publication and independent review remain separate.
