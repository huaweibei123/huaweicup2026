# Gap500 audit

The audit is fail-closed: it will not compute or publish partial means. It requires a `completed` run with `accepted_cells == 500`, exactly 500 accepted unique coordinates covering 001–100 × 1–5, and the frozen solver, runner, and manifest SHA values. It reads saved artifacts and the fixed baseline Git feed only; it does not invoke solver or evaluator.

Current preflight snapshot was still `running`; no scores were computed. Re-run the command after the batch completes:

```sh
python3 results/a/q2-nikolastarx/gap500-audit-20260925/audit.py \
  --repo-root <new-gap-worktree> \
  --manifest results/a/q2-nikolastarx/gap-full500-20260925/manifest.json \
  --run-summary <run-root>/summary.json \
  --old-audit-dir results/a/q2-nikolastarx/active500-audit-20260925
```

A complete run writes `audit.json` with paired old/new means using the same official single-core `B_i`, win/loss/tie counts, solver outer-process wall distributions, and construction/E2/E0 counts. Until all gates pass, the script prints only incomplete status and exits nonzero.

The frozen runner's `baseline_m` is the **old algorithm's Makespan at that same case and core count**. The official single-core `B_i` comes from the old feed's `baseline.result` artifact and is shared across core counts for a case. The audit checks both identities separately, including the first online native baseline score against the old official result. The small synthetic test uses `B=100`, old k2 Makespan `60`, and new k2 Makespan `50`; it does not exercise a solver or evaluator.
