# R3 initial local review: variable packet width

Owner: `nikolastarx/s-6607cb2735304751b36662035723372b`.
This is a qualified review, separate from the preserved Pro originals.

## Decision

The next useful freedom is capacity-derived variable packet width. Preserve the
fixed per-core chain lists, pending-return suffix and complete synchronous Task
boundaries. These give a small acyclic state graph; arbitrary asynchronous
release would require a substantially larger state containing unfinished DDR
service and per-core progress. Do not launch a wider parameter sweep.

The proposed `(n,r)` state is sufficient within this declared domain: fixed
lists and suffix semantics identify every original node; each edge completes
all old returns and leaves exactly a known suffix of new prefixes. At a common
complete boundary no Pipe or DDR request remains. No Task-local storage state
survives. Identical compiled signatures imply synchrony in the rational model,
not automatically in the official binary64/EPS implementation. Emitted plans
contain no artificial barrier and remain subject to official evaluation.

Advance edges strictly increase `n`. A drain goes only from `r>0` to `r=0` at
the same `n`, so one drain closure per layer suffices. The common prefix ends at
`B=floor(chain_count/cores)`. Both fixed terminal macros must simulate all
remaining per-core Tasks together, including their true release times, rather
than sum independent tail costs or insert a barrier. The initial artificial
gate is removed exactly once.

## What was checked locally

- Root read the complete native-copy R3 Markdown and the downloaded ZIP's README,
  state/member construction, ordered-family/prekey checks, transition enumeration,
  path recovery, final signature/model/traffic verification and certificate code.
  No author program was executed in this review.
- A reused Sol reviewer independently checked the frozen compiler and current
  response adapter. Within fixed source/config, single-producer, total managed
  footprint bounds and successful no-spill/no-MEM compilation, it found no
  omitted input to the stated ordered-key equivalence. This does not validate
  arbitrary graph isomorphism, interleaved chain ID blocks or the attachment's
  complete implementation. The stronger family condition must actually check
  all original chains, op orders, tensor orders and original boundary predicates.
- Root's separate `ROOT_CERTIFICATE_AUDIT_R3.py` reads JSON only. It verified
  exactly 203 capacity-feasible normal transition types, 7 drains, 43884 Bellman
  inequalities, continuous selected path, terminal choice, and all three path
  costs. It also checked 210 variable-width and 41 fixed-width potential
  inequalities using `Fraction`, including zero-progress drains.
- The saved edge table gives path cost `(390525, 22268010, 200)` before removing
  the initial 100-cycle gate, hence model Makespan 390425. Its finite fixed-width
  lower bound is 392842 and variable-width potential lower bound is 387703.
  These checks prove arithmetic consistency and finite optimality conditional on
  the supplied transition costs; they do not independently validate all costs
  against the official physical evaluator. No new solver, Task compilation or
  E0/E1/E2 call was made by the certificate audit.

## Corrections to the time-sensitive context

Pro read fixed `1517a896...`. Its introductory description of the old cache is
not a description of the later local `ordered-graph` cache. The later fixed-width
constructor already produced the same plan with 264 static compilations and an
observed 3.618-second construction on this Mac. Its timing cannot be compared
directly with the author's Linux 8.419-second variable-width construction.

The saved official upper bound for 084/k5 is now **397542**, confirmed by one
local E0, rather than the older 399121 available to the Pro request. Its extra
DDR is 8939520 bytes. The new author-model plan reports 390425 and 9031680 bytes:
7117 fewer modeled cycles but 92160 more bytes. Preserve this quality/traffic
tradeoff. Do not update the unified full500 mean (4.025907473836) from this one
candidate or reuse the author's wall time as local solver time.

## Next bounded verification

First validate the downloaded plan's bytes and input/config identities, then
allow one isolated official E0 of that saved plan (one worker, 30-second process
limit, zero retries, zero candidate construction/E1/E2). Record it as an author
plan evaluated locally, not a local constructor benchmark or unified result.
If the model claim survives, port the generic variable-width recurrence behind
the existing structural guard and bounded failure fallback, check a small
adversarial family (including ID interleaving and unequal tails), and only then
freeze a new unified version for a separately declared full batch.

The 335819 R2 lower bound remains conditional on its original private-chain,
FIFO-blocking and disjoint minimum-service proof. Neither that gap nor the new
finite-class certificate proves global P1 optimality. More same-class search
cannot improve an exactly solved class; further gains require changing a
specific structural freedom and validating the new assumptions.
