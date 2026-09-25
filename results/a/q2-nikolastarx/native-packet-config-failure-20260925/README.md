# P2 native packet pilot: configuration adapter failure

Frozen source `f6014d3868c6e9f2ba74ee4ed807adab4be14ed8`; one CPU Standard Colab attempt, 2026-09-25 07:57:05Z. The native runtime source and ABI checks passed, then our adapter rejected the three fields returned by frozen E2 `read_config(problem=2)`. The public `SceneBEvaluator.evaluate_record` supplies `max_iter=1_000_000` before requiring four keys; our private caller omitted that normalization. This is an integration failure, not a candidate score or algorithm negative.

Actual calls: **0 proposal, 0 E2, 0 E0, 0 separate prepare**. Child exit 1 in 0.745 seconds; no surviving processes. Controller successfully downloaded the failure artifact (its `completed_downloaded_unverified` is not scientific success), stopped its session, read an empty session list and reaped the watchdog. No automatic retry.

Results ZIP: 3301 bytes, SHA-256 `6023fcc6a788a7f558987dd53ef9823b1aef35529d1fc4a76a64c0784cb6d4c9`, seven members, CRC passed. Runtime compatibility receipt describes the actual new Python 3.13.15 / NumPy 2.1.3 environment and pinned binary ABI; it does not reuse the old environment attestation as current. The formal full500 benchmark is unchanged.

Historical launch scripts require the original output directory and frozen capsule; do not execute them from this archive. See files.json for archived byte hashes.
