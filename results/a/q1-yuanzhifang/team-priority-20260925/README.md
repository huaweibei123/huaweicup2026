# P1 contribution to the final team solution

The user asked whether defeating the captain remains the right primary goal.
The recommendation is to use the current captain solver as the common quality
baseline and prioritize improvements to the final team submission. A separately
branded solver's slight lead is not by itself a reason for another full batch.
This is a research-priority assessment, not cancellation or completion of the
active optimization goal, and does not direct other P2/P3 sessions to change work.

## Evidence

`priorities.json` recomputes all five means from the fixed v4 500-row feed at
`9c5f87548cc7588465a638e032993969b5cac891`. All referenced single-core baseline
identities are matched to the independently audited 100-row k4/baseline index.
This is not a new audit of all 500 raw plans/results. No solver, Task compiler,
E0, E1 or E2 is run. Decimal arithmetic with 40-digit precision was independently
checked using a fresh feed read and `math.fsum`; all means agree within 1e-12.

| Cores | Captain v4 mean | Requested screenshot threshold | Margin |
| --- | ---: | ---: | ---: |
| 2 | 1.947513173 | 2.19150 | -0.243986827 |
| 3 | 2.739046557 | 2.83820 | -0.099153443 |
| 4 | 3.453039755 | 3.42710 | +0.025939755 |
| 5 | 4.025907474 | 3.90660 | +0.119307474 |

These are captain/team results, not the performance of the new unmeasured
Stage K entrypoint. The complete v4 feed has 100 successful records per core
count; the captain's latest Issue98 comment 5822228938 also reports 500/500
accepted and visible, 49 Makespan improvements over v1 and 32 extra-DDR
increases. That report is not a claim of dominance on every metric.

The measured 051 changes from H/J would contribute only +0.000943871,
+0.000955118 and +0.002305717 to the 3/4/5-core means if the other 99 results
were unchanged. This is conditional arithmetic on separately measured cells,
not a newly measured unified mean. It explains why repeatedly improving one
small structural family has limited portfolio value.

The screenshot's 2-core row is internally inconsistent under the usual sample
median. For 100 sorted observations with median m and maximum M, the lower 50
are at most m and the upper 50 at most M, so mean <= (m+M)/2. Its displayed
m=1.98950 and M=2.24600 imply mean <=2.11775, below the displayed 2.19150.
Rounding at the shown precision cannot explain the gap. The requested value
remains a numerical challenge; it is not verified evidence of another team's
official result. No judgment about the source's intent follows.

## Recommended order of work

1. Integrate the already measured H/J mechanisms with the captain's one
   maintained entrypoint, with paired changed-case acceptance and a generic
   width/depth/round-count guard. Preserve the unchanged official evaluator,
   current baseline candidates and explicit full-solver timing. Stage K's
   separate full100/k4 run has zero dispatches so far; its eventual purpose
   should be integration/regression evidence, not producing a personal rank.
2. Study structurally broad low-core gaps. The updated optimistic 2-core
   headroom ranking begins 044, 071, 065, 055, 015, 023; 3-core begins 044,
   071, 095, 069, 005, 064. These case IDs select diagnostic evidence only;
   the solver must route by graph structure. The bounds can be loose and
   these rankings do not promise that any listed gain is attainable.
   Shared-input batching and capacity-aware stage placement are a concrete
   untested direction; the prepared Stage L two-cell trial can falsify its
   present proxy before further implementation or a broad benchmark.
3. Build useful certificates: scope each lower bound to its proved assumptions,
   record each plan's gap, and rule out low-return families before evaluation.
   Do not demand a universal optimality theorem as the only research stop rule.
   A proved small gap or a fixed-family exclusion can justify redirecting
   effort while the overall objective stays active. No global optimum is
   currently proved.
4. Compare quality and total solver cost together, including cold start, online
   E1, failure paths, tail latency and owned memory. Reuse byte-identical E0
   artifacts, keep small mechanistic trials distinct from final full-suite
   validation, and keep the score board/figures/paper tied to the same release.
   Avoid duplicate P2/P3 research: share reusable memory/DDR insights and
   coordinate measurement windows. Their current sessions own their results.

The shared Windows machine's RAM gates have recently stopped K and P2 before
dispatch; this is a resource constraint, not a negative algorithm result or
evidence of optimality. Sol's static audit found no confirmed K-preflight leak.
The smaller L runner `aa66a805551a2f2225795f2ec5b2db444ba35b28` keeps source
`5c64b4057cb9b2f2af5426bd1efdd579b9df5559` and its two-cell budget unchanged,
with 512 MiB Job committed-memory caps and a 1 GiB available-RAM gate. It has
not been STARTed. Preparation and synthetic supervisor checks are not scores.

Reproduce the arithmetic with:

```sh
python -m src.q1_yuanzhifang.audit_team_priority --output NEW_PRIORITIES_JSON
```

The fixed source/data hashes and all 500 bound comparisons are in the JSON.
No lower bound exceeds the corresponding current v4 Makespan in this check;
that absence of a counterexample is not a general proof of a bound.

## Resumed-work update, 2026-09-25

The preceding unstarted-L statements describe the original assessment time.
Stage L later completed as a negative two-cell trial, archived separately; its
execution after the UI goal pause was a controller error already disclosed in
GOAL.md. The user subsequently resumed the goal, and the parent directly
verified authoritative active status before this new read-only research.

The captain accepted the P1/P2/P3 joint priority recommendation in Issue26
comment 5823085955. Formal paper sections remain captain-owned; this P1 session
owns its member draft, diagnostics and proposed mechanisms. The current team
protocol at `2da54f2bc` makes total coordination responsible for resource
priorities, and the board owner reacts to new official data or concrete faults.
Repeated board status queries and duplicate personal full batches are not the
next useful deliverables.

| Workstream | Current evidence | Next useful action |
| --- | --- | --- |
| Final unified P1 release | v4 has full500; H/J subsequently integrated into a research entry | Validate that fixed entry's coverage and failures before replacing the v4 main means |
| Low-core quality | v4 still below the 2/3-core numerical targets | Investigate a mechanism with measurable aggregate potential, not only another 051 variant |
| Shared-input windows | Zero-score audit finds two conservative-capacity merge pairs in 044 | Freeze a general guarded constructor and one minimal paired check before any larger batch |
| Theory | Captain Pro R4 has qualified fixed-MEM FIFO/credit and restricted return-cut arguments | Use proved assumptions and explicit unresolved gaps; do not duplicate that consultation |
| Program efficiency | New research full500 attempt: 68 ok, 1 external E0 timeout, 431 not run | Separate cold generation from external evaluation and preserve the timeout; use strict identity reuse where permitted |

The last row is the captain's fixed `ce8afb23032c1e26c2f9e427d4e1f838557ce9ac`
report, actually read in Issue98 comment 5825614861. The solver for 014/k4
completed in 76.2345 seconds; its external E0 hit the 900-second timeout. Its
plan was reported byte-identical to old v4, but the new failed evaluation is
retained and is not silently changed into a fresh success. This is not evidence
that the solver itself timed out, nor a new all100 mean.

The detailed next mechanism, restricted proof, identities and reproduction
command are in `../shared-window-audit-20260925/README.md`. This resumed round
has zero new solver, Task compilation, E0/E1/E2 or Pro calls. There is no global
optimality certificate; the full goal is neither declared achieved nor reduced
to the completion of this audit.
