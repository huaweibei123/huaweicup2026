# Constructor-only profile evidence

Report: `docs/a/q2-nikolastarx/CONSTRUCTOR_PERF.md`.
Frozen constructor source: `dd9d89918f7a4e3d2cfab48d4d0246db3408310b`.

Executed once per graph (008, 014, 025), serially on the shared Mac:

```sh
.venv/bin/python -B results/a/q2-nikolastarx/constructor-profile-20260924/profile_once.py 008
.venv/bin/python -B results/a/q2-nikolastarx/constructor-profile-20260924/profile_once.py 014
.venv/bin/python -B results/a/q2-nikolastarx/constructor-profile-20260924/profile_once.py 025
.venv/bin/python -B -X importtime -m src.q2_nikolastarx.direct_solve --help > results/a/q2-nikolastarx/constructor-profile-20260924/importtime-help.stdout.txt 2> results/a/q2-nikolastarx/constructor-profile-20260924/importtime-help.stderr.txt
```

`profile_once.py` invokes the original CLI through runpy, with evaluator entry
points and child-process creation poisoned. Each output is identical to the
already measured pilot's k4 plan. This is three constructions, zero E0/E1/E2,
one importtime capture. It is not an additional performance-score batch.

The first 008 CLI/profile succeeded, then a metadata-only
`platform.platform()` lookup hit the subprocess guard. Summary generation was
recovered with `profile_once.py 008 --summarize-only`, which only reads preserved
pstats and plans. No construction or profile was repeated. The harness now
uses os.uname metadata without subprocesses. Its null elapsed value is
intentional; raw pstats supplies the observed accounted time. Original solver
timestamps are `profile_started_at`; summary recovery time is separately kept.

Each case folder contains the actual plan, solver ledger, normalized binary profile,
sorted text reports, and a machine-readable function summary. `hotspots.json`
extracts selected cumulative totals, which overlap and must not be added as
independent phases. `dependency-inventory.json` is a metadata-only environment
inventory. The importtime file is raw stderr from the real --help command.
`normalize_profiles.py` moved the three original pstats to
`/tmp/p2-constructor-profile-20260924-s8ee/` and substituted `${REPO_ROOT}` and
`${PYTHON_BASE}` in filename/caller keys for the repository copies. It retained
every call count, timing and caller edge, checking total time/counts after
reload. `normalization-receipt.json` records both hashes and raw local paths.
This is an explicitly derived export; it is not the original profile bytes.
Summaries also normalize repository and Python prefixes. Raw artifacts are diagnosis only,
not new scores, exclusive timings, or improvements over Fang.

Do not rerun these commands into the same output directory. Any new profile or
performance validation needs its own declared scope and evidence directory.
