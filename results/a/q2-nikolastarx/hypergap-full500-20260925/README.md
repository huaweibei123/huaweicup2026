# Prepared adaptive hypergap guarded full500 runner

This package prepares one fixed algorithm across all 100 official P2 graphs and
1–5 cores (500 cells). It has **not** constructed or scored any cell. A separate
resource/scheduling release is required before `run`. The selector entry is
`src.q2_nikolastarx.adaptive_hypergap_guarded`; its first native score, when
requested, must match the frozen `60afc38` adaptive-budget plan and E0 truth.
The completed `923b` gap batch is useful for later retrospective comparison,
not an input, forced per-cell winner, or a new score for this algorithm.

The [manifest](manifest.json) pins the solver source commit, all 47 solver
`.py` hashes, the old baseline manifest SHA, and the 500-cell budget. The
separate `manifest-workers1.json` and `manifest-workers2.json` retain those
identities and every evaluation/time limit, changing only the frozen runtime
worker count. Pick one manifest after resource coordination; worker count is
recorded in the run summary, and wall times from different worker counts are
different runtime conditions. None of these variants has been run.

The runner file is auxiliary: at launch, `--runner-commit` freezes its exact bytes,
this manifest, and process-monitor helpers. Runtime solver readback includes
both the solver set and runner. Official input must be supplied with
`--raw-root` pointing to a directory containing `code/` and `data/`; this
worktree does not contain the raw graph files. The actual Python venv entry is
passed through `--python` without resolving its symlink, and an import-only
probe checks NumPy and E2 modules inside the pinned export. Preflight checks
500 graph hashes, official code/config, E2 source/binary, and every frozen
baseline plan/result hash. It makes zero candidate or evaluator calls.
Pass `--runner-commit <full SHA>` to `preflight` to also check the committed
runner, manifest, monitor, and full solver file set before any run directory
is created.

```sh
/path/to/venv/bin/python -B -m src.q2_nikolastarx.hypergap_full500 preflight \
  --manifest results/a/q2-nikolastarx/hypergap-full500-20260925/manifest.json \
  --raw-root /path/to/official \
  --e2-root /path/to/isolated-e2-export \
  --python /path/to/venv/bin/python
```

After review and explicit scheduling release, `run` additionally requires the
full `--runner-commit` and a fresh `--output`. The runner uses four monitored
workers. Per cell, the solver (including at most three public native E2
requests) gets 60 seconds, then exactly one independent official E0 gets 60
seconds. Each monitored cell has a 4 GiB observed process-tree RSS limit; the
batch has 7,200 seconds and zero retries. The selected manifest limits workers
to 1, 2, or 4. It reserves at most 1,500 possible
fallback calls. First fallback, unknown request, source mismatch, unexpected
construction error, missing score evidence, E2/E0 mismatch, timeout, or other
failure stops new scheduling. Already-running cells finish safely and keep
receipts. The stopped directory is never resumed or overwritten.

Each cell directory keeps the full selected plan, online ledger, process
receipts, official result, trace, and log. `summary.json` stores only scalar
metrics, hashes, call counts, and relative paths; it never embeds a full E0
trace or ledger. A partial run is not a full500 score. Only 500 accepted cells
from this one frozen version may support a full-batch mean. Solver wall time
includes online E2 and plan write; independent final E0 wall is reported
separately. Four-worker batch wall is shared-host throughput, not an exclusive
single-case solver time.
