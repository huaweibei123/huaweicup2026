# Interleave two homogeneous leaf chains

The previous packets-first construction removed a remote-join stall on 062,
but its existing official traces still contain 6,534 gaps between consecutive
matrix operations inside the covered leaf chains. Almost all are 36 cycles:
one chain waits for its vector operation while another independent chain is
available. This candidate changes their local order, keeping ownership,
packet membership, packet order and the skeleton policy fixed.

## Rule and exact scope

Recognize a binary V join whose two input branches are complete unary chains
starting at compute sources. Both chains and the join must form one contiguous
block on the same core, wholly inside one existing closed packet. Both chains
must have the exact same constant-duration signature `(M(a), V(b))^r`, with
`r >= 2` and `0 < b <= a`. All other nodes remain in their previous order.

Replace `A1,A2,...,B1,B2,...,join` by the layer word
`M_A1,M_B1,V_A1,V_B1,...,M_Ar,M_Br,V_Ar,V_Br,join`.
The source guards derive these properties from the graph, not case IDs or a
table of known scores. There is one candidate, zero online evaluation and no
parameter search. The emitted full core order is checked for acyclicity.

## Local tight bound

For two independent chains on dedicated, initially idle M and V pipes, with
all inputs ready and no COPY or memory constraints, set `S_j=2(j-1)a`.
The two M intervals in layer j are `[S_j,S_j+a]` and `[S_j+a,S_j+2a]`;
the V intervals are `[S_j+a,S_j+a+b]` and `[S_j+2a,S_j+2a+b]`.
Because `b <= a`, every next M is ready when its pipe becomes free. M is
continuously busy until `2ra`, and the second terminal V ends at `2ra+b`.
Any schedule must execute `2ra` units of M work, and its last M still has a
V successor of duration b. Thus `2ra+b` is a tight bound for this local model.
A common terminal V join of duration c adds c. The original two closed-chain
words take `2ra+(2r-1)b+c` in this model.

This does not prove global official optimality. Variable layer durations need
cross-layer conditions: `(a,b)=(2,2),(1,1)` yields 8 before the join, exceeding
the tempting formula 7. Differing chain lengths, extra dependencies, late
inputs, COPY contention and capacity constraints also require separate
analysis. A synthetic raw-memory example increases UB peak from 17 to 24
bytes after weaving, so local timing optimality cannot certify zero spill.

The implementation reuses the existing tree construction, then scans binary
joins and verifies disjoint candidate blocks. Traversed unary chains are
disjoint in the guarded tree, so detection and rewriting are linear in graph
size after indexing; the inherited heap-based graph/FIFO checks retain their
O((N+E) log N) cost. There is no dependence on a search budget.

## Evidence before official validation

Seven synthetic tests passed in the root process. They cover the ideal formula
at twelve parameter points, a memory counterexample, unsupported signatures,
nonconstant durations, packet boundaries, ownership and dependency invariants,
and the zero-online-call CLI. Scoring and process-spawn entry points are
poisoned in the relevant tests.

One static construction per k=2,4,5 on 062 found 1,089 pairs, covering 8,712 of
8,728 M operations (99.82%). Fixed-plan compute lower bounds changed as follows:

| Cores | Previous bound | Woven bound |
|---|---:|---:|
| 2 | 1,513,740 | 1,388,724 |
| 4 | 843,852 | 774,252 |
| 5 | 670,344 | 615,048 |

All raw-priority peaks fit the frozen capacities; these omit some transformed
runtime lifetimes. These numbers are **not E0 scores**, and reducing a lower
bound alone does not prove an improvement. The associated source/input hashes,
plans, original-trace evidence and function-only timing are under
`results/a/q2-nikolastarx/tree-paired-leaves-static-20260925/`.
The initial subagent completed these files but stopped on a usage limit before
handoff; the root subsequently inspected them and reran the seven tests.
