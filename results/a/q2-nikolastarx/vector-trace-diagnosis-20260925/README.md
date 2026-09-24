# Existing 016 trace diagnosis

Companion report: `docs/a/q2-nikolastarx/VECTOR_TRACE_DIAGNOSIS.md`.

- `analyze.py`: standard-library-only reader and fixed-plan longest-path bounds;
  no solver, official evaluator imports or scoring calls.
- `manifest.json`: SHA-256 of the six plans/results/traces, frozen graph and
  relevant source; also hashes this analysis script.
- `summary.json`: comparisons, exact trace/result agreement, path bounds,
  stage-period histograms, stage 100 cross transfers and wait distributions.
- `pipe_work.csv`: per-core/pipe counts, busy time and idle gaps.
- `stages.csv`: all observed stage root completions and root-to-root periods.
- `stage100_ops.csv`: same stage's 59 eligible operations in each plan.

Reproduce from the repository root:

```sh
python3 results/a/q2-nikolastarx/vector-trace-diagnosis-20260925/analyze.py
```

The analyzer derives paths for **fixed** ownership/order. These are candidate
lower bounds, not new official outcomes or global optimum certificates. The
observed trace and result are two exports of the same official run, so equality
is an export-integrity check rather than independent evaluator acceptance.
No timing claim is made for this diagnostic script or any proposed algorithm.
