# P1 sink-exclusive suffix waves

Status: **structural candidate**, not integrated into the selected solver. No E0,
E1, E2, official Task compilation, or performance run was made for this work.
The input graphs and frozen official code are read-only. Fixed base:
`05f8fa0f7e52f5914f14815f6bdbcb851b631556`.

## Construction and proof

Let G be the official COPY-contracted compute DAG. For the current induced DAG,
let S(v) be the set of sinks reachable from v, including v if it is a sink.
For each sink s, packet P_s consists of all v with S(v)={s}. Let H contain all
other vertices. If u→v, then S(v) is a nonempty subset of S(u). Therefore:

1. There is no edge between different packets P_s and P_t.
2. No edge goes from a packet into H; H is predecessor-closed.
3. Each P_s can contain forks, joins and long chains; it need not be a chain.

Peel all P_s, repeat on H, and reverse the resulting wave list. Whole packets
are assigned by per-wave pipe-load LPT, with one Task per occupied core in each
wave. Every inter-Task graph edge strictly advances the wave index. Core
schedules also strictly advance that index. Their union is therefore acyclic.
Coverage is exact because all sinks are peeled each round and vertices are
removed once. This proves **Task-order legality only**. It does not prove
Step2/Step3 feasibility, zero spill, any Makespan bound, or superiority to the
fallback. The public constructor additionally calls only the official structural
`derive_multicore_plan` / `validate_task_order` checks, never an evaluator.

The wave index is an ordering certificate, not an injected global barrier: the
submitted JSON has only `node_to_subgraph` and `core_schedules`. P1 still uses
actual predecessor Tasks and same-core order for release. Equal pipe work is a
proposal heuristic, not a duration prediction.

## Necessary official semantics

- `data/raw/a/official/code/stub_multicore_cut_and_schedule.py:20` constructs
  op adjacency from both direct edges and tensor producer×consumer edges;
  `:70` contracts paths through COPY nodes. The proof uses this exact DAG,
  not an operation-ID order or a DAG with COPY bridges silently deleted.
- `derive_multicore_plan` validates coverage and quotient dependency order;
  `evaluation_validation.py:validate_task_order` also adds each core's Task
  chain. Both must hold; quotient acyclicity alone is insufficient.
- `multicore_cut_evaluate_problem_1.py:70` constructs independent Task graphs,
  boundary DDR copies and Task-local scheduling. Same-core Task boundaries
  still lose intra-Task reuse. `:310–334` releases only after entire predecessor
  Tasks complete, with same-core / cross-core waits from fixed config (100 /
  1000 cycles). This is why P2/P3 per-op interleaving cannot be assumed here.
- Tasks still execute the official fixed FIFO/memory scheduling rules. Large
  packets may introduce head-of-line blocking, higher live memory or spill;
  shared input tensors may be reloaded across successive waves.
- Load weights here use max(1, cycles), including zero-cycle compute operations.

## Static findings, not scores

`results/a/q1-sink-peel-20260924/static_structure.json` records exact input and
code hashes and a read-only scan. It contains no generated plans or score.
The targeted 13 cases are those reported by the existing bounded04 full100/k4
comparison to fall back to a single Task; its measured scores are not rerun here.

| Cases | Structural outcome |
| --- | --- |
| 016 / 024 / 051 | One sink. All vertices are one packet; fallback. They contain 305 / 101 / 24 repetitions of 12 heavy branches plus an 11-op light reduction tree. |
| 048 | 20 waves; useful whole suffix packets have 50–63 ops. |
| 075 | 22 waves; useful suffix packets have 133–146 ops. |
| 082 | 8 waves; useful suffix packets have 181–194 ops. |
| 085 | 20 waves; useful suffix packets have 229–242 ops. |
| 069 / 071 | 4 waves; final independent packets have 157 / 133 ops. |
| 005 / 047 / 064 / 086 | 8 / 22 / 8 / 8 waves respectively. |

The new hypothesis is that preserving whole output-specific regions amortizes
Task gates and boundary copies better than fine chain waves. Parent-reported
Fang evidence (PR110 at b73c4bfcb8a0629550fdbdf3f8b4f3631e8cbc77) says case048's
fine chain construction had 692 Tasks / 250 layers and lost to its baseline.
This memo does not independently reproduce that score. Fewer waves alone do
not prove improvement: FIFO, DDR, load imbalance and remote releases can reverse
it. The first useful future experiment is one fixed candidate on 048 and 071,
then one larger repeated-stage graph; an authorized owner must run it separately.

051 is deliberately not claimed solved. Keeping the same worker Task across
multiple reduction/broadcast rounds can create a Task quotient cycle. Exposing
every branch separately instead repeats expensive input loads and gates. The
existing Fang / profile-refine plans are stronger measured starting points for
that family; this unmeasured candidate does not replace them.

## Complexity, decline conditions and validation

Let N,M be contracted DAG size, R≤max_rounds, and S≤max_sinks. Bit-mask operations
cost O(ceil(S/word_bits)); the decomposition takes O(R(N+M)ceil(S/word_bits)) after
initial sorting/topological preparation (O(N log N + sum deg log deg)); memory
O(N ceil(S/word_bits)+N+M). Packing all packets takes O(N log N+N K P), with at
most K·R Tasks (K≤5, P fixed). This bound excludes the inherited official COPY
contraction and repeated structural validations, whose cost must be reported
separately when measuring complete solver time. No linear end-to-end claim.

Defaults are 64 rounds / 64 sinks. If either budget is exceeded, the entire
candidate is discarded and the frozen-base bounded04 plan is returned.
Single-core, sufficiently many whole independent components, an existing
in-tree selection, or a decomposition with no multiple independent packets
also retains bounded04. No existing constructor is modified. A remaining
single-sink shared prefix may stay one large Task; this is safe but can erase
benefits. Shallow side sinks can produce short-work waves for which 100/1000
cycle gates dominate; no performance-based activation rule is claimed. No case-ID trigger or measured-score tuning is used.

Validation command:
`uv sync --locked && .venv/bin/python -B -m unittest tests.q1.test_sink_peel -v`
Six tests passed: existing in-tree baseline preservation, coarse diamond regions, repeated shared layers, COPY bridge,
complete fallback under budgets/single-sink, zero-cycle load, and exhaustive
all 1024 ordered five-vertex DAG structural witnesses. These are mathematical
and graph-level tests, not evaluator/solver benchmark calls.
