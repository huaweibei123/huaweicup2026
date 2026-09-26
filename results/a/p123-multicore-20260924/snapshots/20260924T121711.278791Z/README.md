# Receipt-only benchmark snapshot

Capture: 2026-09-24T12:17:11.278791+00:00 to 2026-09-24T12:17:24.392912+00:00 (UTC).

This is a **non-atomic snapshot of a live run**, not its final outcome. Use `comparison.csv` for 1500 unique expected positions: 200 reused baseline anchors (100 each for P1/P2 core1) and 1300 solver positions (P1/P2: 400 each; P3: 500). `captured-comparison.csv` and `captured-progress.json` preserve exact observed bytes; they may lag the independently reconstructed table. `manifest.json` records their SHA256 and coverage.

`receipts.jsonl` contains compact allowlisted fields, source-relative paths and SHA256 of original receipt bytes. `protocol.json`, `harness-revisions.json` and `lineage.json` distinguish the original protocol from actual receipt harness declarations and hash-matched legacy evidence. Result/trace files and stdout/stderr are not copied or revalidated.

`status` is the final cell outcome where observed. `capture_state` and `status_reason` explain incomplete slots; no directory or old PID proves OS liveness. `ok` does not imply all metrics are present. `multicore_speedup` uses a successful official baseline divided by successful Makespan. P3 `cache_speedup` additionally requires equal plan, graph, configuration and core identities in the recorded online/P2 pair. Each absent ratio has a reason.

Timing units are seconds; Makespan units are simulated cycles. `solver_wall_seconds` is the recorded external solver duration. P1/P3 `e0_wall_seconds` is an included E0 component and must not be added again; P2 records its separate official process wall. `pair_wall_seconds` and `pair_eval_seconds` are the separate P3 no-cache process/function costs. `cell_wall_seconds` covers the controller cell; baseline wall/eval costs are shared across anchors, not additive per row. No missing timing is invented.

Reproduce with `python -B src/benchmarks/p123_snapshot.py --run-dir <source_run>`. It creates a new timestamped directory and does not overwrite previous snapshots. Live state will have advanced, so a new capture is not byte-identical.
