# P2 global lower bounds and what would prove optimality

This note concerns the frozen official **P2** objective, minimized Makespan in
cycles. It gives necessary conditions over **all** submitted partitions, core
assignments and per-core subgraph orders, not just our four constructors. The
implementation is `src/q2_nikolastarx/global_bounds.py`. It only validates and
reads graphs; it calls no E0/E1/E2 evaluator. Source hashes accompany each scan.

The separate `assigned_pipe_lower_bound()` remains useful for rejecting one
fixed candidate. Its value can exceed the optimum over other assignments; it
must never be published as the graph's global optimum lower bound.

## 1. Frozen executable contract

The relevant files are under `data/raw/a/official/code/`:

| Fact used | Frozen source location |
| --- | --- |
| Eligible operations exclude the two COPY types; each eligible operation occurs once in the plan | `stub_multicore_cut_and_schedule.py:122–175` |
| Core assignment appends each eligible operation unchanged to that core's Task | `multicore_cut_evaluate_problem_2.py:68–86` |
| Original tensor edges are rebuilt; a DDR-position tensor becomes UB locally | P2 `133–156` |
| One input COPY per consuming core; one required output COPY per producing core | P2 `158–179` |
| Cross-core tensor edges have COPY pairs and a release delay | P2 `181–234`, `323–327`, `374–379` |
| Only direct edges with both endpoints eligible are retained/rebuilt | P2 `209–213` |
| Spill insertion retains every original Task operation | `schedule_step2.py:443–456`, `473–489` |
| Spill consumers may be rewired to a new incarnation; existing backing can suppress COPY_OUT | Step2 `304–408`, `410–441` |
| Exactly one executor slot per core and Pipe | `schedule_step3.py:28–31`; P2 `299–302`, `459–477` |
| Non-COPY duration is `max(1, cycles)` | Step3 `76–85`; P2 `470–477` |
| Step3 and P2 preserve the projection of `seq_ext` on each Pipe | Step3 `279–289`; P2 `381–412` |
| Original cycles are nonnegative **integers** | `evaluation_validation.py:181–202` |
| DDR remaining-work simulation uses binary64, a tolerance and upward projection | P2 `329–371`, `478–483` |

The CLI fixed configuration has bandwidth 60 bytes/cycle, L1 524288 bytes,
UB 131072 bytes and cross-core delay 500 cycles. The compute-only bounds below
do not depend on their values: dropping transfers, nonnegative waits and
capacity restrictions is a relaxation. A failed official plan is not a feasible
witness and cannot establish an upper bound on the optimum.

## 2. Work and indivisibility: valid without a precedence assumption

Let `V` be the eligible operations, `d(v)=max(1,cycles(v))`, `p(v)` their Pipe,
and `k` the submitted core count, including empty cores. Put
`W_p=sum_{v:p(v)=p} d(v)`.

Each operation occupies one fixed core/Pipe for its entire duration. Across k
cores, at most k operations of the same Pipe can overlap, and no operation
starts before time zero. Consequently every successful result C satisfies

`C >= ceil(W_p / k)` for each of the four Pipes.

This includes eligible non-COPY operations on MTE2/MTE3; it does **not** sum the
cycles of removed original COPY nodes. Different Pipe work values are combined
by a maximum, not by addition: M and V may execute concurrently.

There is a stronger inexpensive packing relaxation. Sort one Pipe's durations
as `d_1 >= ... >= d_n`. For every integer
`1 <= q <= ceil(n/k)`, let `m=(q-1)k+1`. Among these m largest operations, some
core must own at least q. Their total duration is at least the sum of the q
smallest durations in that prefix. Thus

`C >= sum_{j=m-q+1}^{m} d_j`.

The implementation takes the maximum of these quantities and the total-work
bound. This is a pigeonhole argument, not an exact bin-packing solver. A witness
contains q distinct jobs, so no operation is counted twice within an inequality;
different inequalities are again combined by maximum. Example: five 100-cycle
operations on four cores require at least 200 cycles, while work/k gives 125.

## 3. Which compute dependency graph is safe?

The implementation uses eligible-to-eligible **direct original edges**, and
eligible producer-to-consumer edges through the **same original tensor**. It
does not add a relation merely because a path traverses an excluded original
COPY. P2 uses a contracted COPY graph for input-plan validation, but the Task
builder does not universally reconstruct all those timing relations.

For the precedence bounds, the current certificate additionally requires **at
most one eligible producer per original tensor**. Multiple-producer cases retain
the work/packing and exact byte bounds; their path/window fields are null. This
is deliberate abstention, not a claim that their precedence always fails.

In the supported domain, a retained dependency survives as follows:

- A same-core direct edge is retained by Task construction and Step2.
- A same-core produced tensor either retains its producer-to-consumer path or
  changes to producer → initial spill COPY_OUT → backing → reload → consumer.
  Later reuse of that backing keeps the first producer dependency. An internal
  single-producer tensor has no incoming boundary COPY backing from another
  producing core.
- A cross-core edge has source-producer → COPY_OUT → external release →
  destination COPY_IN → consumer. On the destination there is no other eligible
  producer. A later spill reload may reuse the DDR backing, but the first
  destination COPY_IN precedes it in `seq_ext` and on the fixed MTE2 order. That
  order is enforced in the final replay, including the external release.
- Capacity dependencies and nonnegative waits add restrictions. We omit their
  durations; we do not assume they disappear in the actual result.

This argument uses successful official execution and the fixed Pipe projection;
it would not apply to a different scheduler that allowed later reloads to pass
the original cross-core COPY_IN.

**Scope check, not a new performance experiment:** the static scan of all 100
frozen graphs found zero multiple-eligible-producer tensors and zero extra
contracted-only edges. Therefore replacing the old contracted graph with this
retained graph leaves their previous compute critical-path numbers unchanged.

### Why the COPY caveat is necessary

A minimal source-derived example consists of three operations and no tensors:
`A(M,10) -> original COPY_OUT(MTE3,1) -> B(V,10)`, with direct op-op edges. Put
A and B in the same subgraph on one core. The graph and plan pass the documented
structural rules. The contracted validation graph has A→B, but P2 lines 209–213
drop both actual edges because each has an excluded endpoint. Its Task contains
independent A and B on different Pipes; the event code issues both at zero and
finishes at 10. A claimed 20-cycle contracted-path lower bound would be false.

This is **a source-derived synthetic counterexample**, not an E0 run or formal
case score. The unit test checks only that our static routine refuses that
contracted timing edge. No evaluator call was spent on it.

## 4. Critical paths and head/tail workload windows

In the supported retained graph, let `h(v)` be the longest total duration of
strict ancestors along a path ending just before v, and `t(v)` the longest
duration of strict successors after v. Both are computed by DAG dynamic
programming. Every official execution has

`start(v) >= h(v)` and `end(v) <= C - t(v)`.

The usual critical-path bound is
`C >= max_v (h(v)+d(v))`. Its witness is an explicit sequence of eligible op IDs.

For **any** subset S of one Pipe, all its occupied intervals lie in
`[min_{v in S} h(v), C-min_{v in S} t(v)]`. Integrating the available k slots gives

`C >= min h(S) + ceil(sum_{v in S} d(v)/k) + min t(S)`.

This does not add a critical path to unrelated total workload. The selected
work genuinely has both the stated release lower bound and the stated tail.
The implementation scans all head thresholds and all tail thresholds; at a
threshold it selects every operation of this Pipe at or above that threshold.
Sorting and a running work/minimum accumulator make the scan O(n log n), not
an enumeration of candidate plans or all subsets.

Hand-checkable example: a 10-cycle predecessor, eight independent 10-cycle V
operations, and a common 20-cycle successor on two cores. The compute critical
path is 40, and V work/k is 40, but the workload window proves 10+40+20=70.

After graph adjacency construction, the certificate needs O(|V|+|E_compute|)
for paths and O(|V| log |V|) per requested k for the load/window scans. Forming
tensor-induced adjacency costs the number of induced producer/consumer edges;
we do not claim it is always linear in the original bipartite edge count.

## 5. Exact mandatory I/O bytes; DDR time is a separate question

P2 necessarily introduces at least one input COPY for every tensor with eligible
consumers and no eligible producer. It introduces at least one output COPY for
every tensor with an eligible producer and either an original COPY_OUT consumer
or no eligible consumers. Let B be the sum of these tensor sizes, counting the
two categories as specified by the builder. Assignment can introduce additional
copies, and Step2's recorded spill traffic is nonnegative. Hence

`scheduled_copy_bytes >= B`

and, using the exact official definition,

`added_copy_bytes >= B - original_graph_copy_bytes`.

The subtraction is not clipped at zero for arbitrary inputs: removed original
COPYs and their traffic can make the official added-traffic quantity negative.
On the 100 frozen graphs this lower bound is zero. The certified byte bound is
not a claim that a plan attaining zero extra bytes also minimizes Makespan.

In a real-arithmetic fair-sharing model, the sum of unavoidable normalized DDR
service work (each reconstructed boundary copy has `max(1,ceil(size/BW))`) also
lower-bounds C. It is stronger than simply dividing total bytes by bandwidth in
some examples. However, the executable uses binary64 updates, 1e-9 comparisons,
and `ceil(cursor-1e-9)`, while active transfers and their releases depend on the
plan. This patch **does not promote that ideal argument into an implementation
level exact time certificate** without a numerical-error argument. It reports
`ddr_time_bound_certified=false`; no DDR time value enters the returned C bound.

## 6. Invalid conclusions to avoid

- Step3's local Makespan is not a universal global lower bound; it is a result
  for one chosen order and local replay, with inserted operations/dependencies.
- A fixed plan's computed/assigned load, cut bytes, spill count, or critical
  path after generated Pipe/memory edges is not automatically a bound over
  other partitions and orders.
- Whole connected-component assignment is a constructor restriction, not an
  official restriction. Component work/k or indivisibility may not treat an
  entire component as one indivisible job unless the theorem states that scope.
- A sum of M and V loads, CP plus all workload, or an independently estimated
  compute time plus all DDR time generally double-counts possible overlap.
- A compute-template guard for M–V*–M does not certify tensor equivalence, zero
  spill, or an official Makespan upper bound for an ideal resource-word formula.
- Original COPY cycles and original cut edges cannot all be charged unchanged:
  P2 removes original COPY nodes and reconstructs boundaries by participating
  cores. Additional spill COPY_OUT may also be suppressed by an existing backing.
- Increasing a core **budget** permits leaving cores empty; forcing a particular
  repartition can worsen a plan. Neither observation proves a graph optimum by
  comparing two unrelated candidates.

## 7. What is sufficient to finish a per-case optimality claim?

For a specific frozen graph/configuration/k, let L be a certified global bound
and U the independently verified official Makespan of a legal submitted plan.
Then `L <= OPT <= U`. Exact equality **L=U** proves that plan's Makespan globally
optimal. For integer timings, a rigorous real lower bound greater than U-1 would
also suffice; this implementation already returns integer bounds.

If L<U, the optimality status is unresolved. A period without improvements,
beating Fang, a narrow grid, or a proof within one constructor family is not a
global impossibility proof. `U/L-1` is a certified **upper bound on the achieved
relative suboptimality**, not an observed error or a guaranteed achievable gain.
If a matching construction is unavailable, a stronger relaxation or a complete,
independently checkable infeasibility certificate for C<U is needed. Such a
certificate must cover actual submission freedom and executable timing.

With the same official single-core baseline `M_single`, the speedup is bounded
above by `M_single/L` (L>0). The average speedup bound is the arithmetic mean of
these per-graph ratios, **not** the ratio of aggregate sums. Comparing the board
requires fixed graph coverage and denominators; no 6-case claim substitutes for
the 100-case 1–5-core requirement.

Makespan optimality alone says nothing about optimal DDR among tied plans or
the minimum solver wall time. To claim joint/Pareto optimality, account for those
objectives separately: e.g. a plan attaining both independent Makespan and byte
lower bounds is optimal in those two mathematical metrics. Solver wall time is
hardware/implementation/measurement dependent; the above schedule relaxation
is not a lower bound on all possible programs. Keep measured quality–wall fronts
and their resource conditions, rather than asserting a wall-time impossibility.

## 8. Static reproduction and the next theoretical question

```sh
.venv/bin/python -B -m unittest discover -s tests/q2_nikolastarx -p test_global_bounds.py -v
.venv/bin/python -B -m src.q2_nikolastarx.global_bounds data/raw/a/official/data --cores 1 2 3 4 5 --output NEW_CERTIFICATES.json
```

Seven tests include exhaustive assignments of only tiny synthetic load lists as
an independent check of the pigeonhole inequality; no official evaluation is
involved. The first static 100-graph scan supported all 500 coordinates, took
9.37 seconds on the shared local machine, and improved 369 bounds relative to
`max(compute CP, ceil(max Pipe work/k))`. These are stronger certificates, **not
improved solution scores**. At k=4 the six development bounds are:

| Graph | Makespan lower bound (cycles) |
| --- | ---: |
| 002 | 60180 |
| 008 | 62532 |
| 044 | 18645 |
| 064 | 4074 |
| 051 | 151787 |
| 016 | 1928760 |

A useful focused Pro question is: **derive an implementation-safe stronger P2
bound coupling mandatory boundary DDR service with compute head/tail windows,
including the frozen binary64 fair-pool replay; prove the numerical guard or
give a counterexample.** Supply actual graph/source hashes, distinguish ideal
real-arithmetic statements from executable certificates, and request a small
falsifiable construction. A second specific question is the exact optimum for
the homogeneous M–V*–M graphs with their real input/output tensors, shared DDR
and capacities. A generic new survey of scheduling would not resolve either gap.
