# Hypergap full500 audit

**Completed and independently audited:** [full500 results and limitations](RESULTS.md), [machine-readable report](report.json).

Read-only, fail-closed paired audit for the frozen `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f` run and runner `ff47cbca4a953602dec7e4b959bbb10a016eca9a`. It requires the completed runtime summary and the 10 archived 10-case groups; it does not invoke a solver or evaluator and never creates or repairs missing artifacts.

Run from the repository root:

```sh
python3 results/a/q2-nikolastarx/hypergap-full500-audit-20260925/audit.py \
  --summary <runtime-run>/summary.json \
  --archive-root results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee
```

Until the summary is `completed`, contains exactly 500 accepted unique 001–100 × 1–5 rows, has complete call accounting, and no in-flight work, the script reports `incomplete` with `scores_computed: false`. On completion it checks the 10-case feed shards and their run/algorithm/parameter/runner identity, archived plan/result hashes and E0 metrics against each summary row, graph/config/official identity against the pinned old feed and source manifest, then reports per-core paired arithmetic means of `B_i / M_i`, win/tie/loss counts, cases with makespan improvement, cases with changed plans, solver wall and external E0 wall separately, and call counts. `B_i` is read from the fixed official single-core result in old feed commit `60afc38b327680fbda0ff10182e3e05a01edd72d`, not from a summary denominator. Peer targets are reference context only; this audit does not establish optimality.

The archive contains sanitized receipt derivatives. Their stored SHA values are checked separately from the original ledger SHA recorded in run.json; they must not be compared as identical byte streams. Cell validation is independently callable for real partial archives, but the main command never computes a full score until all 500 cells are complete.

Root validation on 2026-09-25: all 300 currently archived cells passed the real collect/validate helpers; cloned metric, result-blob SHA and original-ledger SHA mutations were rejected. The actual running summary returned exit 2 with scores_computed=false. See partial-validation.json; this is not a full500 result.

The final audit also checks the existing global bound certificate implementation, six official source hashes and all 500 graph/core identities. It rejects any M < LB, reports mean B/LB as a potentially unattainable relaxation ceiling, and counts M <= 1.05 LB using integer arithmetic. Under the documented bound assumptions, those cells are certified within 5% of optimum because OPT >= LB; a large M/LB does not prove that further improvement is attainable. No bound or evaluator is recomputed.
