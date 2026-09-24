# Repeated vector-lane / fixed scalar-tree stage construction

Construction design and static checks before the first official experiment. No official E0/E1/E2 calls in this note.
Production: src/q3/stage_fork_join.py; original prototype fingerprint below.
SHA-256: c5fea604f3aa7f5ab44febb4d4ff1e3a306dcbdf07770240214e425b57b225bd
Static values below are diagnostic lower bounds, not official performance.

## Recognized graph family and legal submission freedom

The three observed graphs contain 24/101/305 repetitions of the same stage:
12 original vector lanes, each 4 original PIPE_V operations of duration 524,
followed by the original 11 binary ADDs of duration 13. Every lane ends in
an original REDUCE, producing 2 bytes from a 32768-byte vector. The stage root
broadcasts its 2-byte result to the next stage's 12 heads. The original ADD
reduction tree has three 4-lane subtrees combined as 8+4; it is not re-associated.

Each lane repeatedly reads the same original immutable L1 tensor, supplied by
its own original COPY_IN from a matching DDR tensor. Lane identity is that
original tensor ID, not the case name, operation number, or a measured score.

The guard checks exact tensor ports, one compute output with a unique original
producer, UB compute intermediates, L1 immutable inputs, original COPY_IN/OUT
endpoints, repeated lane signatures, repeated original ADD-tree shape/durations,
correct broadcast heads, and complete original compute coverage. Additional
COPY bridges, hidden lane inputs, multiple producers and unrecognized operations
are rejected. All original operations and graph edges remain unchanged.

## Direct construction

1. Assign contiguous lanes in stable immutable-input-ID order to k cores using
   floor(lane_position*k/lane_count). Keep each lane's core across all stages.
2. If every descendant lane of an original ADD is on one core, place that ADD
   on that core. Otherwise place it on a fixed collector core, chosen among
   active cores by least assigned lane work, then core ID.
3. For each stage emit one global compute order: complete original lane chains;
   all pure-local original ADDs in topological order; all mixed original ADDs
   in topological order. Project this order onto each core's singleton schedule.

Pure-local ADDs cannot depend on a mixed ADD: descendant-owner sets can only
grow while moving toward the root. Therefore this three-part order is a linear
extension. Appending the next stage after the old root also preserves the actual
broadcast dependencies. Arbitrary per-core projection is consequently acyclic
for original compute plus induced compute order. Static derive validation is
not a proof of complete official COPY/memory/FIFO execution.

The three-part order matters: a naive entire-tree DFS can append a remote-data
ADD to the collector before its remaining local lane work, turning a short
scalar wait into head-of-line blocking of large independent vector operations.
Finishing all lane chains first retains only small REDUCE outputs; it does not
keep all large vector intermediates alive.

## Communication-height guarantee without changing the reduction tree

On a fixed lane-leaf-to-stage-root path, descendant-core sets start as one core.
They either remain one core, or become mixed at a single first ancestor and
remain mixed thereafter. Thus the owner path is

    lane core ... lane core -> collector ... collector,

with at most one cross-core computation edge during scalar gathering. If the
lane already belongs to the collector, there is no such transition. The next
stage's root-to-lane broadcast adds at most one more cross-core transition.

This limits communication *height*, not total bytes, COPY count, cache misses,
or total E0 time. All the transitions are on the original 2-byte scalar tensors;
no original 32768-byte vector chain is split. A broadcast tensor has many compute
consumer edges but P3 creates a COPY pair per destination core, so compute-edge
count is not COPY-pair count.

For 051/k4 the current lane groups have 3 lanes each. Six pure-subtree scalar
outputs per stage cross to the collector; three destination cores receive the
root broadcast for each of the first 23 stages. Hence there are 213 structural
source-core/target-core tensor connections in this simple family, although the
compute graph has 351 cross-core producer-consumer edges. The corresponding
2-byte payload sum is 426 bytes; neither number includes initial DDR reads or
proves measured physical traffic. Actual official traffic must come from E0.

## Per-stage lower bounds and restricted-model upper bounds

Stage work is W_s=48*524+11*13=25295; original within-stage weighted critical
path is P_s=4*524+4*13=2148. Original broadcast dependencies force all compute in
stage s+1 to follow stage s's root, so for k V pipes a compute-only lower bound is

    sum_s max(ceil(W_s/k), P_s).

For 051/k4 this equals 24*6324=151776. The familiar whole-graph W/k=151770 is
slightly weaker because it omits per-stage integer barriers. These are optimistic
lower bounds, not expected official performance.

Let C be one lane-chain work, a the scalar ADD work, n_c the lanes on core c,
p_c the pure ADD count, and m the mixed ADD count. Define Q_c=n_c*C+p_c*a.
In a computation/Pipe model with fixed cross delay d and no COPY service or
memory contention, the proposed order gives the following conservative upper
bounds on stage increments:

    first:  max(Q_collector, max_remote(Q_c+d)) + m*a
    later:  max(Q_collector, max_remote(Q_c+2*d)) + m*a.

Reason: wait until every pure subtree result has reached the collector, then
execute all mixed ADDs serially there. The actual fixed-order computation model
can overlap some early mixed ADDs with late remote results, so it may do better.
These are upper bounds only for this restricted model, not upper bounds on E0.
For one active core the remote maximum is absent and all ADDs are pure.

The independent enhanced-Pipe-DAG lower-bound tool, with the frozen d=500,
produced these static values after passing its guard:

| case | stages | k | per-core V work | delay-bound |
|---|---:|---:|---|---:|
|051|24|4|153408,151224,151224,151224|176284|
|024|101|4|645592,636401,636401,636401|743466|
|016|305|4|1949560,1921805,1921805,1921805|2246130|

For 051/k4, original scalar roots finish at 6866,14232,21598,... in that restricted
model: first-stage 6866, subsequent increments 7366. This is a diagnostic value,
not an official Makespan or acceptance threshold. An earlier 051/k5 static
prototype yielded 176596, illustrating the 12-lane indivisibility and collector
cost; it was not scored and is not proposed for the first formal sample.

## Memory and testing boundaries

With three fixed lanes per core, immutable L1 data is 3*32768 bytes. Within one
sequential lane chain, at most two large UB intermediates are simultaneously
needed around an operation; completed lanes keep 2-byte outputs. This explains
why the three-phase ordering has better locality than an unrestricted global
leaf-first schedule. It is not a full official allocation/spill certificate:
COPY timing, version/backing and memory-reuse edges still require E0 validation.

Suggested meaningful zero-E0 unit tests:
1. Build a two-stage, two-lane tensor graph with matching immutable COPY_INs,
   original vector chains, original scalar joins and final COPY_OUT. Check
   deterministic plan coverage, unchanged original graph bytes, fixed lane
   ownership across stages and a global computational linear extension.
2. Add an extra immutable tensor input to an internal lane op without changing
   its original compute predecessor; the exact-port guard must reject it.
3. Change one later-stage lane's immutable identity, or add a second producer
   to a scalar tensor. The family guard must reject; do not silently reinterpret
   the stage or recombine the original tree.

Recognition and construction are linear in total graph size for this fixed
12-lane/59-op family, with bounded per-stage sorting. The initial Index / official
static validation cost is part of actual construction cost. No parameter grid,
random search, re-associated reduction, added operators or evaluator calls were
used in the prototype.
