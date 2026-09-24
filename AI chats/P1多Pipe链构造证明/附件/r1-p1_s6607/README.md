# s6607 P1 reentrant-chain research delivery

Start with [RESEARCH_NOTE.md](RESEARCH_NOTE.md).

**Official solver/E0/E1/E2 calls in this session: zero.** The official graph ZIP could not be retrieved. Eight self-contained synthetic-graph prototype processes and two mathematical/model unit-test processes were actually run; receipts, all input/plan/model bytes, logs and code are retained.

Main files:

- `p1_phase_cut.py`: two-key return-rotation candidate; conservative acceptance wrapper. Not E0.
- `lower_bounds_extensions.py`: universal resource-window and cut-or-blocking certificates.
- `integrate_frozen.py`: deployment adapter for a byte-verified frozen repository, not executed here.
- `audit_compiled_plan.py`: read-only official compiler audit and fixed-plan bound, not executed here.
- `make_micrographs.py`, `run_micro_experiments.py`, `test_research.py`: reproducible finite synthetic tests.
- `ACCESS_AND_EXECUTION_MANIFEST.json`: precisely what source was read and what was not.
- `experiments/ledger.json`: eight complete-process wall measurements and source/input/plan/model hashes.
- `experiments/tests_receipt.json`: both unit runs and source-version details.
- `SHA256SUMS.json`: integrity inventory for this delivery.

No third-party packages are required for the self-contained modules. Tested with Python 3.13.5. The frozen repository adapter additionally needs that repository and its normal environment.

The eight original CLI receipts identify `artifacts/p1_phase_cut_executed_v1.py`. The final module adds iteration-limit sufficient guards and was unit-tested again. The earlier three static lower-bound generations lacked a pre-run source hash; their source is reconstructed from the recorded patch and explicitly labeled. They are not official scores. Do not replace historical artifacts when rerunning; use a new directory.

The saved 008 plan/config/log have local byte identity checks. The compressed-result prefix does **not** have full GZip integrity validation. No complete 008 raw graph or full trace was obtained.
