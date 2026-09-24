# Sealed-tree DP rejected candidate evidence

This is research evidence, not a production solver release or a benchmark entry.
New official E0 calls: **0**. Exactly one deterministic construction per original
case 002/062/063 at five cores, frozen delay 500; no parameter grid.

The three plans have guarded lower bounds 63608/671532/252092, already larger
than successful official incumbents 54341/588101/232381. They are therefore
excluded from improving Makespan without any new E0. No candidate official
Makespan was fabricated; the recorded value remains null. Scope is these exact
plan hashes, not all sealed-subtree schedules or all graph/core combinations.

Files:

- `q3_sealed_tree_prototype.py`: independently written Index adapter; source and
  archived Pro attribution are in its header. Downloaded code was only read.
- `q3_sealed_tree_check.py`, `q3-sealed-tree-static-check.json`: 504 random-plan
  checks, 1008 signature-state checks, eight fixed mechanisms and four rejects.
- `q3_sealed_tree_cases.py`: deterministic three-input static construction.
- `q3-sealed-tree-cases/`: three original two-field plans, metadata and independent
  static pipe-bound output, plus summary and SHA-pinned pruning audit.
- `q3_sealed_tree_prune_audit.py`: verifies saved incumbent artifact bytes and
  input/config/code identities, recomputes the static guard, records exclusion.
- `SEALED_TREE_REVIEW.md`: mathematical review and conclusion scope.
- `MANIFEST.json`: payload SHA-256 values, excluding this manifest itself.

Replay is optional and uses only static checks, never E0. Copy the bundle to a
scratch directory first, because scripts rewrite their own diagnostic outputs.
From the project worktree with its existing `.venv`, set `PYTHONPATH` to the
project root and run these scripts by path in order: check, cases, prune_audit.
The pruning audit requires the already published release result commit
f44a7548f8e798f40e83a75bec75712313888661 and its saved result files.
Do not import or run the archived downloaded ZIP to reproduce this adapter.
