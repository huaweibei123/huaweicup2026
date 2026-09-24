# Direct P2 pilot: 24 fixed cells

Source `dd9d89918f7a4e3d2cfab48d4d0246db3408310b`; runner `75c51e9faad12a3134ff3f060c4dae8991c4f54d`.

UTC 2026-09-24T15:06:34.961486Z to 2026-09-24T15:09:13.255889Z; execution batch wall 158.293422875 s; stop=all_fixed_cells_dispatched.

24 successful solver processes; zero online E0; 24 independent external E0. E1/E2=0. No failed cell, retry, replacement or continuation. Each cell has a separately validated feed, original plan/result/trace/log, process receipt and manifest. All 48 owned child PIDs had exited when checked.

| Case | Cores | Strategy | Makespan | Solver s | External E0 s | Δ vs audit Fang |
|---|---:|---|---:|---:|---:|---:|
| 002 | 2 | dag_eft | 131796 | 0.219888 | 0.522966 | -49.96% |
| 002 | 4 | dag_eft | 78812 | 0.223904 | 0.466054 | -40.39% |
| 002 | 5 | dag_eft | 72043 | 0.218008 | 0.435227 | -33.36% |
| 008 | 2 | resource_word | 125682 | 0.197951 | 0.268056 | -48.55% |
| 008 | 4 | resource_word | 63768 | 0.196860 | 0.275755 | -48.18% |
| 008 | 5 | resource_word | 52291 | 0.196383 | 0.280364 | -51.34% |
| 014 | 2 | dag_eft | 13097894 | 1.502600 | 15.902850 | +10.93% |
| 014 | 4 | dag_eft | 8292269 | 1.755251 | 17.242393 | -32.01% |
| 014 | 5 | dag_eft | 7364271 | 2.051493 | 17.773444 | +75.62% |
| 016 | 2 | dag_eft | 9260226 | 0.503534 | 6.074971 | +20.00% |
| 016 | 4 | dag_eft | 2250687 | 0.587725 | 4.306208 | -70.85% |
| 016 | 5 | dag_eft | 2240622 | 0.629153 | 3.876790 | -70.98% |
| 025 | 2 | dag_eft | 4251120 | 0.736417 | 8.056980 | +74.81% |
| 025 | 4 | dag_eft | 2585433 | 0.943325 | 8.075438 | +112.23% |
| 025 | 5 | dag_eft | 2279371 | 0.905529 | 7.796552 | +132.40% |
| 035 | 2 | dag_eft | 128427 | 0.281946 | 0.832104 | -24.65% |
| 035 | 4 | dag_eft | 105911 | 0.289358 | 0.844683 | -38.45% |
| 035 | 5 | dag_eft | 99765 | 0.289898 | 0.768774 | -5.29% |
| 062 | 2 | dag_eft | 2262944 | 0.739590 | 9.735443 | -20.69% |
| 062 | 4 | dag_eft | 1607053 | 0.893189 | 8.220393 | +12.11% |
| 062 | 5 | dag_eft | 1391629 | 0.946320 | 7.595491 | +67.17% |
| 071 | 2 | dag_eft | 16870 | 0.193217 | 0.284125 | -11.55% |
| 071 | 4 | dag_eft | 13146 | 0.198306 | 0.280353 | -21.11% |
| 071 | 5 | dag_eft | 11332 | 0.229657 | 0.283809 | -31.26% |

Makespan is simulated cycles; lower is better. The Fang comparison uses the existing target-audit CSV, whose identity is recorded in verification.json, and does not add any Fang or official evaluation calls. It is a development sample, not the full 100-case average or the full 1–5-core target. End-to-end solver wall includes process/observation/cleanup overhead but excludes the separately reported final E0. P1 may share this machine; wall measurements are nonexclusive.

Checked 336 files from per-cell manifests and 48 lossless compressed JSON round-trips. Stored artifact hashes, plan identity, official scene/core, Makespan numeric types, movement metrics and shared singlecore denominators match their records. All 24 producer prechecks report 1/1 eligible. No central import, Git commit/push, mirror sync or overall algorithm acceptance was performed by this worker.

Raw stdout retention root was emitted by the runner and sent to the parent. Shared informational stdout prefixes are redacted only where needed, with raw/shared hashes in each archive.json. Per-cell files are final; this batch-level summary does not alter them. Official .log files are normally ignored by Git and must be explicitly included by the parent publisher.

Aggregated `board-feed.json` contains the same 24 records without altering individual feeds; `precheck.json` records the successful 24-record producer-format check. The index and final batch manifest include its identity.
