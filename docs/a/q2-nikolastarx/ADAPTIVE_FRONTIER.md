# Component balance and shared-input waves

New entrypoint: `python -m src.q2_nikolastarx.adaptive_frontier`. This is a new
algorithm version requiring its own complete 100×5 evidence, not a change to
the fixed b7 results or a selection of historical winners.

The existing resource-word, reduction-tree and vector guards are retained.
Where the old general route used only the number of components, compute each
component's mandatory work per Pipe and compare the largest with the balanced
whole-graph work per Pipe, `ceil(total_work/cores)`. If a component exceeds that
target, use the existing tensor-aware DAG constructor to allow internal splits.
This detects an indivisibility obstruction; it does not prove that the graph
admits enough parallelism, that the balanced target is attainable, or that the
new official score improves. COPY and memory costs may outweigh load balance.

Otherwise, if external tensors reused across components exceed a memory-pool
capacity, attempt the guarded shared-input wave construction. It matches full
component signatures and schedules the dependency closure of corresponding
shared-input consumers across local components. Unsupported templates retain
the old component-envelope construction. It may still have an oversized
activation frontier; raw touch peaks are not runtime zero-spill certificates.

There is no tunable threshold or case-name selection. Each selected mechanism
constructs one plan, without online E0/E1/E2. The inherited vector-cut repair
can still replace the general proposal with one structurally triggered plan;
both construction steps are included in solver wall time.

Static 056/k5 diagnostic: existing source DAG construction changes the fixed
compute-FIFO lower bound from 253,026 to 67,967 cycles; mandatory assigned Pipe
work is 51,826 cycles. Its independent-COPY timing proxy is 109,810, compared
with the old measured official 253,392. These are different quantities. The
proposed crossing traffic is 7,038,604 B, so real communication may dominate;
no measured improvement is claimed before E0. This pilot is particularly useful
for deciding whether to develop the more local attention-row construction.

Validation so far: meaningful synthetic routing, coverage and wave-lifetime
checks, plus static original-graph constructions. Official performance and
all-case nonregression remain unverified. Frozen old b7 data remain unchanged.
