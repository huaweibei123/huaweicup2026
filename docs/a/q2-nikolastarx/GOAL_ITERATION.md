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

## First official feedback, 2026-09-24 15:09 UTC

The frozen direct pilot completed all 24 cells successfully with 24 external E0
calls, zero online evaluations and no retries. Data commit is
`81219bf923524fb60616e39b5ad2dced67aec3e2`; the comparison source/report is
`debfa9f067364c5ffa6b5feef89a000c5fb631a1`. Every result, including regressions,
is retained. Against fixed Fang the count is 16 wins / 8 losses; against the
earlier historical snapshot it is 14 wins / 1 tie / 9 losses. The same eight-case
k4 mean is 2.903777, below the historical mixture's 2.981852. This does not
establish a full-suite curve or justify promoting this route everywhere.

016/k4 improves 2,556,787 to 2,250,687 cycles while decreasing extra DDR by
657,164 bytes. In contrast 025 regresses at every tested core count, and 016/k2
spills 379,715,584 bytes. The full comparisons and identity checks are in
`results/a/q2-nikolastarx/direct-pilot-20260924/comparison/ANALYSIS.md`.

This feedback redirects the next construction toward memory pressure: preserve
independent components within one core and bound the raw tensor frontier of
interleaved component cohorts. Shared graph inputs can remain live across
cohorts and must be reserved explicitly. This is a new, separately frozen
mechanism experiment, not an extension or rerun of the 24-cell batch. Single
connected graphs need a different treatment; a whole-component guard must not
silently serialize them onto one core.

Scale/Windows verification of stable candidates is routed through the existing
scoreboard coordinator s7c98 for LYX/farmer. This owner keeps algorithm work and
authorized local mechanism samples; it will not send competing member batches.

## Capacity-envelope feedback and unified handoff

The second mechanism pilot used source
`919c82370a42eca9fcff444bef4c1e1e3ea78282`, runner
`aa714b3811fa3722e5e126be12268917af0da93f` and sealed data
`1e92b165b8609e94191b1be8d1eab7c4f8aa5929`. All six cells
(014/025 at 2/4/5 cores) completed with six external E0 calls, no online
evaluation, retries or failures. Each improved Makespan, extra DDR and spill
against the earlier direct construction; 025 spill is zero at all three core
counts. All six beat fixed Fang Makespan and were accepted by the central board
as six strict cell improvements. This is still a selected mechanism sample.

Source `6e5099a35300133419990bf1f44f621f98850c21` freezes
`adaptive_direct.py`: one shared index and a fixed structural routing rule.
All 500 graph/core combinations passed structural and priority-DAG checks,
with zero E0/E1/E2, and 27 related tests passed. The six completed envelope plans
remain byte-identical after extracting the shared-index helper. Route counts
are 421 component-envelope, 64 DAG-EFT, 15 homogeneous resource-word. These
facts do not establish official execution or full-suite means.

`ADAPTIVE_BENCHMARK_HANDOFF.md` gives the central dispatcher one candidate,
fixed inputs, controls, reusable prior evidence, suggested bounded matrix and
failure policy. No full matrix has been started by this owner. Windows runner
compatibility remains unverified. In parallel the next quality research target
is subtree closure / weighted frontier construction for single-component
reductions; 016-k2 and 062 remain unresolved rather than hidden by the router.
