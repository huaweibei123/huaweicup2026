# P3 internal separator proposal: place closed attention rows, retain original singleton operations

Status: one concrete structural proposal, not a benchmark. Scope is exactly raw official graphs 082/075/085. No E0/E1/E2 calls, no plan selection, no repository edits and no new dependencies. The root session will decide the next prototype and any evaluation budget. The scripts only use the existing `Index` plus original operation/tensor edges; operation numbers below are evidence addresses, never interval-based membership rules.

## Main result

A large shared-ancestor fraction does not imply that the large component must remain on one core. These graphs have repeated **multi-entry, single-exit attention query rows** behind shared K/V projections. A row contains real fan-outs and reconvergent reductions, unlike a chain. The shared producers stay explicit and execute once; independent row interiors can be assigned to different cores without cloning, fusing or reassociating any original operation.

| Graph | Identified panels × rows | Ops per row | Node coverage | Row M / all M | Row V / all V | Sum of M+V work coverage |
|---|---:|---:|---:|---:|---:|---:|
| 082 | 6 × 7 = 42 | 80 | 3,360 / 4,113 = 81.69% | 254,112 / 567,936 | 257,400 / 359,766 | **55.14%** |
| 075 | 20 × 5 = 100 | 56 | 5,600 / 7,410 = 75.57% | 393,920 / 1,107,520 | 411,120 / 644,660 | **45.95%** |
| 085 | 18 × 9 = 162 | 104 | 16,848 / 19,737 = 85.36% | 1,324,512 / 2,565,216 | 1,320,696 / 1,724,706 | **61.66%** |

Work is the sum of original positive compute cycles, separately by M/V pipeline, and is not Makespan. Particularly for 075, most M work lies **outside** these rows. A useful solver must also place Q/K/V projections and FFN/residual work; the table is not a promised speedup.

## Exact dependency-derived guard used for 082

1. Consider an original DIV with two compute predecessors, both ADD. Try both numerator/denominator roles.
2. Expand each predecessor's original binary ADD tree. Denominator leaves must be REDUCE operations, each with one distinct EXP predecessor. Numerator leaves must be MATMUL operations, each with exactly one of those EXP predecessors and one distinct external MATMUL projection V. The EXP sets must match exactly.
3. Each EXP must have one SUB predecessor. Those SUBs each combine a distinct score DIV with the **same** ADD root. Each score DIV has one compute predecessor, a score MATMUL with two MATMUL projection predecessors.
4. The intersection of all score-MATMUL predecessor sets must contain exactly one projection Q. The remaining distinct predecessors form K. K, V and Q are disjoint and provide `2m+1` projection boundary nodes.
5. Traverse backward from the common max-like ADD root, stopping at those score DIVs. The stop set must match every score, and internal operation kinds must be REDUCE/SUB/RELU/ADD. The row is the backward ancestor cone of the final DIV stopped at Q/K/V. Its exact operation set must equal the union of the above phases and contain `12m−4` nodes.
6. No non-final row operation may have a compute successor outside the row. Inspect **original tensor ports**, not just COPY-contracted adjacency: every tensor leaving the row must be produced by the final DIV, and there must be exactly one such output tensor. This catches external COPY consumers as well as direct compute consumers.
7. Boundary inputs must be exactly one tensor from each Q/K/V projection plus one 2-byte noncompute scalar. Q has no contracted compute successor outside the row. The script additionally records whether every original tensor consumer lies in the row; this passed for all42 private Q projections. Require that raw-port property before extending a placement capsule to include Q.
8. Reject overlapping row interiors. Group rows into panels by the exact shared K/V producer identities. Verify no direct dependencies between sibling rows and that every K/V compute consumer lies in the panel. Contract **all** accepted row interiors at once, retain every other original compute op as a singleton, and run an explicit quotient topological sort. This final quotient check passed; it is not assumed from a name such as “attention.”

The recognizer infers only graph structure. It does not prove the numerical operation implements softmax or reinterpret its reduction tree. The original graph and arithmetic order remain untouched. The 075/085 independent script applies a compatible frontier traversal and checks closure/shape/ports/quotient; its complete evidence is in `child-075085.json`.

## Concrete 082 first panel and boundary

First panel final DIVs are **214, 294, 374, 454, 534, 614, 694**. Q producers are 114/117/120/123/126/129/132. The shared K set is 115/118/121/124/127/130/133, and V is 116/119/122/125/128/131/134. These memberships were recovered by predecessor traversals. The six full rows each contain **M 6,736 + V 6,672 cycles**; the tail row contains **M 1,936 + V 2,868**, although all have 80 operations. Node-count balancing would be wrong.

For row ending at 214:

| Boundary | Original producers/tensors | Size / position |
|---|---|---|
| Private Q | op114 → tensor1000000150 | 2,048 B L1 |
| Shared K | op115 →1000000151, then 118/121/124/127/130, tail133 →1000000169 | 6 × 2,048 + 512 = 12,800 B L1 |
| Shared V | op116 →1000000152, then 119/122/125/128/131, tail134 →1000000170 | 12,800 B L1 |
| Scalar | tensor1000000021 | 2 B UB |
| Sole output | op214 → tensor1000000250 → op1276 | 2,048 B UB |

The row has **27,650 distinct input bytes**. K/V account for **25,600** shared bytes; Q is private to this row. Sibling rows reuse the same K/V identities, but their Q differs. This is a tensor-hyperedge effect, not the sum of independently charged graph edges.

Inside the row, the common max-like root **173** emits **64 B** to seven score-shift branches. The denominator root200 also emits64B; numerator root213 emits2,048B. Score/EXP intermediates are typically2,048B, with one512B tail branch. Keeping the row local protects these fanout/reduction paths from repeated cross-core release latency.

A minimal mechanism witness uses the actual path:

`136 →149 →156 →157 →158 →165 →166 →167 →171 →172 →173 →174`.

If score DIV136 and shift SUB174 are on core0 while this max-reduction interior is on core1, the dependency path crosses core0→core1→core0. Under the frozen scene-B/C **500-cycle cross-core COPY release** setting, these two boundaries introduce at least1,000 fixed release cycles on that path, before COPY service/queues. Mapping the whole row locally removes these two **internal** boundaries. This is a mechanism example, **not** a lower bound for every row assignment or a Makespan improvement claim; external Q/K/V transfers remain. Moving only a short reduction chain to an idle core can therefore be harmful even when compute loads look more balanced.

The two panels starting at sinks214 and795 share normalized-input frontier `{53,63,73,83,93,103,113}`. Analogous pairs use `{1450,1460,1470,1480,1490,1500,1510}` and `{2847,2857,2867,2877,2887,2897,2907}`. This identifies three two-head blocks by dependencies. Within one pair there are14 row opportunities, rather than one whole weak component.

## Proposed constructor interface and pseudocode

**The capsule is only a placement restriction. Do not turn a row into one submitted subgraph or Task.** A changed Task boundary can change official expansion, ordering, incarnation and reuse behavior. Retain original singleton `node_to_subgraph` identities and original per-operation predecessors. This avoids introducing a fused submitted subgraph; it does **not** preserve official derived Task boundaries, which can change with core ownership/order.

```text
capsules = recognize_rows(original_op_dag, original_tensor_ports)
assert disjoint(capsules) and acyclic(contract(capsules))
for row:
    record exact nodes, (M_work, V_work), frontier tensors, sole output
    record panel identity = (shared K producers, shared V producers)
remaining operations stay explicit (or existing separately guarded units)

place capsules using separate M/V load and tensor-sharing affinity
    all original operations in a row receive the same core
    optionally pull private Q into that row after raw-port closure validation
    K/V producers remain one copy of the original computation
    do not use op count as work or create a new reduction tree

schedule ORIGINAL operations with ORIGINAL ready events and fixed core placement
    choose a ready original op, append to its assigned core's singleton order
    maintain one global topological selection order
emit the ordinary singleton plan; run existing static plan validation
```

A practical communication proxy is each distinct boundary tensor times the number of remote destination cores. Keep this separate from the primary per-pipe workload. **It is not official DDR bytes or a promise of one COPY per core**: Task boundaries, DDR backing, incarnations, spill and read-only cache determine actual traffic and reuse. Panel co-location can increase reuse but reduce parallelism; neither one-core-all-rows nor maximal spreading is a universal rule.

Private Q membership is also optional, not a free win: Q114 consumes a4,096B normalized activation and a4,096B weight, then produces only2,048B. If the normalization remains remote from the row, moving Q into the row can replace a2,048B Q transfer with a4,096B normalization transfer and add weight demand. A first prototype can therefore pack only the strict80-op row and retain Q as an explicit operation with soft affinity.

Do not force an atomic row release at `max(all frontier arrivals)`. Q/K branches can start before later K or V projections arrive, and the row uses both M/V resources. Such an atomic release is an additional conservative ordering restriction and may erase useful overlap. A coarse value may rank placement candidates, but the generated order should preserve per-operation readiness. Projecting one global topological order to core orders keeps the compute+order graph acyclic; this is **not** a proof of full E0 memory/copy executability.

Two-head output joins provide soft locality affinity. For example, op1276 projects row214 and1277 projects row795, then1278 joins them. Prefer useful affinity when workload permits, but do not require the two full rows to become one indivisible unit: that needlessly reduces14 row opportunities to7 token units for this panel pair.

## Peripheral work and explicit limits

082's ungrouped work includes150 MATMULs of1,048 cycles and36 MATMULs of4,120 cycles. Example FFN diamond **1289 MATMUL →1290 SIGMOID →1291 MUL →1292 MATMUL** also has the direct1289→1291 edge; it carries8,192-byte internal activations and M8,240/V1,840 cycles. It is not safe to leave all such work on core0 and infer row-level parallelism solves the full graph. This report does not add a second solver or parameter grid; the root prototype should expose these remaining operations in its quotient/placement inputs.

No zero-spill, cache-hit, optimality, bandwidth-overlap, runtime speedup or official score guarantee is made. Shared K/V distinct input sizes are25,600B for082,17,408B for075 and33,792B for085. They fit individually within the frozen L1 capacity, but individual size is not a peak-liveness proof. Streaming row operations and original COPY consumers must still be respected. Freeze one082 prototype before an independently budgeted official check; do not turn this static census into a100-case sweep.

## Artifacts and provenance

- `inspect_attention_rows.py`: strict082 recognizer, accepts explicit repository/case/output arguments; no E0 call.
- `082-attention-rows.json`: all42 original operation sets, raw tensor boundary IDs/bytes/positions/consumers, work, panels, quotient edges, source/input hashes.
- `082-minimal-mechanism.json`: first two sibling rows and the actual two-crossing mechanism witness; not a submission or score.
- `child-075085.py`, `.json`, `.md`: independent bounded075/085 structural analysis.
- `MANIFEST.json`: byte sizes and SHA-256 of this proposal's files.

082 input SHA-256: `f230fbc200ad75797f3024f84431d1d26f7747d6a284378ee83eabde77b7e70c`.
082 final static recognizer run HEAD: `1a56523b31fd2ea4d33cff538c5b2323fb35af8a`. The initial read used `b1dd5d7e7420f48baa37d3dee6801a04aecb15b2`; the root session advanced its worktree during this read-only analysis. Input and Index source hashes remained unchanged.
Existing Index SHA-256: `942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73`.
075/085 input hashes and all original rows are in the child JSON. No downloaded code was executed.

Reproduce082 from any authorized checkout with an explicit path:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/q3-internal-separator-proposal/inspect_attention_rows.py \
  --repo "$PWD" --case 082 \
  --output /tmp/q3-internal-separator-proposal/082-attention-rows.json
```

No case identifier occurs in the recognizer's motif rules.
