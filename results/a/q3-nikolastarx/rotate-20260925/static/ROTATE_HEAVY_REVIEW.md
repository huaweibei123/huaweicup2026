# Alternate the two heavy lane cores as successive stage collectors

2026-09-25 local date. Independent mathematical review and static calculations;
**0 new official E0 calls**. Production adaptation is confined to the explicitly
authorized stage_fork_join constructor and its tests. No original op or tensor
is changed, no lane chain is split, and no parameter grid is used.

## Specific mechanism

Keep each immutable-input lane assigned to the same core in every stage.
Retain the original binary ADD reduction tree. Pure-local ADDs remain on their
lane owner; all mixed ADDs in a stage use that stage's collector. The stage
order remains complete lane chains, pure ADDs, mixed ADDs.

When exactly two active cores have maximum lane work, alternate these two
cores as collectors, starting with the smaller core ID. Under 12 lanes:

- k2: lane counts [6,6], collector cycle [0,1].
- k5: lane counts [3,2,3,2,2], collector cycle [0,2].
- k3/k4: three/four tied maxima; the new policy explicitly rejects these
  patterns. This does not prove all other collector schedules are useless.

`construct(index, cores, collector_policy="fixed")` remains the default.
The explicit `rotate_heavy` policy raises UnsupportedStructure if its guard
fails, rather than silently returning the fixed policy. No case IDs are used.

## What the fixed DAG makes unavoidable

Let C=4*524=2096 be an intact lane's compute work. In a noninitial stage,
let a be the previous stage root's core, b the current root's core, n_c the
number of intact lanes placed on core c, and d_c the minimum original scalar
ADD path work from any of those lane tails to the current root.
All work is on one V slot per core; delta=500 is the frozen cross-core delay.
Then the stage root-to-root interval satisfies

    T >= max over active c [n_c*C + delta*[c!=a] + delta*[c!=b] + d_c].

Proof: no lane op on c can start before the previous root plus its incoming
communication lag. Serialized lane work totals n_c*C, so some last lane tail
finishes no earlier than that time. That tail remains an ancestor of the root,
and must execute its remaining original ADD path. If c!=b, that path crosses
cores at least once. Taking the maximum gives the bound. ADD work that shares
a lane core can only increase the time; ignoring its FIFO cost is valid for a
lower bound, never an achievable-time prediction.

The first eight lanes have four original ADDs to the root (52 cycles), the
last four have three (39 cycles). The general floor d_c>=39 is safe.

For k4 with three lanes per core, at least one heavy core lies outside {a,b}:
its path pays both 500-cycle legs. Therefore T>=3*2096+1000+39=7327.
Any changed whole-lane allocation giving a core at least four lanes instead
has T>=4*2096+39=8423. Consequently **7327 is also a lower bound for any
whole-lane allocation to at most four cores**, allowing root changes and lane
permutations. The current exact compute-model interval 7366 is within 39
cycles of that restricted optimum; its observed official interval 7372
includes mechanisms omitted by the model. There is no claim that all 1000
cycles can be removed while retaining this allocation family.

For k3, the corresponding whole-lane bound is 4*2096+1000+39=9423; current
fixed model gives 9449. A load >=5 lanes already exceeds this lower bound.

For k5, the two heavy cores can be a and b. Each heavy path then pays only one
500-cycle leg. The light cores pay two legs, but

    2*C+2*delta = 5192 < 3*C+delta = 6788.

Both heavy cores contain only first-eight lanes, so their d_c=52 gives the
stronger necessary bound T>=6840. The actual constructed interval is 6892,
not 6840; original ADD work and FIFO account for the rest.
For k2 alternating roots, the analogous depth-sensitive bound is 13128;
the actual constructed interval is 13167.

This gain mechanism needs enough lane work to hide a light core's extra
communication leg: with counts m on each heavy core and m-1 on the others,
C>=delta suffices for that lane-only inequality. The production guard proves
validity from structure, not guaranteed speed for arbitrary C/delta; actual
performance remains subject to the precise static plan and official check.

## Why cross-stage compute pipelining cannot solve it

Every computation in stage s is an ancestor of its root. Every head in stage
s+1 depends on that root. Thus all previous-stage computations finish before
any next-stage computation can start. Original COPY/immutable-input prefetch
can overlap in the fuller model; that does not change this compute theorem.

Splitting vector chains escapes the intact-lane family but introduces
32768-byte internal tensor transfers; it is a different untested mechanism.
Do not apply n_c*C after counting only heads or tails. As a concrete boundary,
put all 12 heads on core0, then distribute the remaining 3 ops per lane to
four other cores (3 lanes each), previous/current root on core0. With delta500,
there is a relaxed-model schedule whose tails finish by8360 and whose final
root finishes by9003 after return delay plus all143 ADD work. Counting 12
whole lanes on core0 would falsely claim at least25191. Actual per-core op
work, not a fictitious full-lane count, is needed once chains are split.

## Static results for this one construction

`pipe_bound.analyze` independently validated original tensor dependencies,
singleton coverage, original M/V duration semantics, induced FIFO acyclicity,
and frozen config delta500. Candidate numbers below are optimistic lower
bounds on a successful official execution, **not official performance**.

| input / k | fixed L500 | rotating L500 | fixed/rotating steady intervals |
|---|---:|---:|---:|
|051 / 2|326884|315982|13641 / 13167|
|051 / 3|226276|not applicable|9449 / not applicable|
|051 / 4|176284|not applicable|7366 / not applicable|
|051 / 5|176596|165369|7379 / 6892|
|024 / 5|744779|696053|7379 / 6892|
|016 / 5|2250095|2102021|7379 / 6892|

For k5 stage0 is6853, later stages add6892. Therefore N stages yield
6853+(N-1)*6892 in this precise model. Stable-period improvement is487 cycles,
not500: changing collector moves scalar ADD load from the old light core to
a heavy core. Per-stage scalar work alternates between
[104,0,13,13,13] and [13,0,104,13,13], on top of lane work
[6288,4192,6288,4192,4192]. The current heavy root core thus has6392 work.

Pure/mixed ordering remains topological: a pure ADD cannot depend on a mixed
ADD because descendant core sets only grow toward the root. Within each stage
a lane-to-root path moves to that stage's collector at most once. The next
stage can have a different collector without creating a compute/FIFO cycle.

## Cache and COPY boundary

Frozen P3 `copy_tensor_info` uses the non-DDR tensor's `logical_tid` (falling
back to its tensor ID), not source_core, as Cache key. Reassigning a root does
not itself rename its original logical tensor. Each stage has a distinct root
tensor; changing collector does not manufacture cross-stage scalar reuse.
Original immutable lane tensors and their owner stay fixed.

However, which pure-to-mixed boundary tensor is remote can change, as can
source/destination core, generated COPY IDs and execution order. Cache hits
are determined at COPY_IN issue, so equal logical identity does not imply
identical hit counts or timing. Unexpected spill would add further traffic;
there is no zero-spill guarantee here.

A static scan of raw tensor producers/consumers gives identical *connection
counts* for fixed/rotating k5:236,1006,3046 for051/024/016; all crossing tensors
are2 bytes. This is not measured traffic and excludes original input/output
COPY service and any spill. It only rules out hidden 32KB lane-chain cuts.
The 500 lag is mandatory even on Cache hits; official scalar COPY service and
contention mean an observed interval is not exactly this abstract expression.

## Compatibility and verification

The fixed constructor plan and metadata serialized bytes match the pre-edit
snapshots for051 k2/k3/k4/k5 and024/016 k5. The rotating production output is
identical to an independently assembled draft plan on each of the three k5
graphs. Eight stage tests pass, including deterministic four-stage collector
rotation, unchanged graph, fixed lane ownership, original ADD owner/routing,
a synthetic exact one-leg benefit, explicit nonapplicability, and old guard
failures. Test checks invoke static validation only, never E0.

Scope: one explicit construction, six static read-only graph/core checks,
three production k5 output checks. k2 has no formal performance sample in this
research batch. Source/input/plan hashes are recorded separately in this folder.
