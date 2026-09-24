# Unified P1 return-cut v2 (three-cell integrated validation)

Baseline: frozen v1 algorithm `48faef6f1386c3dc7d037674a38af29d533ba774`,
full500 run `20260924T1810Z-s59ee`, five-core arithmetic mean 3.987519066.
The v1 evidence remains v1. It is not relabeled as a v2 result.

V2 adds one graph-derived candidate to the same fixed controller. A cheap
necessary shape guard requires both M and V compute pipes and exactly twice
as many M ops as independent components. The archived Pro recognizer then
requires private, homogeneous M→V+→M components, checks excluded-COPY bridges,
shared tensors and original output taps. The constructor sums every touched
tensor separately for one new prefix and one old return, accounting for DDR
inputs in UB; packet size is the minimum capacity quotient and the largest
number of chains on a core. All chains are cut before their final M. No
ideal-model scorer, case ID, saved plan, or empirical score chooses the packet.

A mixed Task contains a packet of new prefixes and the previous packet's
returns; the submitted result still contains only node_to_subgraph and
core_schedules. Augmented Task DAG validation checks coverage and order.
Capacity sums are a conservative design guard; actual official compilation,
spills, FIFO order, DDR contention and makespan still need E0 validation.

The five-candidate online guard retains earlier candidates. Inapplicability
or construction failure skips the new candidate, while the first scoring
failure stops scoring and retains the prior checked winner. K1 still emits
only the bounded candidate and performs zero E1 calls. Budget changes are
explicit: at most five distinct plans/E1 calls per multicore cell, a worker
lifetime of five plans, same60s/request and10s startup limits, zero retries.
Variant is structural-five-plan-return-v2. An eventual full500 batch must
freeze this new source and budget up to2000 E1 calls separately; it is not
implicitly authorized by the earlier1600-call v1 batch.

The experimental constructor source e566dd5ce6a1737880ca88d35964bfd846bc4512
was tested once on real084/k5, run20260924T1830Z-capacity084: official E0
makespan399121 versus fixed-v1 503472 (-20.7263%), scheduled copies23161962B,
added copies9925632B, spill0, memory-dependency count0. Derived packet5,
solver wall0.186608500s, externalE01.471868250s; one solver/oneE0/no retries.
This proves one mechanism benefit, not integrated v2 quality or generality.
008 previously regressed with a different return-cut candidate; the online
guard is therefore essential. No wholesale adoption without integrated E0.

Validation so far:25 synthetic tests (Python3.12.13), including original
controller tests, capacity boundaries, partial packets, shared-input
rejection, both beneficial and harmful candidate scoring, and the K1 fast
path. A subsequent fixed-source run `20260924T1844Z-return3` completed
008/084/095 at K5: 3 solver calls, 9 E1 calls, 3 external E0 calls, no retries.
Selected official Makespans were 100603, 399121 and 420852 respectively.
Only 084 selected the new return candidate; 008/095 retained the bounded
candidate. All selected E1 Makespan and movement values matched E0.
Data commit: `f552c2c5e87f2d760bda2f9a0a3b175d4f99157c`.
This is three-cell validation of v2, not a new full500 result. Future batches
still require coordination with the production owner. The research priority
and remaining generalization limits are in [Q1_GENERALIZATION_STRATEGY.md](Q1_GENERALIZATION_STRATEGY.md).
