# One-shot vector-arrival static constructions

There are exactly three 016 CLI constructions here: k2/k4/k5, one deterministic
algorithm, sequential execution, zero E0/E1/E2. See
`docs/a/q2-nikolastarx/VECTOR_ARRIVAL.md` for the counterexample, rule, scope,
complexity and decisions. None of the new plans has an official score.

| k | Fixed-plan minimum bound | Against existing achieved results |
| --- | ---: | --- |
| 2 | 4,026,386 | Unscored candidate below the prior 4,170,750 score |
| 4 | 2,251,313 | At least 626 slower than direct 2,250,687; prune |
| 5 | 2,247,348 | At least 3,641 slower than vector 2,243,707; prune |

- `016-k*/plan.json`: the actual singleton submission bytes.
- `016-k*/solver.json`: original CLI ledger bytes, relocated from `online/`.
- `016-k*/cli.json`: exact command, stdout/stderr, return code and child-process
  wall time. These are shared-machine receipts, not throughput claims.
- `receipt.json`: source/input/config and plan/ledger SHA-256 values, one-shot
  calls and recorded synthetic test result. Duplicate evidence plans were
  byte-compared and replaced by documented aliases, not stored twice.
- `construct_once.py`: the actual sequential launcher. It refuses an existing
  cell directory; do not rerun or extend this authorized static batch.
- `verify_static.py`: independent standard-library reader of the raw graph and
  six plan files (new and old vector), with no constructor/evaluator import.
  It checks all vector-core assignments, scalar crossings, complete V-FIFO
  acyclicity and independently recomputes the mandatory weighted-DAG bound.
- `readback.json`: that readback and existing official comparison values.

Only the readback, which constructs no plan and performs no evaluation, can be
repeated against these artifacts:

```sh
.venv/bin/python -B results/a/q2-nikolastarx/vector-arrival-static-20260925/verify_static.py
```

All cross-core edges in these fixed words carry a positive-size 2 B UB scalar
with one producer. The minimum lag is one source COPY_OUT cycle, configured
500 release cycles, and one target COPY_IN cycle. Same-core edges get no added
lag. This is a lower bound for the emitted fixed plan, not an official score
or a global bound over different plans; actual input loading, COPY FIFO,
contention and memory dependencies are omitted.

The old `vector_lanes.py` remains byte-identical:
`1dbccbc915c78f491d74faa57aceff3038e0d4667d1bd65ba7c30243aec5c3ec`.
The parent algorithm owner controls later freezing and any official validation;
this subtask adds no Git operation, team message, Pro request or cloud job.
