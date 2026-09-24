# One whole-lane arrival-tree candidate

This candidate responds to the measured 016 scalar round trips in
[VECTOR_TRACE_DIAGNOSIS.md](VECTOR_TRACE_DIAGNOSIS.md). It changes scalar
ownership and per-core compute order while preserving the exact recognition,
DFS lane order and contiguous lane partition used by `vector_lanes.py`.
That source file is unchanged. There is one deterministic construction rule,
no parameter sweep, online evaluator, portfolio or choice among trial plans.

## Why not simply choose each reducer's earliest-finishing core?

A small counterexample was found before implementation. Fixed lanes A and C
on core 0 take 1000 and 600 cycles; lane B on core 1 takes one. Let R=A+B and
P=R+C each take 13, with a 502-cycle cross-core scalar transfer. After A and B,
a work-conserving critical-tail list can start C at 1000. R then finishes at
1515 on core 1, versus 1613 if it stays on core 0. Greedy earliest finish moves
it to core 1, but P must wait until 2017 for the return and finishes at **2030**.
Keeping both reducers on core 0 finishes at **1626**, 404 cycles earlier.
The 98-cycle local gain was a bad global choice. This is a synthetic scheduling
counterexample, not a contest-case performance score. The rejected greedy rule
was not implemented or run on 016.

## The single construction rule

Let n be lane count, k the number of cores, and S stage count. Recognition
requires the existing all-V fork/chain/binary-reduction template, persistent
positive-size L1 lane inputs, closed single-consumer UB chains and a common
scalar size. No case ID, node-ID layout, fixed n/S/chain length or known score
is used to recognize or choose a plan.

1. Reuse `recognize`, `_tree_order` and `_partition` from `vector_lanes`.
   Every operation of a complete lane stays on its original fixed lane owner
   across all stages. Within each core, keep that DFS-relative lane order.
2. Plan all of a core's current-stage lanes before its scalar reducers. Chains
   are indivisible scheduling units with their true summed compute cycles.
   Different cores may overlap; this is a local ordering restriction, not a
   global barrier requiring every core to finish every lane first. Initial
   input loading is omitted from the timing proxy.
3. At each stage, freeze the vector of post-lane core availability f. A leaf
   result's table is finite only at its physical lane owner, at the planned
   lane end. For a scalar reducer u with children l and r, compute

   `D_u(c) = p_u + max(f[c], min_a(D_l(a)+tau(a,c)), min_b(D_r(b)+tau(b,c)))`.

   Here tau is zero locally; remotely it is the configured release delay plus
   two minimum COPY durations, `delay + 2*max(1,ceil(scalar_bytes/bandwidth))`.
   With the frozen official configuration and 2 B scalars, this is **502**;
   500 is read from configuration, not assumed universally. The availability
   vector f is not mutated while filling DP tables.
4. Choose one root state. For a nonfinal stage, minimize

   `max_d(D_root(c) + tau(c,d) + W_next[d])`,

   over cores d with lanes in the next stage. W_next is exactly their next
   stage's fixed whole-lane work. Break ties by D_root(c), then core ID. For
   the last stage minimize D_root(c), then core ID. This includes next-stage
   broadcast as a one-stage heuristic horizon; it is not full-horizon optimal
   control. Backtrack child argmins **from that root state**, rather than
   choosing each node's independent minimum table entry.
5. With these scalar owners fixed, build one topological list. Select the
   ready reducer with earliest feasible V start, then greatest remaining
   compute-tail length, then node/core ID. Recompute actual contention within
   this simplified model: one V operation per core, dependencies, and the
   minimum scalar transfer lag. The resulting listed root end and owner,
   **not the optimistic DP value**, release next-stage lanes and determine
   whether each needs a broadcast transfer.
6. Expand complete lanes and scalar dispatches into one global topological
   order, project onto cores, and emit the official singleton mapping/order
   interface. Verify structure using official `derive_multicore_plan`. Finally
   recompute the fixed-plan longest-path bound on all original eligible
   dependencies plus the full emitted V FIFO; cross-core edges carry the
   mandatory minimum transfer lag. This bound is calculated after placement
   and does not select among plans.

Every emitted core FIFO is a projection of one global topological sequence;
adding its consecutive edges cannot make a cycle. Recognition excludes the
COPY-contraction counterexample discussed in `PRO_R01_REVIEW.md`. Every
cross-core tensor is checked to be scalar; the unchanged whole-lane/input
ownership prevents vector transfers. The global bound is still only for the
fixed emitted plan, not the P2 optimum over all plans.

The placement DP is O(S n k²), because each child argmin is computed separately,
not by enumerating all pairs for each parent state. Backtracking is O(S n).
Scalar scheduling uses per-core release/ready heaps and k-way selection,
O(S(n log n + nk)); lane expansion is O(N). Recognition, graph indexing,
structural validation and final weighted-DAG bound add their existing graph
costs (the heap topological operations are O((N+E) log N)). Tables use O(nk)
working space per stage; detailed evidence and the final plan are O(N+S(n+k)).

## Boundaries and falsifiable expectations

The DP has no scalar resource history: two different subtrees may both assume
they occupy the same V core at the same time. A test with four leaves ready at
100 and three 13-cycle reducers on one core gives optimistic root 126, but
the fixed-owner list correctly finishes at **139**. Thus D is placement
guidance, not a predicted official completion time or a proven optimal
placement under contention.

Even the listed proxy omits input COPY loading, COPY FIFO and shared DDR
contention, Step2 incarnations and Step3 memory dependencies. Root lookahead
ignores serialization of several broadcast COPY_OUT operations. The final
fixed-plan bound omits these costs too, which is why it is a lower bound.
No proxy number is an E0 score, a zero-spill certificate or an execution
validity certificate.

Local lanes-first ordering sacrifices useful lane/reducer overlap when that
overlap was possible. It preserves whole-chain closure and the existing raw
priority envelope: L1 is at most the assigned persistent inputs; UB is at most
twice the largest local lane tensor plus `2*n*scalar_bytes`. More leaf scalars
may coexist than in the old postorder, but their raw bytes fit that envelope.
This does not prove the expanded runtime peak. In particular, fixed whole-lane
granularity remains a potential five-core bottleneck, and the algorithm does
not promise removal of all serial crossings for every recognized tree.

The intended falsifiable test is whether this **one** constructed word reduces
the diagnosed reciprocal scalar path and its fixed-plan bound while preserving
whole-lane/input ownership. Official legal execution and Makespan still need
a separately frozen E0 pilot. A failure is retained; the static run is not a
license to adjust the rule until its 016 proxy looks good.

## Static validation

Synthetic tests cover fixed input ownership and uninterrupted chains, the
greedy-return counterexample, sibling contention, root broadcast lookahead,
carrying listed root time across stages, graph/FIFO acyclicity, deterministic
record shuffling, unchanged inputs, tiny-capacity honesty, unsupported edges,
invalid configuration and the real CLI contract. Evaluator entry points and
`subprocess.Popen` are poisoned during relevant tests.

The 016 k2/k4/k5 one-shot constructions and exact commands are recorded under
`results/a/q2-nikolastarx/vector-arrival-static-20260925/`. They are static
constructor evidence, with **0 E0/E1/E2 calls**, and have no official scores.

| k | Independently recomputed fixed-plan LB | Previous vector LB | Existing direct E0 | Existing vector E0 | Decision from the bound |
| --- | ---: | ---: | ---: | ---: | --- |
| 2 | 4,026,386 | 4,169,655 | 9,260,226 | 4,170,750 | Useful unscored candidate; improvement not yet established |
| 4 | 2,251,313 | 2,549,603 | 2,250,687 | 2,552,270 | Cannot beat already achieved direct result; prune this candidate |
| 5 | 2,247,348 | 2,239,418 | 2,240,622 | 2,243,707 | Cannot beat either achieved reference; prune this candidate |

The final bound equals the listed proxy for these three words. That equality
does not promote the proxy to E0: mandatory input loading and remaining COPY
semantics still increase or constrain actual execution. In particular the k4
bound is already **626 above** the achieved direct score, and k5 is **3,641
above** the achieved vector score. No official evaluation is needed to refute
strict Makespan improvement by these two fixed plans. The candidate is retained
unchanged; no second placement variant was tried.

For k4, all eleven reducers in every stage land on core 0. The old scalar
return path is removed: after the first stage, each tensor-data path crosses
at most twice including the broadcast to a lane core and its scalar's return.
The listed period is 7,383 cycles. This proves fixed whole-lane ownership did
not force the old three-hop reduction suffix; its remaining local-lanes-first
and scalar contention costs still keep this construction above the old best.

For k5 the same single-root concentration gives a 7,370-cycle listed period
and remains inferior by the lower bound. For k2 root cores alternate: listed
periods 13,182 and 13,221 each occur 152 times. Its maximum number of crossings
on an original data path is still three in 152 stages (including broadcast).
Thus the new rule does **not** eliminate all multi-crossing paths, even though
the weighted fixed-word bound improves. These maximum-hop counts do not by
themselves identify the time-critical path.

Raw UB priority peaks are **65,546 / 65,540 / 65,538 B** for k2/k4/k5; these
remain raw intervals, not official runtime peaks. Independent plan readback
confirms all **14,640 vector operations** retain the previous lane core and
that every current cross-core tensor is the same 2 B UB scalar class.
The minimum 502 lag is applicable to every such dependency: the original
single producer must precede inserted COPY_OUT, source COPY_OUT completion
precedes target COPY_IN release by configured 500, and target COPY_IN must
complete before its consumer. `schedule_step3.py` lines 74–82 gives each
positive-size COPY at least one cycle; shared bandwidth or spill cannot make
it shorter. Same-core dependencies get **zero** added lag. No COPY duration is
charged to an intra-core FIFO edge. Input COPY durations are omitted, not
counted as if they were scalar transfers. The frozen template has no internal
original COPY or multi-producer tensor that would invalidate this argument.

Each static CLI ran once, sequentially, on the shared machine. Observed child
process wall times were 0.504 / 0.450 / 0.490 seconds; internal ledger times were
0.462 / 0.408 / 0.449 seconds. These are construction receipts including this
implementation's evidence generation, not an isolated-machine or cross-method
speed benchmark. The nine synthetic tests passed; a separate agent reviewed
the design and implementation without running another constructor.
