# P2 feedback prototype — 2026-09-24

This iteration links the 13:54 UTC board snapshot to a from-graph solver. The prior
13 evaluations remain sealed. The new user request authorizes algorithm iteration,
sub-agent evaluation and shared board delivery; this is a separately bounded run.

## Source and hypothesis

- Board: 100×1–5 P2 cells existed, mainly Fang's contiguous baseline. Reported
  regressions do not by themselves identify DDR as the cause.
- Pro4 `AI chats/20260924-Pro4-算法方案设计/回答原文-f0ff3669-20260924T121808Z.md`
  recommends retaining a confirmed incumbent and treating specialized macros as
  proposals; D3 proposes guarded resource reentry. These are hypotheses/design
  sources, not new experimental facts or a wholesale adoption of Pro budgets.
- `baseline.py` preserves Fang's `src/q2/construct.py` at
  0b58c123cccf02fc993b741d79dcd8511e4dd38f. `packets.py` adapts that same commit's
  proposals.py with parameterized core count; only chain/critical/communication=1
  with singleton subgraphs is used, without its parameter search.
- `direct.py` adapts the team's Q3 Index/affine/resource-word implementation at
  a4e7ee13310d693ec4fb5cc236669ceb3b172d1f for P2 proposal generation. The new
  pipe-ready routine is a compute-only heuristic, not E2 or official timing.

Four fixed proposals: contiguous baseline; chain packets with critical priority;
component affine-eighth order; homogeneous M–V*–M resource word, falling back to
pipe-ready order when its compute guard fails. No filename chooses a strategy.
The latter two keep identical assignment, IDs and map insertion order. Their
comparison can isolate ordering but not the precise hidden execution cause.
Chain versus contiguous changes ownership/granularity and is not that ablation.

Each proposal is checked by the untouched P2 E0 CLI. Only a strictly lower official
Makespan replaces a successful incumbent; ties keep the earlier plan. Failures,
timeouts and unknown results never promote. Exact serialized plan duplicates are
skipped with provenance. If none succeed, no final plan is published. This ensures
nonregression versus the baseline **when that baseline succeeded in the same run**;
it promises neither global optimality nor preservation of the board's historical
best, and it does not establish monotonicity across core counts.

The compute guard requires independent components, each an actual serial chain
with equal homogeneous operation durations, first/last M and intermediate V,
a=end-M duration, b=total V duration <=2a. Lookahead=1+ceil(b/a). Tensor support,
capacity, shared input, COPY/FIFO and DDR remain official-E0 responsibilities.
It is not a zero-spill or performance certificate.

The new ready rule uses per-pipe release heaps; after dispatch it updates successors
and that pipe availability, giving O((V+E)logV) for a fixed number of pipes. Component
and word preprocessing are linear/topological plus sorting. The retained Fang
chain implementation can be quadratic (ready-list selection and dependency
contraction); do not label the whole solver O(VlogV). Online E0 may dominate.

## Frozen first experiment

Six development graphs: 002/008/044 are disclosed historical examples; 064/051/016
come from the board maintainer's observed regressions. They are not a holdout set.
All use P2 and four simulated cores; fixed official config/code and original bytes.
Each graph: at most four internal E0 attempts + one independent final E0; at most
30 actual E0 calls for this batch, no retries, E1/E2=0. One worker, each E0 <=60s,
solver <=240s plus outer cleanup, whole batch <=1200s. Stop dispatch on deadline
or observed process-group memory >4GiB; missing/timeout counts remain in ledger.
Environment preparation/extraction and static development scans are offline costs.

Save all proposals/results/traces/logs, selected final plan, independent final
result, outer subprocess-to-exit solver wall (includes online E0), final E0 wall,
UTC and resource observations, immutable code/input hashes and board feed. Reuse
existing official singlecore results as denominators without re-evaluation.
Sub-agent evaluates after the solver/runner commits are fixed. The root reviews
results and publishes via the existing board recipient, not its production DB.

## Pre-evaluation observations

002/064/051/016 each have one compute component; component-only partitioning would
serialize them on one core. 044 has 11 components of 124 operations. 008 has 108
components of 8 operations and passes the compute reentry guard (a=1158,b=2196,
lookahead=3). See structure.json; this static fact is not a performance prediction.

Acceptance: publish the complete six-cell outcome (including failures), compare
against each independently run contiguous seed and the fixed board snapshot, report
all cases and wall costs, then revise the research direction. A poorer candidate
is useful feedback; it must remain visible. Further batches require their own
explicitly bounded protocol rather than spending this batch's leftover calls.
