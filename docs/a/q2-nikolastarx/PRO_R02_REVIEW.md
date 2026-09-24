# Pro r02: conditions verified, useful new tree freedom, no extra scoring

Read the complete final message `06e2c875-8a5b-41fa-90ee-f6a8572734dd` in the
existing huaweicup / 6 Pro conversation. Its raw reply is archived under
`AI chats/20260924-P2-异构流水与最优性界/r02-response-06e2c875.md`.
It reports that case_016.json was missing (404) from fixed97e44f27, so the
author's local-model tests and code are not real-case E0 or Step2/3 verification.
No new solver or evaluator was run for this review.

## Supported conclusions and independent overlap

For n=qk+r, even L and 0<2r<k, the half-chain scheme has max chain work
(qL+L/2)p. It reaches the operation-count bound only when
ceil(rL/k)=L/2. The equivalent condition L(k−2r)<2k and counterexamples
(n,k,L)=(4,3,6),(5,4,4) agree with our earlier independent math review.
The minimum-cut argument is sound in the specified per-stage model: finishing
strictly before (q+1)Lp permits at most q uncut chains per core, hence at least
r split chains. This is not a global proof that every stage must be split or
that the resulting time/DDR point is Pareto optimal.

The total-service-plus-idle argument for at most one cross-core delay is valid
when all writes are eligible, DMA heads and credit do not add gates, and no
unaccounted traffic exists. In the synchronized rounded-service model the two
directions cost 2rd, giving delta+2rd <= (qL−L/2)p for hiding the communication.
It must not be extended to the real pipeline without the eligibility checks.
Our new vector_split guard rejects integer/official-float COPY rounding
disagreement rather than promoting an excessive lag as a lower bound.

The reply independently derives the same two-byte credit edge risk as our
source audit. Our already completed d1 E0 trace subsequently provides actual
timing evidence: all608 steady incoming large copies start503 cycles after
external release, exactly when the receiver's second whole chain's second
operation ends. The specific credit edge was not exported; it remains a
source-plus-timing inference. Actual period6387 exceeds the fixed-plan bound
6335 by52, comprising3 broadcast serialization and49 exposed receive cycles.
This does not validate the reply's whole ideal model, and our prior12.8559%
single-cell gain must not be retroactively credited to this later answer.

## New actionable contribution

Choose which 2r leaves finish late by minimizing the total weight of their
ancestor closure in the original reduction tree. A tree DP with a label for
the selected-leaf count is exact for that objective: at an internal node,
combine its children's counts/costs and add the node weight iff the count is
positive. Its complement is predecessor-closed, so early reductions can be
scheduled before the closure without changing the original tree.

This can improve the scalar tail while preserving the split count and fixed
external-input ownership. It is a more concrete new freedom than another
unbounded pair/window search. The DP optimizes that conditional tail objective,
not complete official makespan; actual releases and credit can still change
the result. No implementation or new E0 gain for this DP is claimed here.

The prepared-graph longest-path bounds require the actual augmented graph and
joint FIFO acyclicity, plus the frozen event loop's service and dispatch rules.
They are useful follow-up certificates, not a reason to rebuild the entire
evaluator now or declare near-optimality from our compute-only bound.

## Development priority

The remaining scalar-tail gain is limited to its small fraction of each
6387-cycle stage. The full500 audit exposes much larger component imbalance
and shared-input pressure, so the new adaptive_frontier work remains first.
Its first056/k5 official result is253392→165886, but adds7222022B DDR; the
one-cell result cannot replace b7's fixed full500 mean. Improving locality
inside the split component and checking shared-input waves are the next
measured steps. Save late-leaf DP as a bounded refinement for the vector family.

Original .py and ZIP download buttons were attempted; no local file bytes have
yet been obtained. Content export is unsupported by the in-app browser. The
reply text is complete; attachment availability is not claimed.
