# P1: split an in-tree at a weighted antichain

Owner: `nikolastarx/s-6607cb2735304751b36662035723372b`.

The first component-pack experiment exposed its expected limitation on case002:
1,798 compute operations form one weak component, so all work remains on one
core. Static inspection shows an in-tree: no compute node has more than one
successor, while 198 ADD operations merge branches. This motivates a tree
separator rather than more fixed-size random cuts.

`src/q1/tree_frontier.py` is a deterministic direct constructor. It uses
component-pack when K=1, there are already at least K weak components, or the
COPY-contracted graph is not an in-tree forest. Otherwise it accumulates
subtree compute work bottom-up and selects maximal subtrees whose work is at
most total work/K. Integer comparisons define the threshold exactly. The
selected subtrees are disjoint and cannot reach one another. It balances their
per-pipe work into at most K initial Tasks and places all residual operations
in a separate tail Task on the estimated slowest worker's core.

Every cross-Task edge points from an initial Task to the tail. Kernel order
adds only initial-to-tail edges. Thus the augmented Task graph is acyclic.
Each compute operation appears once. A single selected packet falls back to
component-pack, since it exposes no branch parallelism. These properties do
not guarantee good balance, low spill, or low DDR traffic; one large operation
or a skewed tree can leave an expensive residual tail. The tail core is a load
heuristic, not an exact completion prediction. At most K+1 Tasks are emitted.

Subtree mass computation and disjoint subtree traversal are O(V+E) after the
official helper graph is available; packing uses O(C log C+CKP). Original
component-pack validation and the official contraction/validation helpers are
included in actual solver timing, so no end-to-end linear bound is claimed.
There is no online evaluation, optimization search, or case-ID rule.

This follows the Pro guidance to exploit chains/trees while respecting P1's
whole-Task release gates. Fang's separate `chain-wave` is a useful comparison:
that method groups equal-depth chain packets into multiple waves; this method
keeps complete reduction subtrees and one residual tail. Neither is claimed
to dominate the other before E0 evidence.

## Frozen second development batch

Freeze before any new evaluation: **002, 008, 010, 051 at K=4**. Four constructor
starts and four external E0 calls maximum, sequential one worker; 30 s solver,
60 s E0 timeout, no retries/E1/E2. Stop on unexpected failure and preserve all
attempts and unrun cells. Source and runner commits must be frozen first.
The prior 8-cell batch remains sealed. This is a new algorithm identity and
run; existing official singlecore/fixed64 evidence is reused, not rerun.

All four cases are public development cases, not blind tests. Record the
selected mechanism, plan, tail/packet structure, cycles, extra/spill bytes,
solver startup-to-exit wall and separate E0 wall. Other P2/Q3 tasks may share
the host; no exclusive-machine speed claim. Three new graph-level tests check
a balanced reduction, a diamond with shared ancestry, and chain/one-core
fallback, alongside the four component-pack tests. No E0 is called by tests.

## Third, isolated frontier-granularity probe

The second batch's case002 frontier has seven packets and worker operation
counts 295/574/574/349. It improves E0 to 85,702 but leaves a large granularity
imbalance. A single mechanism probe is frozen before evaluation: case002 K=4,
`--packet-factor 4`, one constructor (30 s) plus one external E0 (60 s), no
retry/E1/E2. This makes the threshold total work/(K*4), capped below by the
largest operation's work so leaves remain selectable. It retains at most K+1
Tasks; only the number of independent packets and the residual tail grow.

The purpose is to compare finer balancing against additional boundary DDR and
tail work. It is one explicit structural ablation, not online parameter search
or a claim that higher factors always help. Default factor remains 1. Source,
runner and new batch must be independently frozen and all outcomes retained.
