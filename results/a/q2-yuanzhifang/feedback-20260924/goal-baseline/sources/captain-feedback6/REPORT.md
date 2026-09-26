# P2 fixed feedback batch — official E0 results

Frozen solver: `f17fcc2d84d20497482a1269de7bac95ab7a3138`; execution runner: `4d9b32a19f060f408bea1b2768c16f0cd4e14a0d`.

All six predetermined development cases completed. This worker inherits the parent research context and is not a blind scientific reviewer. No production board write, Git push, PR, or mirror sync was performed by this worker.

Execution UTC: 2026-09-24T14:09:40.033060Z to 2026-09-24T14:10:11.609388Z; measured batch execution 31.576325709 s before compression/export. Do not treat batch wall as per-case solver wall.

24 online E0 + 6 separately launched final E0 = 30 actual E0; 6 solver launches; E1/E2 = 0. No failed execution, timeout, retry or duplicate skip. The exact budget is exhausted; no further evaluation is authorized by this batch.

| Case | contiguous | chain critical | affine eighth | guarded reentry | Selected actual strategy | Final | Prior board best | Change vs board | Solver wall s | Final E0 wall s |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 002 | 132209 | 72795 | 270245 | 276740 | chain_critical | 72795 | 72056 | +1.026% | 1.389680 | 0.330369 |
| 008 | 123060 | 233922 | 64686 | 63768 | resource_word | 63768 | 123060 | -48.181% | 0.768711 | 0.245078 |
| 044 | 125648 | 74713 | 91922 | 66901 | pipe_ready | 66901 | 69113 | -3.201% | 0.764710 | 0.246636 |
| 064 | 20304 | 24843 | 17829 | 16615 | pipe_ready | 16615 | 20304 | -18.169% | 0.704884 | 0.205488 |
| 051 | 610775 | 207134 | 607628 | 1331378 | chain_critical | 207134 | 610775 | -66.087% | 0.946559 | 0.295602 |
| 016 | 7720311 | 2556787 | 7715523 | 16893158 | chain_critical | 2556787 | 7720311 | -66.882% | 20.745567 | 4.107825 |

Makespan is in simulated cycles; lower is better. Prior board comparison is the frozen `../board-before.json` snapshot, a mixture of methods, not a single algorithm baseline. Per-case singlecore ratios, bytes and sampled peak RSS are in `metrics.csv`. All six final results preserve integer Makespan types.

008 uses the guarded M–V*–M resource word. 044 and 064 select the guard wrapper but actually use its `pipe_ready` fallback. Their improvements cannot be attributed to the resource-word theorem. In 002, the new result is 739 cycles worse than the historical board best; incumbent protection guarantees only nonregression against the successful contiguous plan in this run. The large 051/016 pipe-ready regressions are retained and excluded by the official selector, not deleted.

Each final plan was independently evaluated and its full result JSON bytes matched the selected online result (6/6). Every candidate plan hash, result Makespan value and Python type, scene/core count, movement fields and successful exit code was checked. All 60 compressed result/trace JSON files round-trip to their original byte hashes. `batch.json` includes the lossless compression map; solver ledger paths with `.json` refer to corresponding `.json.gz` preserved bytes after archiving.

Actual subprocess argv, UTC, observed RSS, descendant cleanup and online ledger remain in each `<case>/run.json`. Source/config/case hashes were checked before each solve; official files remain frozen. Three monitor tests used only fake child processes, including a grandchild that starts its own session; no evaluator was called by those tests.

Solver wall covers fresh interpreter startup, input reading, four constructors, online E0, output, observed exit and necessary cleanup. The independently reported final E0 wall is outside solver wall (`timing.solver_includes_evaluation=false`). The observer polls at a 50 ms target interval and records `ps`/cleanup overhead; this is not kernel-only timing. Process startup is cold, OS file caches are not flushed. P1/Q3 work may run concurrently on the same Mac; no exclusive-machine speedup is claimed.

Machine: Apple M5 Pro, macOS 27 arm64, 48 GiB RAM, Python 3.12.13, one worker and CPU-only Python. Per-tree peak RSS is sampled, and the 4 GiB stop also includes the observer process. Short memory peaks may be missed. No measured tree approached the threshold. Preparation/extraction/static development preceded this run and their elapsed costs are not reconstructed; the from-graph solver loads no previously optimized per-case plan.

Limits: per E0 60 s, per solver 240 s, whole execution 1200 s, one worker, no retries, no new samples after outcomes. This is a development sample, not a holdout or whole-100-case generalization. No new singlecore run was performed: original shared E0 denominators were read and verified.

`board-feed.json` is board-submission-v1 with six end-to-end portfolio records and existing baseline references. Read-only precheck reports 6 records, 6 eligible, no reported/failed records. Precheck and raw evidence availability do not imply central import or algorithm scientific acceptance.

The 24 online CLI stdout messages include a local checkout prefix. Shared stdout copies replace only that prefix with `${REPO_ROOT}`; `stdout-redaction.json` records raw and derived hashes. Unredacted originals are retained locally outside Git, and their location was supplied to the parent. Official plan/result/trace bytes are unchanged.
