# P2 assignment-dependent pipe-work pruning

This second iteration addresses wasted official evaluations seen in the frozen
first batch (data `5e5d688ca473a80b7d72b26b397ce568ac70f534`). It uses the same four
proposals, order and six development graphs. It does not claim new solution-quality
wins, a holdout, or globally optimal solutions.

## Bound and proof

For each original operation other than COPY_IN/COPY_OUT, let d(v)=max(1,cycles(v)).
For a submitted ownership map c(v) and Pipe p(v), define

    L(P) = max over (core,pipe) of sum of d(v) with that owner and Pipe.

For every structurally valid plan on the frozen P2 evaluator, original non-COPY
operations survive construction/Step2, retain their cycles and assigned core, and
are issued once. `schedule_step3.py` defines PIPE_SLOTS=1 and _op_duration=d(v) for
these operations; _uses_ddr_bandwidth is false for them. P2 global issue/retire uses
that slot count, sets op_end=now+duration, and retires only when end<=now. Thus all
these operations on the same (core,pipe) occupy disjoint intervals at nonnegative
times. Makespan covers their last endpoint, so Makespan>=L(P). Added COPY operations,
external releases, spill and memory dependencies cannot reduce required compute
work. This does not assume zero spill or independent components.

Consequently, given a successful incumbent M and a strict-improvement selector,
L(P)>=M certifies that P cannot replace the incumbent. Equality keeps the earlier
plan by design. No incumbent means no prune. Unsupported input means abstention,
not a low/high guessed score. The implementation certifies integer cycles only
and checks exact original operation coverage plus unique subgraph ownership.
Malformed plans do not acquire feasibility certification from this bound: a pruned
plan is not reported as a valid officially evaluated plan.

Complexity is O(V+number of scheduled groups) time and O(V+groups+cores*pipes)
space including ownership/coverage maps. This version constructs and saves the
candidate first; it saves full E0 calls, not construction time. Future preconstruction
routing would need its own proof and validation.

## Evidence and experimental boundary

`feedback-20260924/bound-retrospective.json` reads the 24 already archived results,
checks L<=actual Makespan in each, and predicts six skips (affine and guarded
fallback for 002, 051, 016). It makes zero new evaluator calls and is retrospective,
not evidence of runtime savings. Hand-calculable bound tests plus mock controller
tests cover pipe serialization/overlap, unsupported inputs, equality, absent
incumbent, error and timeout handling; they also call zero evaluators.

The prospective protocol is `results/a/q2-nikolastarx/pruning-20260924/protocol.json`.
This is a separate maximum 30-E0 budget (expected 18 online+6 final), one local CPU
worker, RSS observation stop 4GiB, 60s/evaluation, 240s/solver, 1200s/batch, no retry
or new samples. All source/runner commits are frozen before dispatch. Preserve all
24 proposal plans and the six expected prune certificates, confirm selected plan
SHA and full final result bytes against batch one, and record actual calls and
outer solver-to-exit wall. Independently launched final E0 is outside solver wall.
No Colab runtime is needed for this small batch; do not reserve another session's
runtime. Local concurrent sessions make wall figures observations rather than a
clean isolated-machine causal speedup estimate.

CLI: add `--prune-bounds` to `python -m src.q2_nikolastarx.solve`. Omitting it keeps
the unpruned selection path, although current source identity differs from the
first frozen commit. The new variant must keep a distinct board run/variant ID.
