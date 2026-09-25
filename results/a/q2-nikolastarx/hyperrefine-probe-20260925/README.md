# Archived 003/k2 hyperrefine probe

One process runs `gap_hyperrefine.refine` once on the saved static 003/k2 seed
placement, with `region_width=16`. The seed is reused from
`../pro-r04-review-20260925/static-003-k2/seed-plan.json.gz`; this experiment
does not include its construction time. Input graph and config are passed as a
directory argument. The script checks their known SHA-256 digests, the seed
compressed and decoded digests, structural validity, and the seed's independently
counted 6,351,422 pre-Step2 original COPY bytes before refinement.

Budget: one worker, one refinement, 30 seconds hard child wall limit, zero
retries, zero E0/E1/E2 calls. No official Makespan or capacity claim follows
from a byte decrease. Shared-machine timing is not an exclusive performance
measurement. The script records a complete compressed output plan and receipts
in a fresh output directory, even when there is no byte gain.

Example from the repository root (paths supplied by the caller):

```sh
python3 results/a/q2-nikolastarx/hyperrefine-probe-20260925/probe.py \
  --source-commit "$(git rev-parse HEAD)" \
  --raw-root /path/to/official/data \
  --seed results/a/q2-nikolastarx/pro-r04-review-20260925/static-003-k2/seed-plan.json.gz \
  --output results/a/q2-nikolastarx/hyperrefine-probe-20260925/run-003-k2
```

2026-09-24 UTC attempt: the first invocation used a short SHA and failed the
outer exact-HEAD preflight before creating a child. The subsequent invocation
created one child; it failed during import with `ModuleNotFoundError` for
`evaluation_validation` before calling `refine`. See `run-003-k2/process.json`
and `stderr.txt`. Actual refinement and evaluator calls were zero, and no plan
or byte result exists. The import order is corrected in the script after that
attempt. The frozen zero-retry budget was respected; no further child was run
under that batch. A separately authorized `run-003-k2-v2` uses the corrected
script with the same one-worker, one-refinement, 30-second, zero-retry budget.

The authorized `run-003-k2-v2` entered `refine` once and failed in its first
narrow region: `load_guarded_cut` received the global chain-work mapping rather
than work restricted to that region (`ValueError: work must have one record per
unit`). See its `process.json` and `stderr.txt`. This is an adapter defect
exposed by the 9,903-chain input, not an algorithm result. No output plan or
after-byte count was produced, and no evaluator was called. This batch was not
retried; a future probe requires an independently reviewed source fix and new
authorization.

## Completed experiment after the interface fix

Root fixed the regional work map in `2cfc86557e3184470ea730d77000624f795d64bd`
and added a twenty-chain, two-region regression test. The eleven regional-cut
and flow tests passed. The separately frozen v3 probe ran exactly once.

| 003 / 2 cores | Original COPY bytes | Added DDR bytes | Official Makespan |
|---|---:|---:|---:|
| Original gap seed | 6,351,422 | 5,067,158 | 248,166 |
| One regional cut pass, inherited order | 4,262,874 | 2,978,610 | 390,530 |
| Same cut placement, freshly retimed | 4,262,874 | 2,978,610 | 245,150 |

All three have zero spill. The original result and plan were read from the
ongoing frozen `923b` run; its decoded plan was checked equal to the archived
seed before either new official evaluation. New E0 calls total **two**, both
successful, no retries, E1/E2 zero. Result/plan/trace gzip files preserve their
decoded hashes in each `archive-manifest.json`; comparison receipts retain the
old result hash and frozen graph/config identities. These are one-cell mechanism
experiments, not a new complete algorithm score.

The byte-only pass took **0.623881 s**, processed 619 regions / 1,201 flow calls,
and accepted 508 regions. Its per-Pipe work peaks did not increase. Nevertheless,
the inherited singleton priorities induced a fixed-compute-FIFO lower bound of
261,573 cycles, already above the seed's official result. Balancing total work
does not preserve the amount of useful overlap.

`gap_retime.py`, frozen at `69b9d26ef972dfe1c8606a891ef8f89a6e896fec`, keeps
every operation on its assigned core and dispatches ready maximal chains by
remaining compute rank into per-Pipe calendar gaps. It uses the existing static
lag, then emits singleton priorities from the resulting starts. No additional
assignment, cut, parameter sweep, or evaluator is hidden in this stage. Twelve
retiming/candidate/regional tests passed. Retiming took **0.528711 s**, brought
the fixed-FIFO compute bound to 234,971, and had static finish 235,640. That
static finish is an optimistic model, not an official lower-bound certificate.

The retimed plan's E0 Makespan improves the seed by **3,016 cycles (1.215%)**;
added DDR falls **41.217%**. New external E0 times were 1.914106 s for the
inherited-order cut and 2.105202 s for the retimed plan. These clocks are separate
from construction, and both experiments reuse an archived seed. They do not
measure the complete production solver, which must also construct its fallback
and account for online selection. Host execution was shared with the original
one-worker full500 run.

Evidence: `run-003-k2-v3/`, `e0-003-k2-v3/`, `retime-003-k2-v1/`, and
`e0-retime-003-k2-v1/`. `score_one.py --retimed` reproduces the second official
comparison into a fresh output directory; it must not overwrite this run.

Next frozen probe: 003/043/056 at five cores, from cold gap construction through
one cut pass and one retiming. These selected diagnostic cases test the observed
communication-heavy mechanism. They are not used in algorithm dispatch rules,
and their results will not be spliced into the ongoing 500-cell batch.
