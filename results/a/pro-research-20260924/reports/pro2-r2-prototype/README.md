# Huaweicup A — independent round-2 prototype and evidence

## What is included

- `RESEARCH_MEMO_ROUND2.md`: Chinese research report, assumptions/proofs, all important positive and negative findings.
- `src/solve.py`: **frozen** bounded E0-only portfolio used in the 10 paired follow-up tests and large-case stress test.
- `src/word_cli.py`, `resource_word.py`: later specialized M→V*→M constructor. Not retrospectively part of the frozen portfolio results.
- `src/compact_priorities.py`: exact scoring-preserving priority-bucket coarsening experiment; **not enabled** because total cost regressed.
- `official/`: unmodified frozen code, configuration and docs; `official-cases.zip`: all100 original case bytes; `problem.pdf`.
- `audit/`, `analysis/`, `fixtures/`: raw identity checks, all100 structural records, semantic graphs, aggregate comparisons, counterexamples.
- Complete new E0 runs are in the separate evidence archive. Extract its `runs/` into this directory to resolve relative report references.

No network, GPU, external services, learned/precomputed case answers or E1/E2 are required to generate a new plan.

## Environment and limits

The author's recorded runs used Python3.13.5/Linux x86_64, one E0 process at a time. The team's 3.12 pin has **not** been independently replayed; do that before adopting formal scores. Code uses the standard library. `solve.json.source_environment` is a historical author-environment label in the frozen version; each new `run.json` records the actual executing interpreter/platform.

The max-evaluations and wall-time guards are prototype safeguards, not an all100 runtime guarantee. Source parsing and argument errors can fail before a plan exists. E0 timeout is unknown, not illegal. Never treat an unconfirmed generated plan as an official result. Explicitly supplied output directories must be fresh. Existing results and source data are not overwritten.

## Run

From this directory:

```sh
python extract_official.py
python src/solve.py official/data/case_044.json -n 4 -q 2 \
  --official official --output new_run_044 \
  --time-limit 300 --max-evaluations 24 --per-evaluation-timeout 60
```

The publicly submit-able incumbent is `new_run_044/incumbent.plan.json`. Sidecar `solve.json` and per-candidate directories retain timing, failure and proof-bound metadata; they are not public plan fields.

The reference portfolio under the same caps:

```sh
python src/solve.py official/data/case_044.json -n 4 -q 2 \
  --official official --output new_baseline_044 --policy baseline \
  --time-limit 300 --max-evaluations 24 --per-evaluation-timeout 60
```

Specialized constructor (only accepts its stated M→V*→M domain):

```sh
python src/word_cli.py official/data/case_008.json -n 4 -q 2 \
  --official official --output new_word_008 --official-evaluate
```

Omitting `--official-evaluate` generates a plan only and explicitly labels it unevaluated. This wrapper was plan-only tested byte-for-byte against a previously fully E0-evaluated plan. The underlying word constructor and native E0 were tested on three actual matching cases and multiple core counts.

## Replay an old complete result

After extracting the separate evidence archive into this directory:

```sh
python replay_one.py runs/resource_word/case_008_p2_word --output replay_word_008
```

Only `input_graph` and `input_plan` strings are removed for the comparison of parsed full official JSON. All operation times, ordering, cache histories, IDs and numeric statistics are retained. Original gzip result and trace bytes remain available and immutable. Failure replay does not equate timeouts with illegal inputs.

## Audits and provenance

`audit/final_evidence_audit.json` reports 894 official CLI calls:890 success,3 intentional cycle rejections,1 timeout;24 formal case IDs, not all100 performance coverage. `analysis/experiment_inventory.csv` indexes every run. Each saved run has original plan, stdout/stderr, run metadata and successful E0's full JSON/Trace/log (result and trace gzip-compressed without semantic alteration).

`runs/paired/FROZEN_PROTOCOL.json` fixes source hashes, 60seconds/24E0 caps and test matrix. Many B0 finite candidate families exhausted before the cap. Equal-call/time-prefix comparisons and negative cases are in `analysis/paired_comparison.json` and `mechanism_summary.json`. Large-case structured quality improved late: it was worse at the common early wall-time prefix. These facts must accompany any performance claim.

The `*_experiment.py` files are the original experiment drivers and retain author absolute paths for provenance. For new portable use, use the generic `solve.py`, `word_cli.py`, `extract_official.py` and `replay_one.py` commands above. `src/audit_evidence.py` also records original audit paths; the distribution manifest verifies delivered files independently.

The source bundle's old295 missing results remain missing. The supplied earlier64 truth files were not relabeled or counted among our new894 calls. This package is not a full FORM, E1 or E2 acceptance certificate, not a claim of global optimality, and not a measured CUDA/Metal implementation.
