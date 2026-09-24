# 016 vector lanes: zero spill does not imply a short reduction path

Read-only diagnosis, 2026-09-25. This report reads the six existing official
016 results and their plans/traces from the direct and vector pilots. It runs
**0 solvers and 0 E0/E1/E2 evaluations**, changes no algorithm, and makes no
new performance claim for a proposed plan. The companion analyzer imports only
the Python standard library.

**k4 regresses because the fixed lane/reducer assignment forces serial scalar
crossings on the stage critical path. k5 is a much smaller, different
regression.** Removing spill solved the dominant observed k2 problem; it did
not optimize the reduction/broadcast latency of the resulting plan.

## Frozen results and comparable work

All Makespans below are cycles; DDR amounts are bytes. The input is identical,
with SHA-256 `76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef`.
It contains 17,995 eligible operations, all on V, and 305 dependent stages.
Each stage contains 12 four-operation lanes (4 × 524 cycles each) and eleven
13-cycle scalar reducers. Every plan performs **7,714,975 V work cycles**.

| k | direct Makespan | vector Makespan | vector change | direct added / spill DDR | vector added / spill DDR |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 9,260,226 | 4,170,750 | −5,089,476 (−54.96%) | 419,834,600 / 379,715,584 | 4,876 / 0 |
| 4 | 2,250,687 | 2,552,270 | +301,583 (+13.40%) | 539,552 / 0 | 12,188 / 0 |
| 5 | 2,240,622 | 2,243,707 | +3,085 (+0.138%) | 281,636 / 0 | 12,184 / 0 |

The following arrays are in core-ID order. V work is the sum of observed
operation durations, which the analyzer also checks against the raw cycles.

| Plan | V busy cycles per core | V internal idle cycles per core |
| --- | --- | --- |
| direct k2 | 3,857,468; 3,857,507 | 5,401,148; 5,401,624 |
| vector k2 | 3,859,470; 3,855,505 | 310,185; 313,635 |
| direct k4 | 1,921,935; 1,918,243; 1,937,314; 1,937,483 | 326,018; 329,698; 311,184; 310,500 |
| vector k4 | 1,933,700; 1,925,770; 1,929,735; 1,925,770 | 616,381; 622,765; 619,831; 623,281 |
| direct k5 | 1,919,654; 1,921,711; 1,300,617; 1,286,490; 1,286,503 | 317,197; 316,175; 936,754; 949,285; 950,352 |
| vector k5 | 1,286,490; 1,282,525; 1,937,665; 1,282,525; 1,925,770 | 952,357; 955,807; 303,306; 955,808; 314,673 |

Internal idle excludes the prefix before the first V operation and the suffix
after the last. It is a trace measurement, not an additive attribution of
Makespan. M is unused. The sum of each core's busy MTE durations is:

| Plan | sum MTE2 busy cycles | sum MTE3 busy cycles | cross-core transfers |
| --- | ---: | ---: | ---: |
| direct k2 | 9,985,867 | 9,812,584 | 3,354 |
| vector k2 | 14,349 | 1,222 | 1,219 |
| direct k4 | 51,039 | 3,834 | 3,816 |
| vector k4 | 29,317 | 3,062 | 3,047 |
| direct k5 | 43,372 | 5,039 | 4,873 |
| vector k5 | 32,600 | 3,061 | 3,046 |

These sums can exceed wall time because different cores/pipes overlap; they
are not DDR bytes divided by bandwidth. The full per-core/per-pipe counts,
busy time, span and gaps are in `pipe_work.csv` under the evidence directory.

## A fixed-plan lower bound establishes the k4 obstruction

Following [the reviewed Pro result](PRO_R01_REVIEW.md#3-adopt-the-fixed-compute-fifo-longest-path-bound-with-the-correct-graph-and-replacement-rule),
form a DAG from only (i) frozen raw tensor producer-consumer compute
dependencies and (ii) adjacent eligible operations in each submitted singleton
V FIFO. For this input the analyzer verifies tensor-only incidence,
single-producer tensors, complete singleton coverage and exact equality of
submitted and observed V order. It does not use contracted direct edges through
removed original COPY operations.

Compute nodes have weight `max(1, cycles)`. Across cores, a producer-to-consumer
edge additionally requires source COPY_OUT, the fixed 500-cycle release delay,
and destination COPY_IN. Three relaxations are therefore valid **for this fixed
plan**: no communication lag, 500 per crossed dependency, and
`500 + 2 × max(1, ceil(tensor_bytes / bandwidth))`. The last ignores contention,
COPY FIFO blocking and memory dependencies, so it remains a lower bound.
Longest paths are linear in graph size after topological ordering; no official
evaluation or schedule search is performed.

Source support: P2 `_prioritize_task_seq` lines 43–59 retains singleton compute
order, P2 `external_release` lines 374–379 adds the fixed delay, and
`queue_if_ready` lines 381–404 enforces the Pipe head. `schedule_step3.py`
lines 27–30 specify one slot; lines 74–82 give minimum COPY duration. See the
earlier review for Step2/Step3 order preservation. The input/source bytes are
hashed in `manifest.json`.

| Plan | compute/FIFO LB | + mandatory 500 LB | + minimum COPY pair LB | official minus last LB |
| --- | ---: | ---: | ---: | ---: |
| direct k2 | 3,871,339 | 4,153,196 | 4,155,024 | 5,105,202 |
| vector k2 | 3,863,435 | 4,168,435 | 4,169,655 | 1,095 |
| direct k4 | 1,949,456 | 2,241,241 | 2,243,075 | 7,612 |
| vector k4 | 1,937,665 | 2,547,165 | 2,549,603 | 2,667 |
| direct k5 | 1,929,748 | 2,231,402 | 2,233,228 | 7,394 |
| vector k5 | 1,937,665 | 2,238,200 | 2,239,418 | 4,289 |

The new k4 plan has a slightly *smaller* compute/FIFO bound, yet its mandatory
500-only bound already exceeds the old **achieved** score by 296,478. Therefore
no removal of spill, contention or other optional delays can make this fixed
ownership/FIFO beat old k4 while retaining official cross-core semantics.
This is a causal constraint, stronger than a correlation of totals. It does
not prove a global P2 optimum or predict the result of changing the plan.

For k5 the new bound is **below** the old achieved score; these bounds alone do
not prove its small regression unavoidable. In all vector cells the official
score is close to the bound. Broad further memory tuning of the unchanged
compute plan therefore has limited room; structural ownership/order changes
are the useful next target.

## Exact observed stage paths

Stage numbers below are zero-based. The analyzer saves all 305 root completions
and stage periods and all 59 operations of stage 100 for each plan. It also
checks every result operation interval against the independent Chrome trace
export: 36,312/25,656/27,762 direct and 20,446/24,102/24,100 vector intervals.
This validates export consistency, not an independent rerun of E0.

Vector root-to-root periods are constant over all 304 transitions:
**13,671 / 8,362 / 7,347** for k2/k4/k5. Direct k4 has period 7,348 on 300
transitions; direct k5 has 7,322 on 149 and 7,323 on 152 transitions, with the
remaining transients preserved in `summary.json`.

### k4: three serial reduction crossings plus broadcast

Previous root 5912 ends on core 0 at 838,059. Its scalar reaches core 2 at
838,562, after **503** cycles. Core 2 executes three full lanes plus two
13-cycle reducers before 5963 completes at 844,876. The remaining tight path is:

| Operation | Core | Start | End | From previous row |
| --- | ---: | ---: | ---: | --- |
| 5963 | 2 | 844,863 | 844,876 | three-lane branch |
| 5968 | 3 | 845,378 | 845,391 | 2 B transfer, 502 cycles |
| 5970 | 2 | 845,893 | 845,906 | 2 B transfer, 502 cycles |
| root 5971 | 0 | 846,408 | 846,421 | 2 B transfer, 502 cycles |

Each 502 is one COPY_OUT cycle, 500 release cycles and one COPY_IN cycle; these
three transfers start at their releases. There is no hidden queue delay in
those three links. The initial 503 is the second serialized broadcast
COPY_OUT (two cycles from root completion), then 500 and one COPY_IN.

`503 + 3 × 2096 + 2 × 13 + 3 × (502 + 13) = 8362`.

Core 0 completes its preceding V operation 5969 at 844,386 and then waits
2,022 cycles before executing the root. In the direct trace, operations
5961/5962/5963/5964/5967/5968/5970 reside on core 3; 5970 ends at 751,179,
crosses once to core 2 and the root runs 751,681–751,694. This comparison of
the same reduction suffix explains why fewer total bytes did not win.

The current source assigns DFS-contiguous leaf groups by compute weight,
then each scalar to the core contributing most original lane work to its
subtree (`vector_lanes.py` lines 252–278). The tie-break is core ID. For k4
this creates the concrete return path **2→3→2→0**. Work balance is not a
surrogate for scalar arrival time or number of serial cross-core hops.

The exact total-score difference decomposes into a 3,130-cycle better first
root and 304,713 more cycles across subsequent root periods, totaling
**+301,583**. Final output costs one cycle in both results.

### k5: two-stage crossings remain, but the regression is only 3,085 cycles

At stage 100, previous root ends at 737,571. Broadcast reaches core 4 after
505 cycles; that core executes three lanes and two scalar reducers. 5968 ends
at 744,390, crosses to core 2 in 502 cycles; two local reducers finish the root
at 744,918:

`505 + 3 × 2096 + 2 × 13 + 502 + 2 × 13 = 7347`.

The direct steady periods are 24 or 25 cycles shorter. The first root is
2,622 cycles faster for vector; subsequent periods cost 5,707 more cycles,
giving **+3,085** overall. Its largest core load also rises from 1,921,711 to
1,937,665, although load alone cannot attribute a delta because idle time
changes too. The fixed whole-lane 2/2/3/2/3 distribution leaves a 3-lane
bottleneck; a five-core ideal work division is outside this restricted class.
Keep the distinct global and whole-lane bounds in
[TREE_FRONTIER_THEORY.md](TREE_FRONTIER_THEORY.md).

There is a genuine but noncritical MTE2 head-of-line wait. The transfer from
5969 to root 5971 is released at 743,295, but its COPY_IN 1000021061 starts only
at 744,892, after preceding COPY_IN 1000021058 from 5968. It ends at 744,893;
the local 5970 ends at 744,905. Thus this conspicuous **1,597-cycle** queue wait
has **12 cycles of slack** before the root needs it. Removing it alone would
not advance this stage's root in the observed schedule. Summing all COPY waits
and calling that a Makespan loss would be wrong.

### k2: memory improvement dominates, with a smaller scalar round trip left

Old direct has about 5.4 million V idle cycles per core and almost 20 million
summed MTE busy cycles; the vector plan removes the recorded spill traffic.
The two plans also change partition transfers and FIFO order, so this is not
an isolated intervention estimating “spill alone” causally.

In vector stage 100, relative to the previous root, core 0 completes six lanes
and five scalar reducers at 12,641; its scalar reaches core 1 at 13,143. The
other core-1 input is ready at 13,130. One local reducer, a return transfer to
core 0, and the root give:

`max(6 × 2096 + 5 × 13 + 502, 502 + 6 × 2096 + 4 × 13) + 13 + 502 + 13 = 13671`.

The root's critical branch is **0→1→0**. The initial broadcast to core 1 exists
but is covered by the longer branch. It is a smaller version of the same
scalar-routing opportunity, not evidence that zero spill solves the whole
scheduling problem.

## Next construction to test, not a claimed improvement

Preserve guarded full-vector-chain closure, persistent L1 lane ownership and
the small raw frontier. Replace majority-work scalar inheritance with a
**critical-arrival-aware reduction forest**. First determine lane completion
estimates from the fixed local lane order, then favor running a parent on the
later-ready child's core when the other scalar can arrive in time. In k4 the
specific obstruction to remove is sending the critical partial sum from core
3 back to core 2 before its final delivery. Intermediate reducer IDs are not
the rule; subtree completion, successor location and fixed transfer latency
are the structural inputs.

A tree DP with state “subtree result available on core c” can generate such
placements in a relaxed model. For fixed child completion tables,

`D_u(c) = p_u + min_{a,b} max(D_left(a)+tau(a,c), D_right(b)+tau(b,c))`,

where `tau` is zero locally and the minimum transfer delay remotely. Independent
minima over a and b make this O(tree_nodes × k²), rather than enumerating k to
the number of reducers. Include the next-stage broadcast when choosing the
root location, so improving one join does not merely shift the same delay to
the next fork. A structurally identical stage can reuse its placement rule;
do not cache case-ID answers.

This DP is **not exact for official P2**: two subtrees may compete for the same
V or COPY FIFO, and one completion label omits resource/credit history. Use it
as candidate guidance, then produce a single globally topological list with
per-core resource order, maintaining whole-chain closure. Verify that the
candidate removes the measured reciprocal scalar path and reduces its
fixed-plan bound before a separately authorized bounded E0 comparison.
The fixed-plan bound is a rejection certificate, not an evaluator replacement.
If preserving lane ownership still cannot improve k5, consider limited chain
splitting as a separate construction with an explicit memory/transfer budget;
the whole-lane lower bound is not the global five-core optimum.

No new plan has been generated or scored in this diagnosis. Exact memory
WAR/WAW causes cannot be recovered from these exports because the complete
added predecessor graph is absent. The report therefore does not attribute
unexplained gaps to a guessed memory edge or promise zero spill after a change.

## Reproduce and inspect

Run the stdlib analyzer from the repository root:

```sh
python3 results/a/q2-nikolastarx/vector-trace-diagnosis-20260925/analyze.py
```

It only reads the frozen graph, six plans, six official result exports and six
traces, then writes into its own diagnostic directory. `manifest.json` contains
their SHA-256 values plus official/source hashes; `summary.json` contains
period histograms, lower-bound decomposition, representative path nodes,
stage-100 transfers and queue waits. `stages.csv`, `stage100_ops.csv` and
`pipe_work.csv` provide the detailed numeric evidence. No score or pilot
artifact is overwritten.
