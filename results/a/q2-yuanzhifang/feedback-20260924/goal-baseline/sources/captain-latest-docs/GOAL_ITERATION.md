# P2 quality and solver-time iteration, 2026-09-24

This session remains the P2 algorithm owner
`nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894`. Fang keeps his independent P2
implementation; P1 and shared evaluator infrastructure remain with their own
sessions. Source, protocols, all attempted outcomes and board submissions stay
separate. Local and Colab resources are authorized, subject to coordination with
other sessions; that permission does not turn unused evaluation budgets from a
completed experiment into a new experiment.

## Objective and comparable evidence

The primary score is unchanged official P2 Makespan in cycles, with extra DDR
bytes also reported. Solver efficiency is cold-process end-to-end wall time,
including any online evaluator calls; separate final E0 is external evaluation
time. The official 5–10 minute guidance is neither a minimum runtime nor an
automatic 600 second disqualification. A short brute-force grid is still a
grid: the present direction uses structural decisions without online scoring.

The user's image gives target mean speedups 2.26/3.18/3.96/4.53 at 2/3/4/5
cores. Its formula, denominator, coverage and author are unspecified. It is
preserved as a numerical target, not assigned to Fang. Our reported full means
must use the same frozen 100-case single-core baseline and arithmetic mean of
per-case ratios. A historical mixture of winners is useful feedback but is not
one executable solver or a meaningful mixed-hardware timing baseline.

The independently recalculated board snapshot is in
`results/a/q2-nikolastarx/target-audit-20260924/`. At its recorded time, the fixed
Fang contiguous algorithm means were 1.45984/1.83622/2.09981/2.28146 and its
average construction wall time about 0.31 seconds. Our preceding six-case
portfolio improved five historical cells, but online E0 dominates its wall time
and those cells cannot establish a full-suite mean.

## Next falsifiable algorithm

`direct_solve.py` chooses exactly once from graph structure: guarded homogeneous
M–V*–M resource word, otherwise the tensor-aware DAG earliest-finish constructor
in `dag_direct.py`. It performs no online E0/E1/E2 calls. This is not a safe
replacement claim for the preceding portfolio: shared DDR contention, memory
capacity and spill remain outside the prediction model, and even structural
validation is not full official execution validation.

The first pilot uses 002/008/014/016/025/035/062/071, selected by documented
static features before this candidate was scored, at cores 2/4/5. Some cases
have known scores under earlier algorithms, so the pilot is a development set,
not a holdout. The separately frozen JSON protocol controls the 24 final E0
calls, zero online calls, one worker, no retries and all time/resource limits.
Failures are outcomes, not opportunities to silently replace cases or methods.
The second step depends on these measured mechanisms; full 100×5 evaluation is
needed before claiming target means or superiority across cases.

## Mathematical boundary and stopping criterion

Global bounds use mandatory retained dependencies, indivisible pipe work and
head/tail windows. Their scope and proof are in `OPTIMALITY_BOUNDS.md`; static
100×5 certificates are in `results/a/q2-nikolastarx/goal-20260924/`. A successful
official result meeting a certified global lower bound proves that cell's
Makespan optimum. No improvement in a finite collection of candidates proves
nothing comparable. A schedule optimum also does not prove minimal solver wall
time or optimal extra DDR at every score.

A new, focused ChatGPT 6 Pro question is in the huaweicup project and archived
under `AI chats/20260924-P2-异构流水与最优性界/`. It asks about heterogeneous
reentrant pipeline construction and optimality certificates. The request is
in flight; no answer or experiment from it is yet accepted. Local falsification
continues while it runs. Any answer needs its assumptions checked before use.
