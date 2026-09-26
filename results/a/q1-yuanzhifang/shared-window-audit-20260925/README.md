# Shared-input windows: a useful team-level next hypothesis

This is a read-only audit, not a new benchmark. The captain's v4 remains the
complete measured baseline. Improving the final maintained solver has priority
over producing another personally named full-suite result. This does not claim
completion or cancellation of the user's still-active optimization goal.

## Fixed evidence

- v4 source: `a0537aeb72dc702af86d67d3194587d581ac207c`.
- Archive: `9c5f87548cc7588465a638e032993969b5cac891`, cell `044/k4` in
  `results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/`.
- The original graph hash and the archived plan/result bytes are checked against
  the fixed `run-derived.json`. `verified-audit-final.json` records the hashes.
- `src/q1/shared_input_budget.py` at the same fixed archive was read. It compares
  metadata for 1..K active cores, chooses one configuration, then runs the
  bounded constructor once and splits each old Task by external-input windows.
- All original graph tensors incident to compute in this diagnostic are L1
  tensors. Original DDR backing tensors are not mistaken for additional L1.
  Every tensor has at most one producer, no excluded COPY bridges two compute
  nodes, and all reported inter-Task dependencies are forward on the same core.
  Every original Task also satisfies the full resident-union capacity condition,
  so the remaining Tasks' no-spill claim does not rely on preserving their IDs
  or compiler tie-breaks after the two merges.
- No new solver, Task compiler, E0, E1, E2 or Pro request was run. The audit
  recomputes boundary COPY metadata and reads existing official timelines.

The measured plan has schedules `[[0,2,3,4,5],[1,6,7,8,9],[],[]]`, Makespan
64,624 cycles, scheduled COPY 2,026,944 B, extra DDR 1,051,488 B and zero spill.
The 512 KiB L1 and 128 KiB UB capacities are fixed official configuration values.
Reported Step3 L1 peak is 264,192 B on each active core; UB peak is zero. This
compiled peak is not asserted to equal the runtime peak under all schedules.

The baseline's 256 KiB external-input threshold is a heuristic, not a capacity
certificate. Keeping all tensors touched by a Task is a stronger, conservative
test that includes internal values and outputs. Two existing adjacent pairs
pass that stronger test:

| Core | Adjacent Tasks | Union L1 B | Union UB B | Shared external B | COPY removed B |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | 2 + 3 | 455,424 | 0 | 0 | 1,536 |
| 1 | 6 + 7 | 453,248 | 0 | 0 | 1,280 |

All other adjacent pairs exceed the L1 union bound. The two passing pairs are
disjoint. Contracting them in metadata reduces 10 Tasks to 8, scheduled COPY to
2,024,128 B and isolated COPY service from 34,030 to 33,964 cycles. It removes one
100-cycle same-core boundary on each active core. These savings cannot be added
to predict a Makespan reduction: pipe overlap and shared-DDR timing change.
No submission plan was emitted and no new Makespan was assigned.

The pairs have **no common external input**. Requiring such overlap would reject
them unnecessarily: each internal producer-to-consumer boundary can also lose
its COPY_OUT/COPY_IN pair. The independent Sol review's initial overlap filter
was corrected after this metadata check.

## Restricted proof and its limits

Assume a valid Scene A plan with single-producer tensors and no excluded COPY
bridge, with every inter-Task dependency forward along its own core schedule.
Let A and B be adjacent on one core. Contract them while preserving every other
Task and the relative order of the remaining Tasks.

1. **Task topology.** Any dependence path from A through another Task to B would
   lie on the same core and require that Task strictly between A and B. There is
   none. The contraction therefore preserves an acyclic Task/schedule graph.
   This claim would fail without the full local-dependency condition: an
   A→X→B path through a remote X becomes a cycle after contraction. Unrelated
   compute nodes inside the merged Task still follow the original compute DAG.
2. **Capacity and spill.** Let T be all distinct original tensors incident to
   compute nodes in A∪B, including inputs, outputs and dead outputs. After the
   official boundary builder's position conversion, require sum of their sizes
   separately within L1 and UB capacity. Each no-spill Step2 live set, including
   allocated outputs before releasing inputs, is a subset of T. Its occupancy
   cannot exceed the union bound; thus a first spill cannot occur. Newly built
   DDR backing nodes are unmanaged. No spill means no additional spill-created
   resident incarnations. This audit uses the narrower all-compute-tensors-L1
   case; a general implementation must account for DDR→UB explicitly.
3. **COPY bytes.** In the official boundary rule, a tensor is input to a Task if
   that Task consumes it without producing it. It is output when produced there
   and required outside, originally copied out, or dead. Apply the contraction
   separately to each tensor. An external tensor read in both Tasks loses one
   input copy. A tensor flowing A→B loses B's input copy; A's output also vanishes
   only if no remaining Task/original output needs it. A third-Task consumer
   keeps the required output. Dead/original outputs remain once. Consequently
   no tensor gains a boundary copy. When both merged and remaining Tasks satisfy
   the union condition, scheduled and extra COPY bytes cannot increase. The
   present audit verifies this for every remaining Task independently as well;
   a prior zero-spill result alone is not used to justify an unexamined compiler
   identity change.

This is a sufficient condition for these properties, **not a Makespan theorem**.
Changed Task identities can change generated COPY IDs, Step1 tie-breaking, FIFO
order, memory-reuse edges and shared-DDR overlap. The union is also conservative:
failing it does not prove an actual spill or impossibility. No compiled-peak
runtime bound, global optimum, or universal dominance is claimed.

## Candidate and smallest useful experiment

A general postprocessor can walk each core's existing Task order left to right,
merge an adjacent pair only when the complete local-dependency and resident-union
guards hold, keep the left Task ID, and otherwise advance. It has no case-ID
routing and no plan enumeration. Hash-set insertion gives expected time linear
in the inspected tensor incidences for a disjoint-pair pass. The baseline
construction, guard checks, official validation, optional online selection and
file output all belong in the end-to-end solver timing.

For this fixed graph the rule deterministically chooses the two pairs above.
A future implementation should freeze one candidate and make one paired E0
check against the existing unchanged baseline. Compare Makespan, scheduled and
extra DDR, spill, and complete generation time separately. A negative or failed
result is retained; it is not a reason to scan merge subsets or expand the batch.
This report **does not START or allocate that experiment**. The next controller
must recheck the active goal, fixed source/budget, shared host window and RAM.

Broader value comes from integration and evidence, not this graph alone. The
captain has already integrated the H/J mechanisms into a research entrypoint;
its subsequent full500 attempt is reported as 68 successes, one external E0
timeout and 431 not run. That partial version must not inherit v4's full mean.
The duplicate personal Stage K full100 batch remains unstarted. New theoretical
consultation should target an unresolved proposition; the already archived
captain Pro R4 was read and need not be requested again.

## Reproduction and scope of checks

```sh
python -B -m src.q1_yuanzhifang.audit_shared_windows --output NEW_AUDIT_JSON
```

The first script attempt stopped before writing output because it overstrictly
required even original, nonincident DDR backing tensors to be resident. That
guard was narrowed to tensors incident to compute. `audit.json` preserves the
initial successful metadata report; `verified-audit.json` adds explicit
single-producer, no-COPY-bridge and forward-local Task guards. The final
`verified-audit-final.json` also checks the union certificate for every original
Task. Their numerical and identity fields agree. This is an audit-script correction, not an evaluator
failure or a changed algorithm score. No actual evaluator was called.

Windows/Python is the local audit platform. No new dependencies, raw-file
changes, official-evaluator changes or paid GitHub services are involved.
