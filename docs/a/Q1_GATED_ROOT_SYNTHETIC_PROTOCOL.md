# Predeclared traffic-sensitivity probe for the root-aware candidate

Status: preparation only; execution awaits release of the existing P1 full500
window and a fixed runner receipt. This is a synthetic mechanism experiment,
not an official-case benchmark and not evidence of hidden-test performance.

## Decision and hypotheses

The immediate decision is whether the root-aware candidate merits a bounded
place in a later unified solver. Do not tune it to repair named official
cases. Freeze the existing standalone source before inspecting these results.
The solver candidate is `f777a11fa415d83e9f2b3d990befedbfa9a3b986`.

1. Root-aware active-core allocation may save Task waits on repeated fork/join
   graphs. Compare it with the existing generic fork frontier, grain 4.
2. Local subtree fusion may save boundary copies but delay Task completion or
   increase memory pressure. Compare fused and plain plans at identical
   allocation. A slowdown refutes a quality-dominance claim; it does not refute
   the DAG proof.
3. Since the allocation ignores tensor traffic, changing only tensor sizes
   may change the preferred constructor. No hypothesis assumes the same
   winner at every pressure level.

The generic frontier and plain candidate differ in more than one mechanism.
Their comparison measures the whole construction, not isolated causal
attribution to a particular gate term. The plain/fused comparison isolates
the optional fusion transformation on the same allocation.

## Fixed synthetic inputs and treatments

Each tuple is (chain width, chain depth, per-chain-operation cycles,
per-reduction-operation cycles). All compute uses PIPE_V. Each compute
operation produces one UB tensor. An original COPY_IN provides the common
input; the final root feeds an original COPY_OUT. Tensor sizes are uniform
within one graph; graph generation is deterministic with disjoint op/tensor
IDs. The official config stays unchanged: UB 131072 bytes, L1 524288 bytes,
DDR bandwidth 60 bytes/cycle, same/cross waits 100/1000 cycles.

| Family | Rounds | Binary tail shapes | Core budget |
| --- | --- | --- | --- |
| A | (8,4,200,7) repeated 3 times | balanced | 5 |
| B | (7,3,60,7) repeated 3 times | comb | 3 |
| C | (5,2,400,5), (9,3,80,9), (6,5,150,4) | balanced, comb, balanced | 4 |

For each family use tensor sizes 128, 4096 and 32768 bytes: nine distinct
graphs. Evaluate three constructors on every graph: `fork_frontier.construct`
with grain 4, `gated_root_frontier.construct` plain, and the same function with
`fuse_reductions=True`. No parameter sweep, retries, random seeds or online
scoring; each constructor emits one plan. Keep all outcomes, including ties,
losses and failures. Do not replace a graph after seeing its result.

This varies structure beyond the original fixed 12-chain, depth-4 example,
but the families were designed after reviewing the algorithm. Call this
structural sensitivity and falsification, not a blind holdout evaluation.

## Planned execution limits and evidence

Execution is not released by this document. The future independent window
must have a fixed runner/manifest and confirmed resource availability. Its
maximum scope is 27 fresh constructor calls and 27 unmodified official E0
calls, zero E1/E2 calls, zero official single-core baseline runs and zero retries. One worker;
30-second constructor and 30-second E0 windows including cleanup; 900-second
whole-window limit. First failure or unconfirmed cleanup stops the batch and
leaves remaining cells explicitly unrun. Do not increase limits automatically.

Record generator/source/config hashes, complete graph and plan bytes, raw E0
results, source closure, actual call counts, cold-process constructor wall
time, separate external E0 wall time and resource/cleanup receipts. An invalid
plan is a failed observation, not missing data to omit. Report Makespan and
scheduled/extra/spill DDR bytes per graph and variant. Synthetic ratios stay
outside the official 100-case and 500-cell averages.

After results, retain the unchanged baseline and decide whether to reject the
candidate, narrow its structural guard for a stated mechanism, or test it in
a new frozen unified portfolio. Any change gets a new source and experiment;
these nine graphs then become development data.
