# Prepared latency hypercut pilot — not run

Fixed coordinates are 005/k5, 009/k5, 015/k5. Each cold worker reads the official graph and config, constructs one `gap_candidate.build` seed independently of the old run, calls `latency_hyperrefine.build(region_width=16)` once, and writes the complete selected plan. The constructor uses the unchanged pairwise region width and Pipe caps, plus fixed-owner retiming after an accepted proxy cut. Seed/selected original COPY byte counts and before/after isolated-transfer proxy cycles are recorded separately. Neither is an official Makespan prediction or bound. The saved c665 old plan is read only for identity verification; it never seeds candidate construction.

One public native E2 request scores each complete candidate. Independent E0 runs only when native Makespan is strictly lower than that cell's old c665 official E0 Makespan. The old E0 is accepted for comparison only after checking graph/config hashes, complete selected plan hash, c665 algorithm source set and ff47 runner checkout, E2 source identity, native online ledger, selected canonical plan/score binding, and successful old E0 process. No case-specific algorithm branch or historical score enters construction.

Limits: one worker, at most three native E2 requests and three independent E0 calls; no E1; 60 seconds for each cold construction plus E2, 60 seconds for each E0, 360 seconds for the batch, 4 GiB observed process-tree RSS, zero retries. The first fallback, unknown in-flight request, source mismatch, timeout, failure, or E2/E0 metric mismatch stops the remaining cells. The fresh output directory cannot resume. The runner pins its own bytes and **all currently present solver Python sources** (at least 47, including `latency_hyperrefine.py`) to the full `--runner-commit`, checks official source/input hashes and isolated E2 identity, and retains native/E0 originals and gzip hashes. The requested venv Python entry path is kept without resolving its symlink.

After independent review, commit/freeze, and resource scheduling release, the command shape is:

```sh
/path/to/verified-venv/bin/python results/a/q2-nikolastarx/latency-hypercut-pilot-20260925/pilot.py \
  --runner-commit FULL_CURRENT_HEAD --python /path/to/verified-venv/bin/python \
  --raw-root /path/to/official --old-run /path/to/complete-c665-run \
  --e2-root /path/to/isolated-603b-export --output /path/to/fresh-output
```

This preparation used syntax/import checks only: zero real constructions, zero E0/E1/E2 calls. Even a successful three-cell pilot is partial mechanism evidence, not a 500-cell fixed-algorithm score. The old c665 run and previous pilot failure history remain separate evidence.
The read-only old-run identity check passed for 005/k5, 009/k5, and 015/k5 against the existing c665 run (old E0 Makespans 33,515; 51,905; 40,828). The runner accepts either the official source root containing `data/` or that `data/` directory as `--raw-root`.

Source audit: frozen P2 Task construction retains even zero-byte cross-core direct edges as explicit COPY pairs (multicore_cut_evaluate_problem_2.py, direct-edge lowering); the proxy therefore retains the fixed release delay for them. Shared tensor fanout is charged per distinct receiving core, not per consumer. Summing these delays is still a placement heuristic because transfers may overlap and need not be critical.
