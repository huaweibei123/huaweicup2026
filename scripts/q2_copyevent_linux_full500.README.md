# Linux P2 COPY-event full500 producer

This script runs one frozen algorithm, upstream solver commit
`295ec9cf4351b77f5c6fffe8fbb23e8bc8d2f323`, across all 100 official
graphs and cores 1–5. It requires a capsule manifest made from fixed Git
blobs. The manifest hashes every solver `.py`, the runner, official code,
config, graphs, E2 source, and the report-only single-core baseline artifact.
The solver package's `.py` set must match the manifest exactly, including its
own historical `hypergap_full500.py`; the portable runner lives in `scripts/`
to keep that solver set unchanged. The capsule's local Git HEAD exists for
the solver's `git rev-parse` readback and is recorded separately from the
upstream solver and runner source commits.

Preflight also verifies the official source manifest, the byte-identical
fixed P2 manifest alias, all 50 E2 sources, Linux build receipt, binary SHA,
and native ABI through the existing source checker. The launcher must create
`runtime-identity.json` and `e2-linux-build.json` after compiling E2; their
hashes have no defaults. Run `preflight` before scheduling and give `run` a
fresh output path outside the capsule:

```sh
python -B scripts/q2_copyevent_linux_full500.py preflight
python -B scripts/q2_copyevent_linux_full500.py run --output /path/to/new-output
```

Limits are at most two workers, four native E2 attempts and one independent
E0 per cell, 2000/500 calls over the grid, no retry, 180 seconds per solver
or E0 process, 7200 seconds for the batch, and 4 GiB sampled RSS per cell.
The launcher must enforce the separate 8 GiB total process-tree cap with its
outer watchdog; this script's monitor enforces each cell cap. Setup, package
transfer, environment sync, and Linux native compilation must be reported
separately from measured solver wall time.

Every cell retains the plan, full solver ledger and attempt records, stdout,
stderr, process receipts, and independent official result/trace/log. A selected
native E2 score must match the final official E0 in Makespan, traffic, and all
five movement fields. A genuine one-plan route with zero E2 requests can be
certified by independent E0 alone and is labeled as such. Failed, timed-out,
unknown, or fallback calls stop new dispatch; already in-flight cells finish
and gaps remain visible. Only 500 accepted cells make a complete run.

The baseline artifact contains 100 fixed official single-core Makespans and
result provenance for speedup denominators. It is not fed to the solver.
Unlike the older macOS hypergap runner, this producer does not replay each
old selected plan through native E2 or compare the first new score to a saved
old plan. Its evidence supports this algorithm's frozen full-grid result only.
