# Fixed Linux COPY-event pilot runner

This runner operates on a separately packaged, immutable capsule. It checks
`capsule-manifest.json` input hashes, the byte-identical fixed P2 manifest at
both `fixed-p2-manifest.json` and the solver's hardcoded path, all 50 E2 source
hashes, and `runtime-identity.json` against the Linux build receipt and native
binary. The launcher builds and verifies E2 before starting this runner;
compilation, environment setup, and packaging time are separate from measured
solver wall time. The capsule's Git HEAD is the local runtime identity; the
manifest's solver and runner source commits record upstream provenance.

The runner first compares native E2 for each frozen 005/009/015 K5 seed against
its saved official E0 result, including Makespan and all five movement fields.
It stops if any comparison fails. It then runs the complete cold solver once
per graph, using the fixed Linux receipt and at most four online E2 requests,
and independently evaluates each selected plan with official E0. The selected
plan must have a native E2 score in its solver ledger, and that score must
equal the final official result. Unknown, timeout, fallback, partial ledger,
or any failed step stops the batch without retry.

Run under the launcher's locked Python 3.12 environment, with output **outside**
the capsule root:

```sh
python -B results/a/q2-nikolastarx/copyevent-linux-pilot-20260925/runner.py --output /path/to/new-output
```

Limits: one worker; three seed E2 plus at most twelve solver E2, three final
E0, zero retries; 90 seconds per solver, 60 seconds per final E0, 600 seconds
for the batch, and 4 GiB sampled process-tree RSS. `batch.json` records
reservations, attempted calls, process receipts, uncertainty, and verification
state. A failed process may have made an unknown number of internal E2 calls;
the runner stops and never interprets missing evidence as zero.

This three-cell pilot is a mechanism check, not a full 500-cell result. It
must not be dispatched from this source tree; the production owner controls
the capsule and run.

## Actual pilot, 2026-09-25

Frozen solver `295ec9cf4351b77f5c6fffe8fbb23e8bc8d2f323`, Linux x86_64,
Python 3.12.3 under `uv sync --locked`. All three saved-plan native/E0 pairs
and all three selected-plan native/independent-E0 pairs match exactly on
Makespan, cross-task traffic and all five movement fields. Actual 15 native
E2 calls, 3 independent E0, zero fallback. Batch 56.933s; setup 16.499s is
separate. Solver walls 15.152s / 20.511s / 7.360s are remote end-to-end values,
not a controlled speed comparison with the Mac.

| Case / K5 | c665 M | New M | Selected |
|---|---:|---:|---|
| 005 | 33515 | 32849 | COPY-event |
| 009 | 51905 | 44648 | COPY-event |
| 015 | 40828 | 40828 | Original selected seed |

`report.json` records local downloaded-byte verification. The two ZIPs retain
original input/code/results, the Linux binary and the build receipt. This is
not a new full500 score, nor proof of all-case Linux equivalence. A separate
capacity-safe 015 probe (one extra E0) is archived in
`../capacity-safe-diagnostic-20260925/` and is not part of this frozen solver.
