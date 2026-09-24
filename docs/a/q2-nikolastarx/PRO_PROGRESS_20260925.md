# P2 progress and Pro contribution, 2026-09-25

The user's acceptance rule is one frozen algorithm over all 100 graphs and
1–5 cores. The current algorithm has not met the requested targets. Historical
per-cell winners and later single-cell experiments do not replace this matrix.
Input-structural routing is legitimate only as part of the frozen solver;
selection, online scoring and fallback belong in its end-to-end cost.

## Current complete algorithm

- Solver: `b7c05cf2205bd42ec23680e618a10796b37562f6`, `adaptive_semantic`.
- Fixed result commit: `571536962b3f6ad9468584a0e5ae04398e684543`.
- Batch: `20260924T1729Z-s59ee`, 500 successful unchanged-official-E0 cells.
- Mean: arithmetic mean of each graph's official A single-core Makespan divided
  by this P2 candidate's Makespan, with all 100 graphs in each column.

| Cores | Current full-100 mean | User target | Status |
| --- | ---: | ---: | --- |
| 1 | 1.0817525414 | — | Reported, no target inferred |
| 2 | 1.9750479340 | 2.26 | Not met |
| 3 | 2.6986145873 | 3.18 | Not met |
| 4 | 3.3200478711 | 3.96 | Not met |
| 5 | 3.8250585361 | 4.53 | Not met |

The target numbers are the user's requested benchmarks; their external source
and denominator have not independently been certified. This does not relax the
target. Own measured means use the verified official-A denominator.

The current complete source improves substantially over the older contiguous
baseline (the user's board screenshot displays rounded five-core means 2.281
and 3.825). It is not evidence of theoretical optimality. Against Fang's fixed
`e64723bdf99669c44f76d8e90ab0379a8578522e` full-100 four-core result at
`b71d2efbcb45fe96770a22fc68d6a29d9b8fe78c`, the verified means are 3.3200478711
versus 3.3302284594: 37 wins, 48 losses, 15 ties for our solver. No conclusion
about full 500-cell dominance over that Fang version follows from this column.

## What the Pro interactions actually contributed

1. Earlier shared Pro synthesis supplied guarded resource reentry words and
   useful boundaries between ideal computation and official COPY/capacity.
   These influenced the P2 constructor, especially homogeneous independent
   chains. Earlier six-cell feedback also used Fang chain packets and local
   pipe-ready fallbacks; their gains must not all be attributed to Pro.
2. P2-specific r01, completed with a displayed 56m55s work time, supplied an
   independent M–V–M permutation reduction and a 3/2 ideal approximation,
   safe-drain conditions, and fixed-FIFO lower-bound/memory-order directions.
   We independently checked the relevant hypotheses. The independent-job
   guarantee does not apply directly to all-V fork/join 016 or the multi-visit
   reduction tree 062. Its strongest immediate contribution was diagnostic:
   distinguish poor compute order/assignment from incidental COPY waiting,
   and avoid treating zero spill as sufficient for good Makespan.
3. Subsequent local feedback—not separate Pro replies—improved 016/k2 by
   approximately 3.44% with arrival-aware scalar order, and 062/k2,k4,k5 by
   approximately 8.2% relative to the packets-first version with paired leaves.
   These are scoped experiments. No full-suite per-Pro-round ablation was run,
   so no causal full-100 percentage can honestly be assigned to each reply.
4. P2 r02 asks about controlled chain splitting and hiding transfers under
   actual COPY/memory semantics. The browser was checked this continuation:
   it still displayed Stop answering. Its unreceived answer has contributed
   no validated improvement. While waiting, our own d1 construction achieved
   016/k5 2,240,622 → 1,952,569 cycles (12.8559%), with extra DDR rising from
   281,636 to 39,994,024 B and zero spill. This new source is outside the b7
   full matrix. Result commit: `1235796fc408ecd0c50725ed24215b9145265a4e`.

Long thinking time is not evidence of correctness or measured contribution.
These interactions have been useful but uneven; broader structural weaknesses
still dominate the next development priority.

## What the full matrix changes next

The whole-component route misses internal parallelism in graph families with a
dominant connected component. For example, 056 places 97.21% of its operations
in one component. Other weak cases have shared inputs exceeding L1 capacity:
083/044/092 each use 930,400 B of shared L1 input against 524,288 B capacity.
Reducing the component batch to one does not fix that input set. Their large
spill differences from Fang identify useful work, while 044 also differs in
input replication/core use; it is not a pure ordering ablation.

Prioritize structural row/subgraph splitting and capacity-aware shared-input
ordering, then freeze a new unified algorithm and establish its complete
100×5 evidence. Do not splice the d1 single-cell win into b7 or certify success
from special-case progress. All figures here refer to simulator quality or
measured solver time, not verified hardware execution gains.

Evidence: `PRO_R01_REVIEW.md`, `FEEDBACK_SUMMARY.md`, the fixed raw benchmark
commit, `results/a/q2-nikolastarx/semantic500-review-20260925/`, and
`results/a/q2-nikolastarx/vector-split-pilot-20260925/run/SUMMARY.md`.
