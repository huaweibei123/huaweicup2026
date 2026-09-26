# P1 two-structure selector, revision 1

The completed Stage C experiment exposed genuine wins and losses. Stage D's
five results were all worse and that variant is excluded. This new revision
retains exactly two direct constructions: the captain's frozen bounded
component/tree-frontier constructor at
`05f8fa0f7e52f5914f14815f6bdbcb851b631556` (factor 4, trigger 4096, chunk 1024),
and our Stage C chain-atomic fork-stage frontier (grain 4, per-core Tasks).
The first is attributed in `src/q1_yuanzhifang/upstream_bounded/provenance.json`;
only root-path depth and two relative imports differ from those fixed sources.
This is cooperative reuse of the captain's implementation, not a claim of
independent authorship.

For each candidate, compute `G + D`, where `G` is the fixed-plan compute/Task
gate lower bound and `D` is the service cycles of all mandatory Task-boundary
COPYs, with official per-copy rounding at the configured bandwidth. Prefer the
fork candidate only on a strict decrease; otherwise use the bounded plan.
One core retains the bounded constructor directly. There are no case IDs,
stored plans, E0 scores, learned parameters, random restarts, or online
simulation in the selector. All candidate construction and structural
validation are included in the cold solver process wall time.

`G + D` is an **overlap heuristic**, not a proven lower bound, upper bound or
actual runtime predictor. It deliberately penalizes excess cuts and repeated
input copies. Compute and DDR can overlap, FIFO and spills can delay them, and
the true critical path can differ. The sum has no performance dominance
guarantee. Both candidates have structural acyclicity proofs, but neither the
selector nor those proofs replace the final official capacity/deadlock check.

The boundary count uses the same tensor incidence predicates as frozen E0:
one input COPY for each consumer Task without a local producer; one output
COPY for each producer Task with an original COPY_OUT, no eligible consumer,
or any consumer in another Task. Multiple consumers in one Task count once.
This counts mandatory copies before spill. Direct operation edges carry Task
dependencies without inventing tensor bytes. Task-private copies are counted
even when the two Tasks share a core.

For two fixed candidates, counting copies is linear in tensor/edge incidence;
topological paths cost O((V+E) log V) with the current heap implementation.
The existing bounded constructor can additionally pack independent chunks,
and its existing first-fit cost is retained and measured rather than hidden.
This is a fixed structural choice, not bounded brute-force partition search.

Development exposure includes A/B/C/D and the captain's published full matrix.
All 100 official inputs remain public development data, not a held-out test.
Freeze before the next batch; retain every failure and regression. Reusing an
old E0 quality result is allowed only with identical plan bytes, graph,
configuration and official code identity, explicitly separate from newly
measured solver wall. No score is claimed by this proposal document.
