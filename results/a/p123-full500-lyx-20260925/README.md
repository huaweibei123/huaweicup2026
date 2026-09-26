# P1/P2/P3 fixed-batch visualization preview

Status: the captain-approved three-panel preview has been generated and locally validated.

Captain approval: Issue 15, comment 5830738949, 2026-09-25.
Scope: one three-panel preview in PNG/PDF/SVG, with a reusable Python script, per-case data, summaries, and provenance. No solver, E0, E1, or E2 runs are authorized or needed for this plotting task.

## Previous-task checkpoint

The existing 1,300-slot benchmark and its untracked raw results are preserved. The 845-record volume under `results/a/p123-multicore-20260924/submissions/20260924-cases011-075` remains pending publication; this plotting task neither republishes nor changes it. The previous source-audit task is not represented as completed. Existing files outside the three allocated visualization directories are not edited.

## Interpretation

These inputs are captain-selected full-coverage reference batches, not proof of globally best solutions. P1/P2 use the arithmetic mean of per-case official-singlecore/multicore makespan ratios, without forcing the one-core point to 1. P3 requires verified same-plan cache pairs and reports both mean makespans and the mean of per-case no-cache/cache ratios. Missing or rejected records must never be imputed as zero.

P3 also retains `official_singlecore_makespan / current_cache_makespan` in the per-case and summary files for provenance and the captain's k=1 anchor check. That speedup is distinct from CacheGain and is not substituted for it in the third panel.

## Validated coverage

Each problem contains 100 cases at each of 1–5 cores: P1 500/500, P2 500/500, and P3 500/500 identity-matched Cache pairs. All exclusion-count dictionaries are empty. The k=1 arithmetic means are P1 1.002097×, P2 1.108597×, and P3 official-baseline speedup 1.199407×; these agree with the captain's independent checking anchors. P3 CacheGain rises from 1.002349× at one core to 1.084465× at five cores.

## Reproduction

```powershell
uv run python src/analysis/p123_full500_lyx/make_preview.py
```

The script verifies fixed feed Git blob IDs, artifact SHA-256 values, and all five P3 pair identities (`graph`, `config`, `official`, `plan`, and `cores`). It invokes no solver or evaluator. `summary.json`, `per_case.json`, and `manifest.json` are the published numeric/provenance outputs; the verified input cache remains local and is excluded from Git.

The figure is exported as PNG for review and PDF/SVG for paper editing under `figures/a/p123-full500-lyx-20260925/`.
