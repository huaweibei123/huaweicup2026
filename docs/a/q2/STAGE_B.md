# Q2/B stage B: preregistered finite comparison

Task `a-q2-core-search`; execution session
`yuanzhifang30-sudo/s-25ac3f7459f94fabb940724245a20ade`.
The local coordinator explicitly approved this stage after reviewing fixed
`9d51da742723f87bb6264c51d1d06f8445b29977` / Draft PR #40.
Development T0: 2026-09-24 04:29:06 Asia/Taipei; first checkpoint ETA 05:29–05:59.
Branch: `codex/q2-budget-search-yuanzhifang`; separate from the stage A PR.

## Fixed scope and reasons

Exactly case002, case008 and case044, four cores, seed0 (deterministic tie breaks),
one worker. These are public development cases, selected before this experiment:
002 exercises branching/chain placement, 008 has reported reentrant M/V and spill
sensitivity, 044 is a contrasting case where reported finish-first preferences
were harmful. Those descriptions are research leads, not our measurements.
No sealed tuning set, neural training, Pro execution, Q1 or evaluator modification.

Each case × method is a cold independent unit. Every unit regenerates D from
the same original graph/config, then calls the unmodified official Q2 on it.
No initial score, final score, trace, compiled profile or truth cache is reused
from another unit. D must succeed; otherwise stop comparisons for that case and
report to coordination. Final incumbents require a new official call and exact
full-result equality (same plan filename, so no excluded fields).

| Method | Preregistered family | Maximum explorations |
|---|---|---:|
| D | Existing min-ID Kahn topology, cumulative cycle weight contiguous 4-way assignment, one SG/nonempty core | 0 |
| M1 | chain / weak component / topo64 packets × ID / critical packet selection × 0 / 500-cycle cut-edge placement penalty × packet / singleton SG | 24 |
| M2 | fixed D core assignment; ID / critical tail / short tail / frontier delta / reverse-ID ready selection × 1/2/4/8/16/64-op core buckets | 30 |

M1 greedily balances per-Pipe compute loads, with an optional coarse penalty for
predecessor packets assigned elsewhere. It is not a DDR, backing or spill model.
Chain contraction uses only unbranched edges (outdegree/indegree both one);
component packets can be too large and cause severe imbalance. Topo64 may join
unrelated work. Each proposed quotient is checked; rejection is retained.

M2 considers up to 32 ready operations by original ID, selects according to the
declared key, and emits per-core buckets from that global topological traversal.
The frontier key is new touched tensor bytes minus last-touch bytes, using real
tensor IDs but a counterfactual no-spill lifetime. It is only a preference: no
capacity certificate, fixed 2×spill charge, unsafe hard pruning or optimality
claim. A compute topology does not prove compiled global FIFO/memory feasibility.

Mapping iteration order uses the original deterministic topology; core and op IDs
are retained. Deduplication compares the whole JSON structure serialized **without
sorting keys**, preserving mapping order. It removes only exactly identical plans
inside the current unit. No relabelling/core permutation or compute-word quotient.
Families stop when exhausted, even if calls/time remain; no after-the-fact expansion.

## Budget, process control and evidence

Each of 9 units: at most 32 official calls and 600 seconds; aggregate at most
288 / 5400 seconds. Slot 1 is the independently generated D, slots 2–31 are
exploration, slot 32 is reserved for final confirmation (it can be used early).
D will normally consume only two calls. Exact duplicates and construction
rejections consume proposal time but no official calls. All evaluator failures,
timeouts, retries and confirmation launches remain charged; no retry is automatic.

With R seconds left, stop exploration at R≤120. Ordinary generation/evaluation
timeout is min(120,R−120); final evaluation min(105,R−15); no nonpositive launch.
One exclusive stage ledger at `results/a/q2-yuanzhifang/stage-b-20260924-042906`
owns all units, independent of CLI invocation. Reserved units cannot be reset;
a stopped attempt requires explicit carry-forward accounting, not a new run ID.
Official reservations are fsynced before Popen; attempted/started/completed are
separate facts. The controller stops further units on a supervision failure.

The outer monotonic clock starts before unit directory/ledger/process creation.
The entire worker (hashing sources, graph parsing, baseline generation, all
proposals, official CLI output, deduplication, selection and evidence hashing)
runs in a Windows Job Object, including every generator/evaluator descendant.
The worker waits for a GO gate until job assignment succeeds. Closing/terminating
the job reaps the whole tree. Source: [Microsoft Job Objects documentation](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

Controller + all current job processes are sampled every 250 ms; threshold is
4 GiB aggregate working set. Exited-PID races are checked against job membership;
live-process sampling failure stops the unit. This can miss transient peaks,
double-count shared pages and overshoot between samples; not an OS memory cap.
Timeout is enforced externally even during parsing, construction and final hash
writing. Killing a unit may leave partial evidence, which must be labelled.

Evidence writing/hashing is inside the job budget. Controller cleanup is timed,
then controller.json is fsynced; stage.json records elapsed through that receipt,
and the captured controller output records elapsed through the stage-ledger write.
Both cleanup/receipt cost and actual overshoot are retained. These are explicit
measurement endpoints, not a claim that writing the last timestamp costs zero.
Only fixed-size control bookkeeping follows job completion; no graph-dependent
cleanup or hashing is deferred outside the measured unit. Human report/PR work is
separate delivery labor and not solver throughput. No provisional run is a final
quality or resource claim.

Every call preserves graph/config/plan identities, command, official result,
trace, log, stdout/stderr, timing and outcome. Each unit records code HEAD/source
hashes, Python/platform/lock and all candidate specifications. Unit output hashes
exclude controller files still being written; the final delivery manifest includes
them after completion. Entire method-quality comparisons use confirmed incumbents,
show all invalid/time/resource outcomes, and report actual unused budgets.

## Source reading and impact

At fixed `a6aec8d0fc2339d25e2d36aeeff7612ea21026d6`: read AI chats short index,
MATERIAL_SYNC_CHECK, AGENTS archive delta, Pro3/Pro4 directory READMEs;
selected Pro4 r03 report sections 1–5 and original Q&A lines 415–452 and 880–1005
(the question and relevant later audit/corrections). Pro3 COPY/FIFO probes were
already independently read and rerun in stage A. No claim of reading all 35 chats.
The remaining reports, full FORM catalog, Pro learning/source archives and
unneeded Q1 implementation details remain outside this stage's reading scope.

Impact: separate assignment from priority; keep all original labels and real
tensor identity; preserve COPY placement effects; do not equate no-spill profile
with physical peak or treat its failure as plan invalid. Captain reminder
[#33/5802420112](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5802420112)
reinforces rebuilding Q2's own tasks/backing via E0 after each partition change.
Directly read the entire fixed `95bca21e3bf211caf975652d82f7f4e331ec44cd`
`docs/a/research/20260924-pro-archive/PRO4_Q1_AUDIT_UPDATE.md` reception report.
Q1 synthetic results are not used as Q2 labels. No new semantic conflict found.

## Commands and acceptance boundary

Before any official call, ten zero-E0 tests check gated success and output-tail
timing, whole-tree timeout/reaping, sampled-memory stop, monitor failure, expired
no-launch, assignment-failure/crashed-worker cleanup, durable call/final-slot limits,
single-call timeout/launch bookkeeping, and remaining-time formulas:

```powershell
uv run python -X utf8 -B -m unittest discover -s tests/q2 -p test_budget_stage_b.py -v
# Only within the already approved stage; resuming does not reset any ledger:
uv run python -X utf8 -B -m src.q2.stage_b
```

The actual experiment uses the real same-version Python executable directly to
avoid the Windows venv redirector extra process. All solver/monitor code is stdlib.
Windows control tests do not claim Linux/macOS, real-graph hard resource stress,
independent scientific acceptance, all 100 graphs or the 2–5-core final matrix.
Atlas remains exclusively with the local coordinator.

## Controller correction checkpoint (after six units, before case044)

Fixed `9b544ad28b9515f9ab53070d457774b1d8f65a58` ran six units with
2/16/26 calls for case002 D/M1/M2 and 2/12/20 for case008: 78 total.
All six finished and were confirmed. Their original identities and evidence
remain unchanged; they are not relabelled as evaluated by the correction.

During execution the coordinator found that an unexpected worker error would not
stop later units, and a missing worker summary yielded an unknown call count.
At the next available boundary, a labelled case044 directory placeholder stopped
the old controller before any case044 reservation or process launch. Its
FileExistsError is a coordination stop, not a rejected candidate. The original
stage ledger/logs and a separate pause receipt are retained. A PAUSE marker now
provides an explicit boundary gate. Six completed units are never rerun.

The correction stops the stage for worker exceptions, failed supervision,
leftover processes or unknown errors even when a saved summary says confirmed.
Only a recognized initial-plan rejection is allowed to stop its case while
moving to a different case. Calls are recovered from durable calls.json even if
summary.json is absent; reservations remain charged. A present malformed ledger
fails closed. Missing ledger before the first reservation is separately labelled.

Known candidate construction rejections and recognized E0 invalid plans may
continue exploration. A proposal/E0 timeout or unknown error conservatively
ends the unit and stops subsequent units, retaining the prior incumbent but
without launching an extra confirmation. This is a stop, not a zero-score or
invalid-plan label. Fixed-size exhausted-time boundaries still reserve final
confirmation/cleanup as above.

Four additional zero-E0 controller checks cover missing-summary charge recovery
and no next launch, confirmed-summary masking of a process fault, a known D
rejection blocking its case only, and timeout/unknown-error halt policy. The ten
real dummy-process/ledger tests were rerun and passed. No new E0 was used for the
correction. Original stage start and 5400-second deadline are retained through
the coordination pause; case044 units remain unspent and individually capped.
The candidate families and score-selection rule are unchanged, so successful
paths remain comparable, while the two executed control-code identities must
be reported separately. Case044 resumes only after coordinator review.

## Delivery-time forced-stop finding (no additional E0)

A later developer rerun on `2422225` retained 4/4 controller passes but 9/10
process-suite passes: the injected memory-stop test encountered Windows
WinError32 while immediately deleting inherited stderr. The earlier passing
runs remain historical facts; this intermittent failure is preserved separately.
Active job PID count alone was an insufficient exit-wait boundary. The precise
cause of the observed file lock was not proven from that traceback alone.

The additional control fix retains SYNCHRONIZE handles for observed job processes,
waits for each to signal under one shared 10-second cleanup deadline, closes all
retained handles plus the Popen process/gate handles, and reports wait failures
as monitor_error. This follows Microsoft's asynchronous-termination contract:
[TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess).
A bounded 12-iteration dummy-tree forced-stop regression checks immediate log
cleanup, alongside injected wait failure and the existing control checks.
Outcomes and code identity are recorded under control-validation; no real graph
is reevaluated with this delivery-only fix, and success is not a proof that every
future file-lock condition is eliminated.

Private traceback paths are removed from shared logs using documented literal
prefix substitutions. Exact raw logs are retained outside every Git worktree;
redaction_manifest.json records raw/shared hashes and substitutions. Shared
sanitized logs are not described as byte-identical originals. Official unit ZIPs
remain original and are separately hash-verified.
