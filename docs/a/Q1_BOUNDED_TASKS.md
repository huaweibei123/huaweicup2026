# P1: bound oversized independent Task groups

The frozen factor4 full-coverage attempt stopped at case014: 35,705 compute
ops / 1,340 weak components became four Tasks of 8,890–8,969 ops. Construction
took 0.346024 s; external E0 timed out at 60.023412 s, emitted no result/trace,
and was killed/reaped. The batch retained 12 successes, this timeout and 86
unrun cells. There is no phase profile, so spill or a particular evaluator
stage cannot be asserted as the cause. It is not a full-100 performance score.

`src/q1/bounded_tasks.py` applies the frozen tree-frontier factor4 construction,
then refines only Tasks larger than 4,096 compute ops. Weak components induced
inside such a Task are packed by decreasing size into chunks of at most 1,024
ops, except an indivisible oversized component stays intact and is reported.
It replaces each old Task at the same position on the same core. No component
dependency is cut inside a chunk group; the original augmented Task DAG gives
a block topological order for the refinement. Official structural validation
checks the resulting plan. Existing small plans retain their exact JSON
structure. The solver has no evaluator calls or search.

These thresholds are explicit engineering parameters to test whether bounding
large compilation units resolves the observed E0 timeout. They are not cache
capacities, proved optimum thresholds, or a time guarantee. More Tasks add
same-core gates and can duplicate shared inputs; retain quality regressions.
Indivisible large components remain an unresolved case. First-fit packing is
worst-case quadratic in the number of components, although each group has
bounded capacity; do not claim the whole solver is linear.

## Frozen diagnostic batch

Before new results: only case014 at K=4, factor4/trigger4096/chunk1024, one
constructor start (30 s) and one external E0 start (60 s), no retries/E1/E2,
single worker. Freeze solver and runner first; preserve timeout/failure just
as success. Do not reuse the stopped 99-cell budget or silently rerun its
original plan. This is a distinct construction and run. Compare against the
old fixed64 same-cell result, official singlecore, and the previous timeout
without inventing a Makespan for the timed-out plan. Further coverage requires
a separately declared batch after this mechanism check.
