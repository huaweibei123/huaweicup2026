# P1: transferable structural gains, not a flat score curve

Research decision, 2026-09-25. This records the current P1 direction, not a
claim about undisclosed official test sets or a new experiment authorization.

## Objective and priorities

Keep one reproducible solver entry point for arbitrary valid inputs. Optimize
official Makespan and solver end-to-end wall time together, with legality and
the fixed configuration preserved. Uniform software does not require one
construction for every graph, or equal speedups across graphs.

Prioritize a bottleneck when it has explainable, recoverable structural headroom
and reasonable development/runtime cost. Low measured speedup alone is not
evidence of headroom: serial dependencies and communication may be limiting.
A high-scoring graph can still waste substantial time. Use a proved applicable
lower bound when available; a fixed-partition bound cannot certify optimality
over all partitions. There is no objective to smooth the per-case curve.

For a fixed core count, the reported mean is mean(B_i/M_i). An equal increase
in an individual speedup contributes equally to that mean wherever it occurs.
Consequently a mean gain need not mean improvement on every graph. Also report
regressions, legality/failure rates, and runtime tails; do not mask them with
the mean or invent a new weighted official score.

## Generalization safeguards

- Select constructions from dependencies, pipe loads, tensor reuse, capacity
  and Task gates. Do not select from case identifiers, graph hashes, recorded
  winners, or constants reverse-engineered only to recognize an example.
- A narrow structural guard is a testable domain of applicability, not proof
  of generalization. The currently unintegrated Fang prefetch adaptation
  requires 12 chains of length 4 and 5 cores. Its legality checks and two
  synthetic tree shapes do not show that this exact allocation remains useful
  when width, depth, durations, tensor sizes, or synchronization costs change.
- Retain the general baseline and evaluate a small, justified set of candidates
  on the current input within a fixed budget. An online evaluator comparison
  is algorithmic selection on that input, not lookup of historical winners.
  E1 accuracy, scoring failures, and the extra solver time remain limitations;
  final official E0 validation is separate.
- The current 100 graphs have already informed research. Neither repartitioning
  them now nor rerunning them turns them into an untouched test set. A frozen
  algorithm must be checked on newly generated instances and, where possible,
  genuinely unseen graph families before claiming out-of-sample performance.
- Separate legality-preserving relabeling tests, structural perturbations,
  generator-family holdouts, and official cases. Synthetic robustness evidence
  must never be counted as official performance. Freeze parameter/seed ranges
  before validation; any subsequent tuning consumes that validation set.

No additional batch is dispatched by this note. Next experiments require a
specific falsifiable mechanism, fixed inputs/code/budget, and the existing
resource coordination. Do not improve a selected example through an expanding
parameter sweep merely because its score remains below another algorithm.

## Current evidence and limits

The fixed v1 source `48faef6f1386c3dc7d037674a38af29d533ba774` completed
all 500 official cells with five-core mean 3.987519066. That is known-set
performance, not a certificate for unseen graphs.

The fixed v2 source `3fa0100c8bf9f4a7c1745f9d3f925748ac3fdc19` was checked
on only 008/084/095 at five cores in `20260924T1844Z-return3`. The new return
candidate was selected on 084 (399121 versus v1 503472 cycles), and rejected
on 008/095, where the baseline remained better. All three selected E1 results
matched E0 Makespan and movement. This supports conditional use plus a guard;
it neither revises the v1 full-set mean nor proves unseen-family robustness.
Data: `f552c2c5e87f2d760bda2f9a0a3b175d4f99157c`,
`results/a/q1-unified-return-smoke-20260925/20260924T1844Z-return3/`.

The independent split-core probe source
`57574a7c7bebf48a1823b13e576677b5f30bea64`, run
`20260924T1856Z-split084`, reduced scheduled DDR bytes but worsened 084
Makespan to 426656 versus 399121. It is not selected for the unified solver.
This is a negative mechanism result, not grounds for case-specific tuning.
