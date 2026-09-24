# Private-chain core specialization: unscored candidate

Previous evidence: all-cut capacity-derived return packets on084/k5 achieved
399121 official cycles, compared with503472 for unified-v1. It did so with
no spills/MEM dependencies, but9925632 additional copy bytes. That is evidence
for testing a more balanced DDR/compute load, not evidence that the following
new construction works.

Use the same strict private homogeneous M(a)→V+(b)→M(c) recognizer. Derive
whole packet size q_w and mixed packet size q_c from touched tensor footprints
and fixed L1/UB capacity. Whole components stay on W cores; return-cut
components stay on C=K−W other cores. Every chain stays on one core and each
core's Task order moves forward. Original IDs are retained; Task IDs are
offset to avoid collisions, followed by augmented-DAG validation.

The fixed proxy uses ell_w=a+b+c+100/q_w and
r=(max(q_c(a+c), a+b+(q_c−1)max(a,b))+100)/q_c. Whole-chain batching amortizes
only Task gates; it does not divide whole-chain compute by q_w. With x cut
chains, consider max(ell_w(N−x)/W, r x/C, D0+delta x), where boundary counts
provide D0 and the complete last interface provides delta (including external
input duplication). These are model quantities, not E0 values or a global
lower-bound certificate.

For fixed W the first term decreases and the latter two increase. The
continuous minimum is at the earlier intersection of the first term with the
other two, clipped to[0,N]. The constructor uses rational arithmetic and
checks integer floor/ceil neighbors of both intersections plus endpoints,
with integer per-core chain counts and deterministic ties. W ranges from1 to
K−1, so parameter selection examines a constant number of graph-derived
candidates for official K≤5; it performs no evaluator-based search. This
rounding rule is explicit and is not claimed to solve an integer scheduling
problem globally.

Important omissions: packet startup/drain, exact Task gates, actual FIFO
interleaving, and time-varying shared DDR contention. Independent core groups
may still synchronize adversely. Neither this proxy nor its minimum is an
official quality result. An E0 experiment must use a frozen source, compare
with existing same-case/k baselines, and inspect actual DDR/compute intervals.

Implementation is separate from unified-v1/v2 and has not been added to their
candidate sets. Three synthetic tests cover plan coverage/DAG, capacity,
determinism, metadata independence, rejection and the serial whole-work rate.
Python3.12.13 tests pass; no real constructor or E0/E1/E2 call has run for this
new candidate. The previous source/data remain unchanged.

Read-only check of the existing084 all-cut E0 output and plan: total rounded
DDR service390951 cycles equals the observed union of all COPY intervals.
Makespan399121 is only1.02089776 times that fixed-plan DDR service. The plan's
boundary copy bytes exactly equal official scheduled-copy bytes23161962.
Thus further Task ordering on this unchanged copy workload has little room;
a better partition must trade fewer DDR copies against available M/V overlap.
This is a fixed-partition resource bound, not a global optimum certificate.
Evidence: results/a/q1-capacity-return-20260925/fixed-plan-analysis/ddr-audit.json.
No scoring or real constructor was rerun for this analysis.
