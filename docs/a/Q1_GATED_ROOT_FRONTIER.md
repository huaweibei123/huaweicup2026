# Generic root-aware fork/reduction candidate

This is a structural generalization of the intact-chain idea in Fang's StageG
(source `e29685da0268420f2d881246603763d6bf8baf5b`). It is a standalone research
candidate, not part of the frozen v4 full500 run. Width 12, depth 4 and core
count 5 are not applicability conditions or allocator constants.

## Restricted graph family and submitted freedom

Each round consists of W independent serial compute chains followed by a
binary reduction tree with one root. All retained compute operations use
PIPE_V; every chain in that round has the same positive total compute work h.
Widths, chain depths, h and reduction work r may differ between rounds. The
previous reduction root is exactly the predecessor of all next-round chain
heads; the last reduction root is terminal. The recognizer rejects other
compute dependencies and COPY-bridge discrepancies instead of pretending
this model describes them. Require W >= 2, a core budget 2 <= K <= 5 and 0 <= s <= x, where s and x
are the same-core and cross-core Task waits from the supplied configuration.

By default use one intact-chain Task per active core, then a separate reduction Task on core 0.
The number A of active cores can be smaller than K and may change by round;
inactive cores receive no empty Task.
The only submitted fields are node_to_subgraph and core_schedules. No timing,
node order, prefetch command or internal pipe schedule is submitted. Task
edges and core-order edges strictly advance (round, phase), proving the joint
Task DAG acyclic. This certifies structural feasibility only; capacity, spill
and actual E0 quality remain to be checked.

The stage recognizer sets its peeling grain to total positive compute work,
so every stage's threshold is one. This matters when one reduction is much
more expensive than all chains: operation count alone does not ensure full
peeling. The guard then checks the resulting chain and binary-tree structure.

## Why the root core may receive more work

First fix A>=2 active cores. For root-core chain count q in [1, W-A+1],
evenly distribute W-q chains among the other A-1 cores. Their maximum count
is m(q)=ceil((W-q)/(A-1)). Consider a
relaxation that removes boundary transfer and spill costs and retains compute
work and Task waits. Single-pipe compute occupies exactly n*h per branch
Task; the reduction occupies r. Its first completion is

    T_0 = max(q*h + s, m(q)*h + x) + r.

On later rounds, the root-core branch starts at T_previous+s, and foreign
branches at T_previous+x. The previous foreign branch's core-order gate is
no later: T_previous already follows that branch by at least x, and x>=s.
After the return dependency to the reduction Task, completion satisfies

    T_next = T_previous + max(q*h + 2*s, m(q)*h + 2*x) + r.

Thus the same/cross wait difference is charged twice in later rounds. Greedy
balancing that considers only the branch launch can miss the return wait.
This is a relaxed-model derivation, not an exact model of official DDR/FIFO.
For this fixed Task template it supplies necessary compute/gate time. It is
not a global optimality certificate over arbitrary cuts or reduction layouts.

## No scan of actual scheduling candidates

For multiplier g=1 in the first round and g=2 later, write

    a(q)=q*h+g*s, b(q)=m(q)*h+g*x, f(q)=max(a(q),b(q)).

a is strictly increasing and b is nonincreasing. Before the first integer
crossing a>=b, f=b; after it, f=a. Therefore a minimum lies at that crossing
or its predecessor. Binary search locates the crossing in O(log W) arithmetic
steps; no-crossing and boundary cases use the corresponding endpoint. On a
tie, the larger q is the largest global minimizer of this relaxed objective.
Choosing it can reduce remote leaves but does not prove lower real DDR cost.
The remaining positive counts differ by at most one.

Evaluate this analytical minimum for A=1..min(K,W). For A=1 the round
contribution is W*h+g*s+r, with no cross-core predecessor. Choose the least
proxy time, breaking ties toward fewer active cores, then the larger root
count. This derives a possible smaller startup width rather than encoding
Fang's later fixed-four-core startup variant (`4f1b9f8be4bbcc98759a19451c108e62e80abb17`).
Only one plan is emitted. There are at most five arithmetic allocation
comparisons, no evaluator calls. Transfer volume may motivate the fewer-core
tie-break, but actual transfer time and spill behavior remain outside the model.

Graph recognition/construction uses the existing fork-stage machinery and
official validation; its full runtime includes their traversal, sorting and
validation costs. O(K log W) describes the complete allocation step only.

## Optional local reduction fusion

`construct(..., fuse_reductions=True)` retains the same allocation and processes
the binary reduction tree in topological order. Fuse an operation into a
current-round branch Task only if both compute predecessors already belong
to that same Task. Otherwise leave it in the residual tail, which runs on
core 0. A residual-tail predecessor prevents all its descendants from being
fused back into a branch. If A=1, the whole tail can be fused and no separate
tail Task is emitted. The plain and fused variants have distinct identifiers.

This rule never creates a dependency between branch Tasks. All remaining
cross-Task dependencies are branch-to-tail within a round or proceed to a
later round, and core-order edges also advance (round, phase). Thus the joint
DAG proof and exact compute coverage survive fusion. Every fused operation
can be executed after its predecessors within its branch Task.

Fusion can eliminate some Task-boundary copies and waits, but can also alter
Task completion gates, FIFO order and memory pressure. In particular, the
allocation proxy above still describes the *unfused* template: it is neither
an exact prediction nor a necessary lower bound for the fused plan. No E0
quality dominance is asserted. This extends the local-subtree idea in Fang's
StageH source `4f1b9f8be4bbcc98759a19451c108e62e80abb17` without its fixed
width, depth and startup-core constants.

## Evidence and next decision

Arithmetic tests may exhaustively compare small relaxed-model domains to
verify the crossing theorem. They are not evaluator-guided plan search in the
solver. Structural tests vary widths, depths, costs and core counts and check
coverage, intact chains, joint Task order and rejection boundaries.

Validation at this draft: eight synthetic/arithmetic unit tests pass via
`python -m unittest discover -s tests/q1 -p test_gated_root_frontier.py -v`.
These include changing active-core counts, very expensive reductions,
balanced and comb trees, and full-tail fusion with one active core. They do
not invoke the official scoring simulator or any official case.

No official case improvement or unseen-family performance is claimed by this
prototype. The existing 100 official graphs already informed research. The
next useful test is a small predeclared synthetic comparison of the generic
frontier baseline, the plain candidate and the fused candidate, varying
tensor traffic while keeping compute/gates fixed.
A loss with large cross-core tensors falsifies the use of gate-only counts as
an E0 optimizer; it need not falsify the restricted graph recognition or Task
DAG proof. Any future online portfolio can retain the baseline and compare
this single structural candidate, with the extra scoring cost charged to the
solver. Such integration and scoring require their own fixed source/window.
