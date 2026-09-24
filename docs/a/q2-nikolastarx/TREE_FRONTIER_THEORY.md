# P2 single-component frontiers: reduction trees and scalar-separated lanes

Read-only theory/structure investigation at source commit
`6e5099a35300133419990bf1f44f621f98850c21`, 2026-09-24. This note changes no
algorithm, invokes no solver or E0/E1/E2, and creates no benchmark allocation.
It uses original graphs, the frozen builder/scheduler, and already archived
pilot evidence. The two proposed mechanisms have different structural guards.

The target is better official Makespan with fewer avoidable transfers and lower
solver cost. A smaller raw priority frontier is an explanatory intermediate
quantity; it is neither the target score nor a zero-spill guarantee.

## 1. Exact observed structures

### 062: an in-tree after folding private unary chains

Original input `data/raw/a/official/data/case_062.json`, SHA-256
`fa99943eab55b174047687337a4bcd81c3967e052e22eaabf3fb7740914df2b4`.

| Static quantity | Value |
| --- | ---: |
| Eligible operations / weak components | 19636 / 1 |
| Operation indegree 0 / 1 / 2 | 2181 / 15275 / 2180 |
| Operation outdegree 0 / 1 | 1 / 19635 |
| MATMUL / RELU / ADD counts | 8728 / 8728 / 2180 |
| MATMUL duration, Pipe | 300 cycles, M |
| RELU and ADD duration, Pipe | 36 cycles, V |
| Total eligible work | 3011088 cycles |
| Maximum eligible dependency-path vertex count | 28 |

Every eligible operation produces exactly one tensor; every internal tensor is
1536 bytes and has exactly one eligible consumer. Starting from each indegree-0
operation and following the unique successor until its first binary join yields
2180 chains of 8 operations and one chain of 16 operations. These chains plus
the 2180 ADD joins cover all 19636 operations exactly once.

Each no-eligible-producer input belongs to only one such chain; no such input
is consumed directly by a join. A 4608-byte L1 tensor is used by eight MATMULs
(`10793,10795,10797,10799,10801,10803,10805,10807`), but all eight uses are inside
the same 16-operation chain. It is **not** shared across independent leaf blocks.
The remaining 4608-byte weights each have four uses in one 8-operation chain.

Therefore the collapsed graph is a binary reduction tree whose private-input
leaf blocks each return one 1536-byte UB tensor. A leaf block's original-tensor
inclusive first-to-last-use profile is L1 7680 bytes, UB 1536 bytes: it retains
its 4608-byte weight, initially consumes a 1536-byte L1 input, and allocates a
1536-byte L1 result. Alternating L1/UB outputs never require two simultaneous
1536-byte UB values inside one leaf chain. An ADD's allocation moment requires
two UB inputs and its new UB output: **3 × 1536**, not 2 × 1536.

This folding matters. Applying a one-output recurrence to each unary operation
while forgetting its still-live weight would undercount L1 occupancy.

### 016: a sequence of fork-join regions, not an in-tree

Original input `data/raw/a/official/data/case_016.json`, SHA-256
`76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef`.

- All 17995 eligible operations use **PIPE_V**. There is one weak component.
- There are 305 successive stages with identical normalized internal adjacency.
- Each stage consists of 12 independent 4-operation chains (each operation
  524 cycles), followed by 11 binary 13-cycle ADDs reducing their scalar results.
- Each chain has three 32768-byte UB intermediate tensors and returns 2 bytes.
- The 2-byte stage result feeds all 12 chains of the next stage; 304 such nodes
  have eligible outdegree 12.
- Twelve distinct 32768-byte L1 inputs each have 305 consumers, one per stage.
- Total eligible work is 7714975 cycles.

For example the first-stage chains include `13→14→15→16`, `17→18→19→20`.
ADD `61` joins outputs of `16,20`; the final ADD `71` supplies a 2-byte scalar to
`72,76,80,...,116` in the next stage.

Subtrees of this graph share ancestors and long-lived inputs. A tree algorithm
must not duplicate the previous stage's computation, count its scalar once per
chain as separate logical storage, or free it after its first consumer. The
useful decomposition is **stage regions separated by a shared 2-byte value**.

## 2. What weighted Sethi–Ullman ordering actually proves

Consider a single memory pool and a parent whose child subtrees are evaluated
one at a time, each subtree completely before the next. Assume:

1. The child subtrees have disjoint operations and private internal tensors;
   each result has one parent consumer. No recomputation or aliasing is allowed.
2. Child i has an already computed peak P_i and leaves R_i bytes resident.
   Its summary includes its own input/output allocation overlap and private
   external inputs. Other persistent boundary storage is explicitly reserved.
3. Parent execution starts after all children; its own input/output allocation
   requirement A is order independent. Output allocation happens **before**
   consumed inputs are released.
4. The statement concerns this sequential, noninterleaved priority evaluation
   model. It does not describe real parallel Pipe issue or inserted COPY nodes.

For order π, the subtree peak is

`P(π) = max(max_j (sum_{i<j} R_{π_i} + P_{π_j}), A)`.

An optimal order **within this family** sorts children by decreasing `P_i-R_i`.
For adjacent i,j satisfying `P_i-R_i >= P_j-R_j`, the two-child contribution is

`max(P_i, R_i+P_j) <= max(P_j, R_j+P_i)`.

Both terms on the left are at most `R_j+P_i` on the right. A common prefix adds
the same resident bytes; the pair leaves the same `R_i+R_j` for the suffix.
Adjacent exchanges therefore prove the sort. Different parent subtrees can
use this recurrence bottom-up. This is a direct O(V log Δ) tree computation
after block summaries, not a grid search over schedules.

### Two counterexamples that limit the theorem

**Interleaving can beat weighted closed-subtree order.** Let each of A and B
consume a private 99-byte input, produce 1 byte, then expand that 1 byte into a
50-byte result. Their parent consumes both 50-byte results and produces 1 byte.
Each child has P=100, R=50. Either closed-subtree order peaks at 150 bytes.
Instead compute A to 1 byte, B to 1 byte, then expand A, expand B, and join:
the peak is 101 bytes. This is a private-input pure tree with no shared
subexpressions. Thus weighted P−R sorting alone is not a theorem about every
topological order of every weighted tree.

**Two pools need not agree.** For child profiles
`P_A=(10,1), R_A=(0,1)` and `P_B=(1,10), R_B=(1,0)`, A-before-B peaks at
`(10,11)` and B-before-A at `(11,10)`, excluding the same parent term. With
capacities `(10,11)` only the former is feasible; with `(11,10)` only the latter
is. A sum of bytes or one arbitrary scalar key does not establish vector
optimality. One can keep a Pareto set of child summaries for a small tree, or
choose a declared heuristic and independently calculate both pool frontiers.

Shared external inputs invalidate the private-child recurrence unless their
first/last uses are carried as state or they are conservatively reserved across
all affected child blocks. Counting the same shared input in every child's
private result and then summing it is also incorrect. In 062 the collapsed leaf
blocks avoid this issue; in 016 the long-lived inputs require explicit ownership.

## 3. Concrete 062 recurrence and balanced cutting

After the verified folding, all returned values are UB 1536 bytes, leaf peaks
are `(L1=7680, UB=1536)`, and joins need UB 4608. Sort two child blocks by their
UB P−R values. For children a,b in that order:

`P_UB(v) = max(P_UB(a), 1536 + P_UB(b), 4608)`;

`R_UB(v)=1536`, while its L1 peak is the maximum of the leaf-block L1 peaks.

The root recurrence gives **UB 19968 bytes and L1 7680 bytes** for a full
closed-tree priority order. This is a useful memory reference, **not** a proposal
to place the entire graph on one core, a runtime zero-spill proof, or a score.
It also does not claim the minimum over arbitrary interleaved priority orders.

### Cutting exactly k root subtrees is not a balance method

The root is ADD `23998`. Its children have very unequal size:

| Root child | Leaves | Eligible work |
| --- | ---: | ---: |
| 23990 | 133 | 183504 |
| 23997 | 2048 | 2827548 |

The larger child next splits into 1024-leaf children. Merely assigning these
two root subtrees to two cores throws away most parallel capacity. Cutting the
largest subtree until there are exactly k pieces similarly need not balance
non-power-of-two k.

A small deterministic candidate is:

1. Use the private unary leaf blocks and their reduction tree as indivisible
   leaves. Choose one declared target piece weight, e.g. `W/(2k)`, using integer
   rounding. This is a fixed construction granularity, not a tuned parameter grid.
2. Descend through an over-target subtree, keeping its root join in a residual
   join skeleton; stop at maximal subtrees no heavier than the target, or at an
   indivisible leaf block. Each operation belongs to exactly one piece or to the
   skeleton. A too-large leaf is reported; it is not silently split contrary to
   the guard.
3. Assign complete pieces in decreasing work to the currently least-loaded core,
   with deterministic ties. Within each piece emit its proven closed postorder.
4. Emit the residual joins in one common topological/postorder sequence, assigning
   a join to a child-result owner where possible; use remaining-work/load only as
   a declared tie or placement heuristic. Every cross-core cut is at a 1536-byte
   result, not in an M/RELU chain or across a 4608-byte private weight.
5. Preserve a common global topological order and project it onto the cores.
   Pieces can precede the skeleton in priority order; this is not a real execution
   barrier. Account for every piece-root value retained until its skeleton use.

For ordinary scalar list packing, if total piece work is W_p and maximum piece
weight is p_max, greedy least-load assignment satisfies
`max piece load <= W_p/k + (1-1/k) p_max`. This is a compute-load bound on pieces,
not on official Makespan; residual join work, dependencies and communication are
still present. It is stronger evidence than saying the heuristic is “balanced”.

One bounded static calculation with the `W/(2k)` rule (no plan emitted or scored)
gave the following before assigning residual joins:

| k | Complete pieces | Residual joins | Piece loads (cycles) |
| --- | ---: | ---: | --- |
| 2 | 5 | 4 | 1414392, 1596552 |
| 4 | 9 | 8 | 707832, 889992, 706488, 706488 |
| 5 | 17 | 16 | 536712, 531156, 706416, 706416, 529812 |

This exposes remaining imbalance instead of hiding it. An implementation may
choose another single structurally justified cut rule, but must freeze that rule
and verify its raw frontier before requesting a new official batch. There is no
theorem here that `W/(2k)` is the optimal quality/communication tradeoff.

Even a closed leaf order can lose M/V overlap compared with a small interleaving
cohort: each leaf alternates M and V, while different leaves can fill each
other's dependency gaps. First test the memory correction, then investigate a
capacity-certified small cohort if E0 shows a compute/Pipe utilization loss.
Do not restore an unbounded global pipe-ready frontier to gain that overlap.

## 4. Concrete 016 primitive: complete lanes with stable ownership

Assign each of the 12 long-lived L1 input tensors and its matching vector lane
to one core, consistently across all 305 stages. Within a core/stage finish
one 4-operation chain before starting the next. Then execute the small scalar
reduction in a common valid topological order, placing joins using child owners.
The next stage depends on the previous root. This keeps parallelism **across
cores**, while removing large-tensor transfers between operations of one lane.

All original computation is on V, so interleaving independent lanes on the
same core does not create extra **compute-Pipe** concurrency. It can still alter
overlap with COPYs, external waits, and memory operations; hence closing lanes
is not by itself a proof of optimal official timing.

For k=2 and k=4, each core receives exactly 6 and 3 lanes, respectively. For k=5,
the indivisible lane counts are 3/3/2/2/2; this imbalance must be reported, and a
claim of per-core optimal work balance would be false. A later refined candidate
could migrate a lane only at a scalar stage boundary, but that duplicates its
32768-byte L1 input across owning cores and trades compute balance for input
traffic. Do not change this tradeoff invisibly inside the first candidate.

With complete-lane execution, stable ownership, and no next-stage interleaving,
the original-tensor inclusive priority frontier has conservative bounds:

`UB <= 2×32768 + (23+1)×2 = 65584 bytes`;

`L1 <= ceil(12/k)×32768 bytes`.

Two consecutive large intermediates account for allocation before last-input
release; one whole stage's 12 leaf results and 11 join results plus the preceding
stage scalar conservatively cover the small values. This overcounts scalars
already freed, which is safe for this raw bound. At k2 and k4 the L1 bounds are
196608 and 98304 bytes, both below the fixed 524288-byte capacity. The UB bound
is below 131072 bytes. These inequalities concern original priority intervals,
not the final extended graph or actual simultaneous residency.

### Existing evidence explains why this candidate is targeted

The frozen DAG pilot had the following statically reconstructed communication;
the sums match its archived official partition-added COPY values:

| Quantity | 016-k2 | 016-k4 |
| --- | ---: | ---: |
| Split 4-operation chains / 3660 | 608 | 0 |
| 32768-byte cross-core tensor pairs | 608 | 0 |
| 2-byte cross-core tensor pairs | 2746 | 3816 |
| Two-ended cross-core COPY bytes | 39856872 | 15264 |
| Duplicate graph-input bytes | 262144 | 524288 |
| Total partition-added COPY bytes | 40119016 | 539552 |

The previous k2 priority order opens six large chains before closing them and
has raw UB 7×32768; k4 opens three and has raw UB 4×32768. Existing E0 reported
379715584 spill bytes at k2 and zero at k4. This is consistent with the diagnosed
capacity problem but is not a universal implication from raw frontier to spill.

Stable complete lanes eliminate the large cross-core chain edges and duplicate
long-lived input reads structurally. Scalar communication remains and must be
measured. The input graph, counts and existing-plan analysis were independently
read by the nested static-inspection agent; it ran no solver or evaluator.

### A stronger true P2 lower bound from stage separators

The 305-stage structure also provides an assignment-independent certificate,
different from the whole-lane constructor. A static region traversal was checked
at **every** stage: its 59 operations consist of 48 operations of duration 524
and 11 joins of duration 13; all entry operations depend on the preceding stage
root (except the first stage); all 59 operations precede this stage's root.
Every large operation has at least 39 cycles of successor computation before
the root finishes, and the final root itself has duration 13.

Let Δ_s be the interval from completion of the preceding root to completion of
the current root, taking zero as the start of stage 1. These intervals do not
overlap. All 48 large operations of a stage must execute on the k V slots inside
this interval, and every one completes at least 39 cycles before its end. Some
core owns at least `ceil(48/k)` such indivisible operations, even when chains are
allowed to split between cores. Thus

`Δ_s >= ceil(48/k) × 524 + 39`.

Separately, the final 13-cycle root can begin only after all other stage
operations have completed. Their total V work is `25295−13=25282`, so

`Δ_s >= 13 + ceil(25282/k)`.

This is not “critical path plus all workload”: each inequality identifies the
work that necessarily fits **before** a particular final interval. Integer
ceilings are valid because one core carries an integer amount of that work.
Cross-core transfers, waits and memory constraints cannot reduce these required
original compute intervals. The retained-dependency assumptions are the verified
single-producer ones in `OPTIMALITY_BOUNDS.md`; no original excluded-COPY edge is
being used as a timing dependency.

The resulting **global P2** bound is

`C >= 305 × max(ceil(48/k)×524+39, 13+ceil(25282/k))`.

For comparison only, if each four-operation lane must remain on one core,
some core instead owns at least `ceil(12/k)` complete lanes, imposing
`Δ_s >= ceil(12/k)×4×524+39`. This is a restriction on the constructor family;
it is not a restriction in the official submission format.

| k | Global stage lower bound | Global 305-stage lower bound | Whole-lane family lower bound, 305 stages |
| --- | ---: | ---: | ---: |
| 1 | 25295 | 7714975 | 7714975 |
| 2 | 12654 | 3859470 | 3859470 |
| 3 | 8441 | 2574505 | 2574505 |
| 4 | 6334 | 1931870 | 1931870 |
| 5 | 5279 | 1610095 | 1929735 |

No equality with a feasible E0 result is asserted. At k5, even solving the
whole-lane class perfectly leaves a potentially material restriction gap. Moving
whole lanes between cores **between stages** can change persistent input traffic
and average ownership, but every individual stage still has a 3/3/2/2/2 whole-lane
allocation and the 6327-cycle restricted lower bound. Rotation alone cannot
remove that per-stage bottleneck because the scalar root separates stages.

Getting below the restricted bound requires departing from complete-lane
ownership within at least one stage, or finding a flaw in its structural premise.
An internal large-tensor cut introduces a 32768-byte COPY pair; the nominal
isolated transfer time is `ceil(32768/60)=547` cycles on each end plus the fixed
500-cycle external release delay, or 1594 cycles along that communication path.
This figure describes the isolated-copy model, not an additional certified
floating-pool time bound or a net Makespan penalty: communication can overlap
other compute, and the source/target Pipe orders matter. The compute-side saving
from balancing a most-loaded three-lane core toward ten rather than twelve
large operations is at most 1048 cycles for that comparison. Comparing 1594 with
1048 does **not** prove every internal cut is inferior; it specifies the overlap
and critical-path question a later mathematical or bounded experimental study
would need to settle. No such additional candidate is run by this note.

## 5. Lowering either construction to the real P2 interface

The submitted object contains only `node_to_subgraph` and `core_schedules`.
Singleton subgraphs let the constructor express each core's chosen priority
order. They do **not** specify start times, barrier nodes, custom op scheduling,
tensor addresses, or bandwidth allocations.

Frozen P2 merges all subgraphs on a core into one Task. `_prioritize_task_seq`
stable-sorts the Step1 sequence by submitted subgraph rank. Boundary COPYs are
attached to first-consumer or last-producer buckets. Step2 may insert spill and
rename tensors. Step3 uses the expanded sequence's per-Pipe projections and
adds memory reuse dependencies; final P2 replay combines these with cross-core
COPY releases and global DDR sharing.

A common global topological original-op order, projected to cores, proves that
original dependencies plus those per-core original-op priority edges are acyclic.
The singleton mapping has exact coverage and unique ownership. In the verified
single-producer domain, the generated boundary-copy bucket order has the usual
producer-before-consumer direction, as discussed in `DAG_DIRECT.md`.

These facts do not prove that **all** inserted COPY FIFO and Step3 memory edges
produce a valid final execution, or that a raw capacity bound forces zero spill.
In particular a remote consumer waits on a source COPY_OUT, and a later same-Pipe
COPY cannot bypass an earlier blocked COPY. A priority phase is not an execution
barrier. Structural validation, the raw frontier calculation, successful E0,
and improved E0 scores are separate evidence levels.

## 6. Smallest falsifiable next candidates

- **062 candidate:** structural in-tree + private unary-block guard; weighted
  closed postorder; deterministic complete-subtree cut/assignment; residual
  join handling. Report piece loads, cut tensor pairs/bytes, per-core raw L1/UB
  peaks and all guard failures. Do not route by a case ID. Verify that no private
  leaf-chain input touches multiple cores and no leaf chain is cut.
- **016 candidate:** structural repeated all-V lane-region guard; complete
  four-operation lanes keyed by the stable external input; same owner across
  stages; local lane closure; scalar-only cut edges. Report exact lane counts,
  large-edge cut count (expected zero), duplicate long-lived input bytes
  (expected zero), raw pool peaks and scalar communication.

Each is one deterministic proposal with an independently frozen minimal official
test requested by the root session; this note authorizes no additional calls.
First compare the appropriate existing fixed plan on the same cell using saved
evidence. New E0 output must report Makespan, total/partition/spill bytes and full
solver wall time. A useful static improvement that worsens those metrics is a
failed candidate, not progress to relabel as a score improvement.

If these guarded constructions work, the unresolved theory is narrow: derive a
time-quality guarantee for concurrent closed subtrees/lane regions under the
actual two-ended shared-DDR COPY and FIFO constraints, or find a counterexample.
General weighted Sethi–Ullman and raw frontier bounds alone do not provide that
guarantee or an impossibility proof for the full P2 optimization problem.
