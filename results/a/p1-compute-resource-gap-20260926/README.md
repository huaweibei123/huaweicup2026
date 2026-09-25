# P1 five-core compute resource bound and coverage decision

This read-only calculation uses the published full-500 checkpoint at
`a1bb4451cd85c46b32bb928d57c81e22cfeca1a6` and the frozen scene-A
evaluator. It runs no solver or evaluator. Reproduce from this checkout with:

```sh
python3 -B src/q1_benchmarks/p1_resource_gap.py > results/a/p1-compute-resource-gap-20260926/resource-gap.json
```

For each original non-COPY op, `_op_duration` in the frozen evaluator is at
least `max(1, op.cycles)`. A legal plan assigns each such op exactly once. Each
of five cores has one executor slot for a given Pipe (`PIPE_SLOTS = 1`), so
the sum of those op durations on Pipe `p`, denoted `W_p`, gives the bound

`M_i >= L_i = max_p ceil(W_{i,p}/5)`.

Dependencies, waits, DDR contention and generated COPY operations can only
make this lower bound more optimistic. It is a necessary resource bound, not
an achievable schedule or a global optimality certificate. The script checks
`L_i <= observed official M_i` on all 100 graphs; it aborts if this fails.
The fixed official single-core denominator `B_i` gives an optimistic speedup
ceiling `B_i/L_i` for each case.

The latest complete checkpoint has five-core mean **4.055266985790237×**.
The old v4 +5% threshold is **4.227202847527824×**, while +5% relative to
this latest checkpoint would require **4.258030335079749×**. The R7 strict
shared-input recognizer covers only six cases: 044, 046, 067, 073, 083 and
092. Even if all six somehow attained their compute-only lower bounds and the
other 94 stayed fixed, their conditional best mean would be **4.223134277861007×**.
It falls short of the v4-based threshold by 0.004068569666817× and the
latest-checkpoint threshold by 0.034896057218741×. Thus that exact six-case
domain cannot alone satisfy either +5% target. This does not bound methods
that also change other cases.

`resource-gap.json` contains all 100 per-case work sums, lower bounds, current
official results and conditional headroom. The largest optimistic individual
mean contributions are 044 (0.0799×), 048 (0.0607×), 071 (0.0579×), 069
(0.0566×) and 005 (0.0516×). These numbers rank mathematical room, not
predicted gains: the bound ignores Task legality, L1/UB capacity, FIFO,
COPY and DDR costs. The next candidate should expand structural coverage
beyond the six strict graphs, with joint Task DAG and official evaluator
checks before any quality claim.

The six-case recognizer snapshot is preserved as
`r7-strict-census.original.json` (SHA-256
`548e8e79392331954d305e514a9c861621d5c9d4c5c788f88722cfb25771f7f7`),
copied from the earlier P1 research worktree. The script asserts its
recognized set and records source hashes in `resource-gap.json`.
