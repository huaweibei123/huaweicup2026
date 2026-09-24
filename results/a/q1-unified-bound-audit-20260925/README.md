# Frozen v1 full500 versus static global lower bounds

This joins existing records only: zero new solver, E0, E1 or E2 calls. Source
feed and static-bound SHA-256 values are fixed in
`src/q1_benchmarks/unified_bounds_audit.py`; each of the 500 graph/config
identities, all 100 compressed baseline records, the bound implementation and
its four relevant official source files are checked. No case is missing or
duplicated, and no existing lower bound exceeds the corresponding official
Makespan. This consistency check does not substitute for the bound proof.

The mathematical assumptions and proof are in `docs/a/Q1_LOWER_BOUNDS.md`.
A separate bounded Sol high review checked boundary COPY predicates, retained
compute dependencies and release/work/tail resource inequalities against
frozen source lines; it found no concrete counterexample. This is a reviewed
mathematical bound under the documented integer/resource semantics, not a
machine-checked proof for arbitrary numeric domains or modified simulators.

| Cores | v1 mean speedup | Bound on best possible mean | Cases with U/OPT−1 at most 5% | At most 10% |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1.002097 | 1.242013 | 32 | 44 |
| 2 | 1.918082 | 2.479521 | 32 | 40 |
| 3 | 2.710450 | 3.701813 | 24 | 35 |
| 4 | 3.411256 | 4.917657 | 23 | 31 |
| 5 | 3.987519 | 6.088558 | 18 | 28 |

For each graph, L <= OPT <= U implies U/OPT−1 <= U/L−1. The second numeric
column is mean(B/L), using the same fixed official single-core denominators;
it is an upper bound, not an achieved score or a prediction. Large gaps may
mean the bound is weak. These known-set numbers do not establish generalization.
The 1-core output is the submitted P1 construction compared with the frozen
official single-core baseline, so that ratio need not be exactly one.

The static bound for 084/k5 is 253415 cycles. It is independent of partition.
The all-return candidate's DDR service bound 390951 belongs to that fixed
partition and must not replace the global bound. Its official 399121 cycles
therefore do not certify global near-optimality, even though they are close to
its own mandatory DDR work. The audit table intentionally retains v1's 503472
for this cell; it does not splice the later improvement into a uniform-v1 mean.

Research consequence: use proved small gaps to avoid spending large experimental
budgets on nearly exhausted cells; investigate bottleneck families behind large
unresolved gaps rather than force equal gains across all cases. This does not
authorize a new score batch, parameter sweep, or use of case IDs in the solver.

Reproduce from a checkout containing the fixed full500 feed and baseline files:

```sh
python -B src/q1_benchmarks/unified_bounds_audit.py \
  --feed-root . --output output/p1-bound-audit-fresh.json
```

If the data is in another checkout, pass that checkout via `--feed-root`.
Outputs refuse overwrites. `audit.json` contains every cell and the exact
identity checks; the script consumes only committed static results and never
constructs a plan or invokes an evaluator.
