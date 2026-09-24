# Fixed-plan lower bound for P1: prototype, not online pruning yet

The objective is to avoid scoring a candidate that cannot improve an already
validated incumbent. This file proves only a bound for one fixed submitted
partition and core order. It does not constrain the optimum over other plans.
The prototype does not change the frozen v4 solver or the in-flight full500 run.

## Assumptions and official correspondence

Use the frozen P1 evaluator with one slot per pipe, one globally shared DDR
service capacity, all original non-COPY operations retained, and successful
execution. The implementation calls the official plan view for mapping and
contracted inter-Task dependencies, then independently topologically checks
the union with per-core Task order. It does not run Step1, Step2, a Task
compiler, or E0/E1/E2.

The Task-local mandatory copies are those created by `_build_scene_a_tasks`:
for each tensor and Task, a local consumer without a local producer forces one
read. A local producer forces one write if there is an original COPY_OUT
consumer, no eligible compute consumer, or a compute consumer outside that
Task. A tensor shared by two Tasks on one core still requires two Task reads.
Multiple local consumers do not duplicate that Task's boundary read. Original
COPY nodes are excluded rather than charged as compute. COPY bridges contribute
to official inter-Task dependencies but must not create fictitious intra-Task
compute chains. Additional spill copies can only increase required resource
work; the bound does not assume every spill emits a new write.

For Task t, let P[t,p] be all original compute cycles on pipe p, plus mandatory
boundary-copy service assigned to MTE2 or MTE3. Let D[t] be the sum of mandatory
read and write service. Durations follow max(1, cycles); boundary COPY duration
uses the same math.ceil(size / bandwidth) expression as the frozen program.
Define d[t] = max(max_p P[t,p], D[t]). Since a Task is activated as a whole and
finishes only after every operation, its elapsed time is at least d[t].
Serialized global DDR capacity implies this even when read and write use
different pipes; contention with other Tasks cannot shorten its service work.

Add the following precedence edges with a lag:

- Adjacent Tasks on the same core: same_core_wait.
- An official cross-core Task dependency: cross_core_wait.
- A same-core Task dependency: zero (the ordered-core path already supplies
  the appropriate waits).

Merge duplicate edges by maximum lag, not sum. All Task operations start after
activation; the official release function uses max(previous core end + same
wait, cross-core predecessors' end + cross wait). Thus every edge (u,v,w)
requires start[v] >= end[u] + w. A topological longest-path recurrence
E[v] = d[v] + max(0, max_(u,v,w)(E[u]+w)) is therefore a lower bound on every
Task completion. Combining max_t E[t] with sum_t D[t] gives a fixed-plan
Makespan lower bound. Neither estimate assumes attainable FIFO order or zero
spill.

## Proposed use and current limits

If L(candidate) is strictly greater than a successfully scored incumbent's
Makespan, that candidate cannot win the Makespan comparison in the mathematical
model. Equality alone is insufficient because the solver breaks Makespan ties
with scheduled DDR bytes. No candidate is skipped by the present prototype.

The evaluator uses binary64 and tolerance-based DDR event handling. Mirroring
boundary duration rounding avoids one input-level mismatch but does not prove
all-domain numerical equivalence. The bound needs fixed-source review and
independent E0 evidence before any pruning is enabled. A selected-plan audit
can expose overestimation; it cannot establish how many unselected candidates
would be pruned or prove a complete solver speedup. Bound computation cost must
also be included in solver wall time.

The new tensor and Task work bookkeeping is linear in the visited memberships;
the augmented DAG traversal uses a heap. The complete function also invokes
the official validator/plan-view implementation, whose sorting and adjacency
costs remain part of its runtime; no linear end-to-end complexity is claimed.
