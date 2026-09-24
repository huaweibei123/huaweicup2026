# Integrate the verified construction mechanisms

`adaptive_semantic.py` integrates structural improvements into a solver that
accepts an arbitrary original graph, core count and frozen configuration. It
does not read case names, previous plans, scores or an online evaluator.
The previous `adaptive_direct.py` and its frozen 500-cell protocol stay intact.

## Deterministic routing and repair

Build one `DAGIndex`, shared by all following steps:

1. If the existing homogeneous resource-word guard holds, use that constructor.
2. Otherwise, if the tensor reduction-tree guard holds, use packets-first with
   same-core homogeneous paired-leaf weaving. Unmatched leaf chains retain the
   inherited tree order.
3. Otherwise, run the previous general rule: component envelope when the number
   of weak components is at least the number of cores, DAG EFT otherwise.
4. Recognize the guarded all-vector fork/chain/reduction template. Inspect the
   general plan's ownership along internal producer-tensor-consumer edges.
   If any tensor larger than the template's scalar crosses cores, replace the
   general plan once with whole-lane arrival-tree placement. If there is no
   such cut, retain the general plan exactly.

Step 4 is a diagnosed structural repair, not repeated search over scores or
different parameters. A triggered repair incurs both the base construction and
one repair construction; both belong to online solver time. The evidence
reports their counts. Construction errors propagate and do not cause an
unreported fallback or retry. The emitted plan still has only the two official
fields; routing and lower-bound diagnostics live in the sidecar evidence.

## Why inspect the cut instead of replacing every vector plan?

On the existing official 016 plans, the two-core general construction has 608
internal non-scalar cross-core edges totaling 19,922,944 tensor bytes before
COPY expansion. Its 4/5-core plans have no internal non-scalar cut. The former
had severe spill; the latter already beat indiscriminately replacing them with
the tested whole-lane constructions. This distinction is observable from the
input and current plan without consulting an official score or a case ID.

The repair eliminates internal vector transfers under the recognized template,
but it can increase scalar traffic or reduce overlap. Its official performance
is not guaranteed. Likewise, tree raw-priority peaks are not universal Step2/3
zero-spill certificates. This integration must receive its own structural
validation and either new official evaluation or explicit exact-plan reuse.
Reused scores cannot invent a new solver timing measurement.

## Current evidence and scope

Six synthetic tests pass with scoring/process entry points forbidden. They
check unchanged word/component plans, one-index tree construction, the repair
trigger, no repair for scalar-only cuts, propagated repair errors and the
single-attempt CLI contract. All-graph recognition in
`specialization-coverage-20260925/coverage.json` found tree candidates on
002/062/063, vector templates on 016/024/051, and resource words on 008/084/095.
That scan constructed zero plans and performed zero evaluations.

The separately tested leaf-chain and scalar-placement methods provide local
official gains; they do not prove this unified program's full-suite mean. The
next check compares its actual plans on the six newly affected graph families
against frozen prior plans and the original 500-cell static hashes. No new
performance budget or Windows admission follows from this document.
