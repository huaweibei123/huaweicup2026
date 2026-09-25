# Three-cell hyperrefine and fixed-core retime pilot

Fixed coordinates: 003/k5, 043/k5, 056/k5, in that order. Every cell runs the
same cold candidate pipeline: `gap_candidate.build` once, check exact equality
with its saved old production plan, `gap_hyperrefine.refine(region_width=16)`
once, then `gap_retime.retime` once only if exact pre-Step2 original COPY bytes
strictly decrease. Old plans and E0 results are identity/comparison evidence;
they do not generate the candidate. The selected complete plan gets one public
native E2 request. An independent official E0 runs only if native Makespan is
strictly lower than the old same-cell E0. A native fallback, unknown outcome,
failure, timeout, resource breach, identity mismatch or E0 mismatch stops the
remaining batch without retry.

Limits: one worker; at most 3 E2 API calls, 3 independent E0 calls, no E1;
at most 60 seconds for each cold candidate plus E2, 60 seconds for each E0,
360 seconds total, 4 GiB observed process-tree RSS, zero retries. The pilot is
three cells of a new method. Its timing includes graph read, all candidate
construction stages, native E2 and plan write, but excludes comparison with
the old `adaptive_budget` route. It is not a full production solver or a
100×1–5 score. Static Pipe work/lag is not an official Makespan bound.

Inputs are passed at run time; the script contains no machine-specific paths:

```sh
"/path/to/verified-venv/bin/python" results/a/q2-nikolastarx/hyperretime-pilot-20260925/pilot.py \
  --runner-commit "$(git rev-parse HEAD)" \
  --python /path/to/verified-venv/bin/python \
  --raw-root /path/to/official/data \
  --old-run /path/to/old-gap-full500-run \
  --e2-root /path/to/isolated-603b-export \
  --output results/a/q2-nikolastarx/hyperretime-pilot-20260925/run-v3
```

The runner checks the fixed script and constructor bytes against its full
commit, official code/data/config against `docs/a/source-manifest.json`, E2
source and native binary against `check_e2_source`, and old per-cell plan/E0
identity. Artifacts include gzip-compressed plans and native/E0 originals;
compression roundtrip and raw/compressed hashes are recorded. The original
uncompressed E0 files remain alongside their archives for direct inspection.

## Frozen run outcome

The single attempted batch stopped at 003/k5. The cold seed matched the saved
old plan, and an independent pre-Step2 original COPY counter found 11,129,744
bytes for the seed and 6,921,880 bytes for both the refined and retimed plans.
All three plan archives decompress and the selected archive equals `plan.json`.
The public native E2 subprocess exited 1, before any native result was returned.
Its stderr was not preserved by the wrapper; the E2 ledger therefore remains
`request_in_flight=true` / `uncertain_exception` with one possible E0 fallback
reserved. The batch itself made zero separate E0 calls and no E1 calls. The
remaining 043/k5 and 056/k5 cells were not run. This is a toolchain failure,
not evidence of candidate Makespan or algorithm quality; there was no retry.

A read-only check with the same Python 3.14 executable found that `import numpy`
raises `ModuleNotFoundError`, while the E2 package imports numpy during module
loading. This supports an import-stage cause but does not recover the lost E2
stderr or resolve the uncertain ledger. See `run/batch.json`,
`run/003-k5/e2-ledger.json`, `run/003-k5/failure-receipt.json`, and the process
stdout/stderr receipts for the exact evidence.

The attempted `run-v2` stopped in its import-only preflight, before creating
the output directory or constructing/scoring any candidate: its script followed
the venv `bin/python` symlink to an unconfigured base interpreter. The failure
is retained in `run-v2-preflight-failure.json`. The corrected runner preserves
the requested venv entry path, checks E2/NumPy imports, and records nested
subprocess stdout/stderr on `CalledProcessError`; its separately authorized
batch uses `run-v3`. The first batch remains one attempted E2 request plus one
possible E0 fallback in the cumulative call account.

## Completed run-v3 pilot

The fixed three-cell batch completed in 23.449 seconds (one worker). Every
selected plan had one native E2 return and one independent official E0; no
native fallback or E1 ran. E2 and E0 agreed on Makespan and movement fields.
The gzip archives of plans, native receipts, official result, trace, and log
passed byte-for-byte roundtrip checks.

| Cell | Old E0 M | New E0 M | M reduction | Old added COPY B | New added COPY B | Cold candidate + E2 + plan s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 003/k5 | 205,295 | 163,449 | 20.383% | 9,845,480 | 5,637,616 | 6.433 |
| 043/k5 | 208,889 | 149,013 | 28.664% | 10,459,268 | 5,717,700 | 4.416 |
| 056/k5 | 96,280 | 69,685 | 27.623% | 4,863,236 | 2,446,782 | 3.813 |

`run-v3/batch.json` and each `candidate.json` contain exact hashes, timings,
construction diagnostics, E2 call ledgers, and official E0 originals. These
three selected inputs were a fixed mechanism pilot, not an all-cell result or
an algorithm chosen online against the old adaptive route. Across all attempts,
there were four E2 API requests: the first batch's one uncertain request plus
three run-v3 native returns. The first batch retains one possible E0 fallback;
run-v3 made three separate verified E0 calls. The run-v2 preflight made no
candidate or evaluator call.
