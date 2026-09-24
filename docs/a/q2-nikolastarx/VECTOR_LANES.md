# Fixed vector lanes across fork/reduce stages

`src/q2_nikolastarx/vector_lanes.py` constructs one plan from a recognized graph
template. It performs no E0/E1/E2 calls and is not yet an officially evaluated
candidate. The source contains no case ID, known plan, score table, or fixed
lane/stage/chain counts. It does not change the existing adaptive router.

## Guard and construction

All eligible operations must use `PIPE_V`. Only op/tensor incidence edges are
accepted. Every tensor has at most one original producer; original COPY ops
must be explained external input/final output wrappers. Direct op/op edges,
internal COPY paths, extra vector consumers, extra intermediate inputs/outputs,
and uncovered eligible operations are rejected.

A lane is identified by its external positive-size **L1 tensor ID**. At each
stage exactly one head consumes that input, plus the previous stage's scalar
root if the stage is not first. The head and following single-consumer chain
keep that lane's input byte size in UB until a terminal operation produces a
strictly smaller positive UB scalar. Chain lengths, vector sizes, operation
names and durations may vary. All terminal scalars share one width inferred
from the graph. They enter a full single-consumer binary reduction tree with
the same scalar width. Its unique root is either the final output or broadcasts
only to all next-stage heads. Every lane appears once at every barrier.

The chain guard and scalar-tree activation check every used edge. In
particular, `lanes - 1` reduction nodes alone would not prove a tree: the guard
also requires distinct input tensors, one producer, one consumer on every
interior scalar, both inputs available within the current stage, and a unique
root. Together with original acyclicity, these exclude shared subtrees and
partial or mixed-stage joins. No stage inference uses arithmetic on op IDs.

The first stage's deterministic tree leaf order defines a contiguous lane
order. Each lane's total compute work is summed over all stages. A direct
integer feasibility search finds the smallest possible maximum lane work for
a contiguous partition into at most the requested cores; feasible cuts nearest
the remaining mean select one deterministic partition. This is an exact
solution of that **restricted load partition**, not a search over officially
scored schedules or a P2 optimality certificate. This lane-to-core assignment
stays fixed for all stages, and excess cores may be empty.

Within each stage, iterative tree postorder emits an entire vector chain as
one contiguous block, then emits a reduction once its children are available.
Reduction ownership goes to the core contributing the largest original lane
compute work to that subtree, with core ID breaking ties. This is a heuristic
to retain subtree data; it does not prove a minimum number of transfers.

Every operation is a singleton subgraph. One global postorder is projected to
each core. The implementation verifies exact eligible coverage, every original
contracted compute edge's forward position, and unchanged official
`derive_multicore_plan` structural validity before returning a plan with only
`node_to_subgraph` and `core_schedules`.

## What is proved, and what still needs E0

All parsed compute dependencies point forward in the global order. Every
additional compute FIFO edge on a core also points forward. Their union is
acyclic. Each large internal vector tensor has one producer/consumer on the
same core. Each external lane input's consumers occupy exactly one core across
all stages. The latter matches P2's tensor-by-consumer-core COPY construction
granularity and avoids duplicating that input merely because stages repeat.

There is no simultaneous compute benefit from opening multiple chains on the
same single `PIPE_V`. Closing each chain before the next therefore targets raw
vector residency. This does **not** prove an unchanged Makespan: DMA overlap,
COPY delays, Step2 spill, and Step3 memory-reuse dependencies can still affect
the real schedule. Original compute/FIFO acyclicity does not certify the final
expanded graph. The source explicitly reports `zero_spill_claim=false` and
`official_score_available=false`.

For an assigned core, let B be its largest lane input size, L its sum of lane
input bytes, n the number of lanes, and s the scalar byte width. Original
tensor inclusive-touch intervals in the submitted priority order satisfy:

- L1 peak <= L: these are the persistent input tensors assigned to that core.
- UB peak <= 2B + 2ns: only one vector chain is open, with at most adjacent
  vector input/output tensors touched simultaneously; all scalar outputs of
  the current stage plus its previous root number at most `(2n - 1) + 1`.

This deliberately reserves scalars more broadly than needed. The implementation
also computes the exact raw inclusive-touch peaks and asserts the bound. If
the envelope exceeds capacity, it reports that fact rather than issuing a
zero-spill promise. The formula excludes inserted COPY/incarnations and is
not an official runtime memory certificate.

Recognition and raw interval accounting are linear in original incidence
size, apart from deterministic sorting. The contiguous lane partition uses
O(n log W) feasibility work plus O(kn) cut selection, where W is total lane
compute and k is the used core count. Reduction support counters cost O(kN).
Official derive is retained with its existing cost; no claim of linear total
solver complexity hides that validation step.

## Static validation completed

Command: `.venv/bin/python -B -m unittest tests.q2_nikolastarx.test_vector_lanes -v`.
Nine synthetic tests passed: variable template dimensions/bytes, no COPY
wrappers, extra idle cores, deterministic record shuffling, unchanged inputs,
fixed ownership and contiguous complete chains, explicit compute/FIFO DAG
check, capacity-overflow honesty, partition correctness against small exhaustive
contiguous partitions, and malformed-template refusals. This exhaustive tiny
test is a test oracle, not the production solver method.

The only real graph constructions were 016 at k=2/4/5, each once, using the
actual CLI, with zero evaluator calls. Input SHA-256:
`76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef`.
The guard inferred 305 stages and 12 lanes, each four operations; all 3,660
chains stay whole, and all 12 external inputs each have one consumer core.
Plans and complete ledgers were archived without rerunning into
`results/a/q2-nikolastarx/vector-lanes-static-20260924/`, together with input,
config and source hashes, the test receipt and independent read-only review.
Original temporary directories remain under
`/tmp/p2-vector-lanes-s8ee-20260924/016-k{2,4,5}/`.

| Cores | Lanes per core | Maximum raw L1 | Maximum raw UB | UB envelope | Cross-core raw tensor COPY bytes, without spill |
|---|---|---:|---:|---:|---:|
| 2 | 6 / 6 | 196,608 | 65,542 | 65,584 | 4,876 |
| 4 | 3 / 3 / 3 / 3 | 98,304 | 65,540 | 65,584 | 12,188 |
| 5 | 2 / 2 / 3 / 2 / 3 | 98,304 | 65,540 | 65,584 | 12,184 |

These byte counts are static properties of the proposed mapping, **not official
extra-DDR/spill figures or new performance scores**. CLI internal times were
0.346/0.406/0.394 seconds on a shared Mac; they omit process startup and final
ledger serialization and are not comparative end-to-end benchmark results.

Exact plan SHA-256, respectively:

- k2: `009338de55db3bbe3c89696400573d4a7e44d6999a333bee43f080c753fcc53b`
- k4: `57563e380c32663f73afea7a0228e57d09431468b767b8b112c3eb0bd721d83f`
- k5: `a193acb4bee1e82a7e133e67272bbbe7566a6b3c6db6d7f6de7800af3365baa1`

The five-core result has unavoidable whole-lane load granularity for this
fixed-lane class: some cores take three chains and others two. That restriction
does not prove a lower bound for unrestricted P2, which may split chains or
change ownership between stages at a communication cost. The next meaningful
test is a separately frozen official evaluation against the already measured
016 candidates, retaining all three core counts and any regressions.

CLI follows the direct matrix contract:

```sh
.venv/bin/python -B -m src.q2_nikolastarx.vector_lanes \
  data/raw/a/official/data/case_016.json --cores 2 \
  --config data/raw/a/official/data/config.txt \
  --output <new-directory>/plan.json --evidence <new-directory>/online --wall 30
```

This report authorizes no additional evaluation and does not replace the
algorithm owner's review or the central benchmark dispatch protocol.
