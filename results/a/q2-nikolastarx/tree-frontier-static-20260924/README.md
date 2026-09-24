# Guarded tree-frontier candidate, static evidence

This is one deterministic P2 construction proposed for external official review.
It is **not** an E0/E1/E2 result, zero-spill certificate, benchmark submission,
or full-domain replacement for adaptive source `6e5099a35300133419990bf1f44f621f98850c21`.
The earlier frozen sources and router are unmodified.

Implementation: `src/q2_nikolastarx/tree_frontier.py`.
Tests: `tests/q2_nikolastarx/test_tree_frontier.py`.
Reproduction: run the command at the top of `check.py` from the repository root;
existing static evidence is intentionally not overwritten. `report.json` fixes
source, runner, input, config and all three plan/detail SHA-256 values. No random
seed is used; all ties use graph IDs/core IDs. Single worker, no external process,
E0, E1, E2, or official task compiler was called by the audit.

## Guard and actual P2 degrees of freedom

Require one eligible weak component, one sink, no eligible op with two successors,
exactly one tensor output per eligible op, one eligible producer per produced
tensor, at most one eligible consumer per produced tensor, no intermediate
original COPY_OUT, and no direct op-op edge. Tensor-induced eligible predecessors
must exactly equal official COPY-contracted predecessors. This excludes forks,
multiwriter tensors and excluded-COPY dependency surprises. Nonproduced graph
inputs may be shared; they are explicitly handled as first-last intervals.

Output contains only singleton `node_to_subgraph` and `core_schedules`. Every
eligible op is assigned once. The full weighted postorder is a global original
DAG topological order, and each core receives its projection. Thus original
precedence plus submitted per-core order is acyclic. Official derive validates
the structure; this argument does not cover Step2 spills or Step3 reordering.
Unique producers/consumers also place each inserted cross COPY_OUT in its own
producer bucket and each COPY_IN in its only consumer bucket. Their dependencies
respect the original topological direction. This does not prove memory/runtime
feasibility for the fully transformed program.

## Closed-subtree order and narrow proof

For each tensor pool p use integer scalar weight
`lambda[p] = lcm(capacity[L1], capacity[UB]) / capacity[p]`.
An original DDR tensor is local UB in P2. Capacities must be positive. Graph inputs
are excluded from this private subtree profile, then included exactly once per
core in the final raw priority interval calculation.

For child subtree i, let P_i be its peak weighted private live bytes and R_i its
output weight retained for the parent. Visit children in decreasing `P_i-R_i`,
breaking ties by op ID. For that order:

- Child j contributes `sum(previous R_i) + P_j` to the peak.
- Parent compute contributes `sum(all child R_i) + R_parent`; parent output and
  all child inputs coexist in this inclusive-touch model.
- P_parent is the maximum of those contributions.

The pairwise exchange inequality for `P_i-R_i >= P_j-R_j` is
`max(P_i, R_i+P_j) <= max(P_j, R_j+P_i)`.
This proves the local scalar order, recursively within the **noninterleaving
private subtree family**. It does not optimize two pool peaks independently, the
full graph-input frontier, arbitrary interleaved topological orders, projected
per-core frontiers, COPY contention, or official Makespan.

## Direct ownership, no scoring search

Let W be total clamped original compute work. Select maximal complete subtrees
with work <= W/(2k), a single fixed granularity. Sort them by decreasing work,
then root ID, and assign each intact subtree to the least loaded core. The
remaining skeleton is visited in global postorder. Attach each skeleton op to a
child core that retains the most incoming tensor bytes; compute load and core ID
break ties. A heavy source outside all packets goes to the least loaded core.
This greedily minimizes the immediate incoming cut bytes with child ownership
fixed, not total future cut bytes. No packet-count or load-balance guarantee is
claimed. Parent skeleton work is counted in the final loads.

For a k-core tree, cutting exactly k complete subtrees is not a safe substitute:
062's top join separates work 183504 and 2827548, a severe imbalance. The fixed
W/(2k) granularity permits more than k pieces without online trials or grids.
Construction after indexing is O((V+E) log V + kV), O(V+E) storage. LPT total-work
balance is a heuristic for multiple pipelines. No isolated COPY clock is used.

## Static 062 results

| cores | packets | skeleton ops | cut edges | additional no-spill COPY bytes | largest raw L1/UB peak bytes |
|---|---:|---:|---:|---:|---:|
|2|5|4|2|6144|7680 / 18432|
|4|9|8|8|24576|7680 / 16896|
|5|17|16|14|43008|7680 / 15360|

All 19636 eligible ops are covered, all requested cores are used, official derive
passes, and original-plus-core-order DAG is acyclic. Per-core loads and exact
plan hashes are in `report.json`. The roughly 0.46–0.51 s function measurements
exclude startup, graph/config reading and writing: they are not solver wall time.

The graph has 2181 sources, 2180 joins and one sink. Every internal produced tensor
has one consumer. The theoretical review further found all graph inputs confined
to their corresponding maximal unary leaf chain, including the one input with
eight consumers inside a 16-op chain. The implementation does not assume that
private-input specialization; it counts every touched external tensor across its
first and last submitted op on each core.

The cut COPY bytes follow the guarded official construction rule: two tensor
sizes per cut edge, graph input copied once per consuming core, unique sink
output copied once. There is no replicated graph input in these three plans.
They exclude spill traffic and are not measured official total extra DDR.

Raw per-core intervals start/end at original compute touches. Inserted COPY
allocations, memory reuse edges, resource FIFO timing and execution overlap can
change the real live frontier. Low raw peaks are a mechanism hypothesis, never a
zero-spill claim.

## Synthetic counterexamples and review

Ten unit tests cover guard rejection, parent-output coexistence, input-order
stability, use of multiple cores, official derive/order acyclicity, exact cut
traffic, no evaluator/compilation calls, CLI hash and overwrite refusal, plus:

- Shared inputs X/Y=10 B for leaf pairs A/C and B/D: private SU peak is 5 B,
  ID-tied A,B,C,D order has full inclusive raw peak **23 B**, while A,C,B,D has
  14 B. Private optimality does not imply total frontier optimality.
- Two branches each produce 99 B, shrink to 1 B, then expand to 50 B; the parent
  output is 1 B. Closed subtrees peak at 150 B, while interleaving shrink steps
  first peaks at 101 B. Even private trees need the noninterleaving qualification.
- Two 1-cycle leaves plus a 1-cycle parent, k=2 and a 500-cycle remote delay:
  ownership balances compute but introduces a dominating cross dependency.
  More cores are not a promised Makespan improvement.
- Two 6 B children and 5 B parent must count 17 B simultaneously.

Independent read-only review by `p2_bounds_theory` aligned the exchange formula
and guard; `review_dag_constructor` checked the implementation, COPY accounting
and counterexamples. It found one overstrong packet-count comment, corrected
before this saved static audit. Neither review replaces official acceptance.

## Minimal next official experiment (proposal, not executed)

Freeze this exact source/runner/input/config and evaluate these three saved
062-k2/k4/k5 plans once each with unchanged official E0. Keep solver end-to-end
wall separate from external E0 wall. Record legality, Makespan, graph/cross COPY
bytes, spill bytes, total extra DDR and any deadlock. Compare against the frozen
adaptive/direct and Fang plans at the same cells; do not change the threshold or
expand the matrix based on missing scores. The hypothesis is that subtree closure
and few cuts reduce 062's earlier large frontier and cross-core traffic while
retaining multicore compute; official Makespan may still be limited by skew,
COPY contention and real scheduling. If that hypothesis fails, diagnose the
transformed sequence/runtime before proposing another mechanism.
