# P2 tree packets first: one ordering intervention

2026-09-25. This candidate follows the already recorded diagnosis in
`TREE_TRACE_DIAGNOSIS.md`. It changes one mechanism: defer residual skeleton
joins until all complete packets assigned to each core have been submitted.
It does not change the tree guard, fixed W/(2k) pieces, LPT ownership, skeleton
ownership, packet-internal postorder, or COPY byte count. No score search or
parameter grid is used. The frozen `tree_frontier.py` remains byte-for-byte SHA256
`0ea6976bc0d29cab898a40d040077cf6bfc07c7584d5141769a616a62f5a8ed2`.

## Interface and implementation

`src/q2_nikolastarx/tree_packets_first.py` provides `build(graph,cores,config)`
and `build_from_index(index,cores,config)`. It builds exactly one DAGIndex and
calls the frozen `tree_frontier.build_from_index` exactly once. This is reuse of
its deterministic pieces/ownership, not an online candidate selection. The
wrapper then changes each submitted core sequence from interspersed P/S nodes
to `[all original packet nodes in their existing order] + [all original skeleton
nodes in their existing order]`. Outputs contain only `node_to_subgraph` and
`core_schedules`.

CLI matches `evaluate_matrix --solver-mode direct`:

```sh
python -m src.q2_nikolastarx.tree_packets_first case.json --cores 4 \
  --config config.txt --output plan.json --evidence online --wall 240
```

It records one `tree_packets_first` attempt and E0/E1/E2 calls all zero. Existing
output/evidence is not overwritten. Unsupported graph structures fail explicitly;
there is no new router, fallback, or case-specific table. Frozen adaptive source
is not modified.

The wrapper independently verifies that declared packets are complete disjoint
subtrees, every packet op retains its declared core, work/cardinality agree, and
packet plus skeleton covers all original eligible ops. Original compute
precedence plus per-Pipe FIFO is checked by a DAG longest-path pass. Official
`derive_multicore_plan` performs structural validation. Per-core raw tensor
first/last touch peaks are recalculated, including shared graph inputs.

For diagnostic visibility the wrapper calculates both old and new fixed-compute
FIFO lower bounds. They never select or reject a candidate on score. All this
work, including the single base construction, its existing diagnostics and the
two DAG passes, belongs in solver end-to-end time. The thin wrapper avoids an
unsafe refactor of frozen source but retains some diagnostic overhead; the
static function timings are not full solver wall times.

## Why reordering is legal in the original dependency model

Every selected complete packet contains every compute predecessor of each member.
Thus no skeleton op or other packet is a compute predecessor of a packet op.
All packet-internal dependencies are preserved. Packet-to-skeleton dependencies
remain forward because packet nodes are moved earlier. Skeleton-to-skeleton
relative order stays a projection of the original common topological order.
Equivalently, one can take the original global postorder, stably partition it
into all packet nodes then all skeleton nodes, and project it onto cores. The
result is the submitted sequence on every core. Hence adding complete per-core
order edges to original dependencies cannot form a cycle.

The explicit tensor-tree guard rules out additional hidden contracted-only
compute dependencies. Singleton rank still determines the official original
compute FIFO. Moving cross-core-dependent skeleton buckets behind independent
packets removes that particular source of MTE2/V head blocking. This is not a
proof of full transformed runtime feasibility or an official Makespan bound.

Tradeoff: more completed packet roots may remain live before their skeleton
consumer. Metadata lists the sum of all packet-root bytes per core as a boundary
reserve, and independently scans all raw tensor intervals. Neither that sum nor
the raw peak covers every COPY/Step2/Step3 lifetime or allocator dependency.
`zero_spill_claim` stays false. A deferred skeleton can also delay a useful local
join; the candidate is not claimed to dominate the prior word universally.

## Static tests and the three prescribed original graphs/core cells

Six synthetic unit tests pass, including one-core/three-core structure checks,
empty-packet behavior, fork/partial-packet rejection, unchanged ownership and
packet order, deterministic record shuffling, raw peak scan, cycle rejection,
and CLI zero-calls/hash/overwrite behavior. An initial multiline test-context
syntax error was fixed before any test or official-graph construction ran; it
caused zero solver/evaluator calls.

The one static construction per062-k2/k4/k5 is archived under
`results/a/q2-nikolastarx/tree-packets-first-static-20260925/`. Each uses one index,
passes official derive and original-plus-full-core-order DAG acyclicity, and
matches the old pieces, per-core compute work, singleton IDs, ownership, cut
edges and no-spill COPY bytes exactly. The saved before-bounds also match the
independently derived values from the original official trace diagnosis.

| cores | old fixed-compute-FIFO lower bound | new bound | change | changed core orders | max raw L1 / UB bytes |
|---|---:|---:|---:|---:|---:|
|2|1513704|1513740|+36|1|7680 / 18432|
|4|1005132|843852|−161280|2|7680 / 16896|
|5|670344|670344|0|3|7680 / 16896|

All raw peaks fit the fixed capacities. The k4 UB maximum remains16896; some
cores retain one more1536-byte value. k5 increases some individual raw peaks but
still has ample capacity. k2's +36 and k5's unchanged bound are retained rather
than selecting only the favorable row. A lower lower-bound is not a performance
prediction; no new official score or zero-spill result exists for this candidate.

## Bounded next experiment and later work

Root should freeze this source/runner and evaluate exactly the three saved cells
with unchanged official E0, recording legal completion, Makespan, spill, total
extra DDR and solver end-to-end time separately from external E0 time. The
single hypothesis is that packet-before-skeleton words eliminate observed
unnecessary serialization, particularly k4. Keep all outcomes, including k2/k5
regressions or ties. No threshold tuning, ownership change or matrix expansion is
part of this intervention.

If k4 improves, residual ownership imbalance remains: core1 contains645 leaves
while three other cores contain512. The separately suggested next direction is
continuous leaf-chain intervals balanced by compute-Pipe work, with local
reduction subtrees retained on their owner and only boundary-spanning ancestors
placed in the skeleton. It is not implemented here. A two-leaf internal pipeline
is another separate mechanism. Both should be isolated from this ordering test;
a95-million-state DP preserving current words has no rationale from the trace.
