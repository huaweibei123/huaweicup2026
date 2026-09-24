# Shared-input waves with a core budget

After the ee1 full500 regression audit, this entrypoint preserves whole-component
ownership when enough independent components exist. It no longer infers that
internal splitting helps from `largest_component_work > balanced_work` alone.
The old `adaptive_frontier` entrypoint keeps its frozen policy for reproducibility.
This revision is later than the b4 active-core prototype and requires its own
full-suite run; neither b7 nor ee1 results are its achieved scores.

All twenty four-core and twenty-two five-core regressions in the paired audit
belong to the added `dominant_component_dag` route. It also improves eight and
nine cases respectively, so this is not a theorem that splitting is useless.
Each shared-input-wave route improves all nine cases at each of those core
counts. New split proposals need a cost decision that accounts for COPY and
memory, rather than the failed balance-only proxy. E2's current P2 interface
can compare complete plans, but new-plan cold preparation is substantial and
its existing 32-plan validation does not cover this new candidate family.

`adaptive_budget` is a new algorithm version. The completed `ee1b8fd` / `adaptive_frontier` full500 does not use this
new version. Source2794 now has one independently produced official pilot
(044/k4); its own full500 has been commissioned and remains pending.

## Why fewer cores can help

For `n` repeated independent jobs, let `W` be a job's largest Pipe workload,
`H` its compute critical path, `S` the bytes of inputs shared by every job,
`P` the remaining distinct external-input bytes, and `B` the DDR bandwidth.
For `q` balanced active cores, use the relaxation

`L(q) = max(ceil(n/q) W, ceil((q S + P)/B), H)`.

This ignores output traffic, COPY eligibility/delay, queue order, overlap
constraints and spill. Its optimizer is a construction heuristic, not an
official optimality proof or performance guarantee. It applies only after the
existing repeated-component guard and positive integer M/V-work checks.

The compute term is nonincreasing and the input term nondecreasing. Find their
first crossing by binary search, and compare that point with its predecessor.
Before the crossing the maximum equals compute; after it equals input. The
constant critical-path term preserves the minimum but can extend a plateau.
Given minimum value `F`, the earliest compute-feasible core count is
`ceil(n / floor(F/W))` for positive `W`, clamped to the allowed minimum. Input
traffic cannot increase on moving left from a minimizer. Thus this selects the
smallest minimizer in `O(log k)` arithmetic, without constructing and evaluating
a grid of plans. Work zero is handled separately.

Read-only workload extraction from the frozen input graphs predicts two active
cores for 044 under a five-core budget, four for 083 under four, and five for
092 under five. These are predictions from the relaxation, not new results.
For 044, the compute/input pairs for q=1..5 are
74404/15883, 40584/31389, 27056/46896, 20292/62403, 20292/77909 cycles.

## Capacity guard and scope

Fewer cores mean more jobs per core. For each actual job, project the existing
wave sequence onto that job and compute its private-tensor raw touch peak.
Take the largest per-pool value `Pmax`. At most one shared wave input is live
under the recognizer, so `m Pmax + Smax` bounds raw priority touch for a group
of at most `m` jobs. Private aliasing and ID-dependent traversal are handled by
scanning every job, not assuming job 0 has every private lifetime pattern.
See [the capacity derivation and corrected boundary counterexample](WAVE_CAPACITY_DERIVATION.md).

This bound restricts the minimum active-core count. If even the requested
count cannot satisfy it, retain the existing requested-core wave plan and
report the uncertainty. Passing the bound is not an official zero-spill
certificate. The new guard falling outside its domain also preserves the old
wave route. Exactly one final plan is constructed and empty schedules pad it
to the requested core budget. No case ID, stored score or online evaluator
controls the choice. Recognition and private-lifetime scans are linear in
the represented graph apart from the existing recognizer's matching work;
the legacy wave builder currently repeats recognition once, included in
future measured solver wall time.

Validation uses exhaustive small-domain comparison of the binary-search
optimizer against direct arithmetic enumeration, plus synthetic padding,
capacity rejection, fallback preservation and existing adaptive-route tests.
Whole-suite regression and aggregate quality remain pending.

## First official core-choice pilot

Source `2794ceba93acc1f7fc119154f61082511843d4b3`, runner
`696186ec328b31a988ce9f35b9b38cac32c8ab1e`, immutable result commit
`4526add27e180f2f6e18859a4c207df43de377db`. Production ran 044/k4
once: one cold solver and one final E0, zero online E0/E1/E2/retries.
The formula selected two active cores under a four-core budget. Official
Makespan is 43,795 cycles, extra DDR 930,400 bytes, spill zero. The prior
shared-wave four-active-core plan measured 66,901 cycles and 2,791,200
extra bytes. This is a 34.54% Makespan reduction on this cell only.
Solver wall was 0.197130s; external final E0 0.274407s.

Root verified all23 artifact files equal the fixed result commit, read the
compressed official result, checked zero exit/survivor receipts and that the
three recorded driver/solver/E0 PIDs no longer existed. Production authorship
and this read-only verification remain separate. These results do not prove
the relaxation exact on other structures or replace a fixed-algorithm full500.

A separate2794 full500 has been commissioned: 100graphs x1–5cores, one cold
solver and final E0 per cell, no score-table selection/online E0/E1/E2/retry.
Declared limits: solver25s, E060s, cell95s, batch1800s, at most four independent workers with total sampled
process-group RSS4GiB. The former one-worker arrangement was a conservative
resource choice, superseded before dispatch; all500 cells remain unique.
Shared-host concurrent wall times are not isolated throughput benchmarks. The production owner freezes its runner/manifest before dispatch.
Failures/missing cells remain visible; this is authorization, not completion.
