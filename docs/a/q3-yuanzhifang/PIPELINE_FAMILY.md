# Pipeline family k5 structural batch (2026-09-25)

This is a frozen development benchmark for `pipeline_stages.py` at commit
`6bae8dfa317bc71226068344b59dd65d2612c32b`. It tests cases 044, 046,
067, 073, 083 and 092, each with five requested cores and the official fixed
configuration. It does not replace the unified full500 solver result or claim
independent acceptance.

The constructor reads one original graph, forms homogeneous shared-input
chains, and solves a contiguous stage partition of a copy-free flowshop
abstraction by an O(k L²) dynamic program. The actual hardware simulation
includes copies, contention, capacity and dependencies; the abstraction's
objective is neither a bound nor the official Makespan. Only an unchanged E0
P2/P3 evaluation of each guarded output supplies official measurements.

## Fixed scope and runtime

- Graphs: `../huaweicup2026/data/raw/a/official-cases/data/case_*.json` for
  the six listed IDs. Official code, graph bytes and config are checked against
  `docs/a/source-manifest.json` before any call.
- Candidate and its Python dependencies are byte-checked against their fixed
  commits. The benchmark, exporter, this note and feed template are likewise
  verified by `--check-only`; commit these three files before that check.
- At most six fresh-process cold solver calls and twelve external E0 calls;
  zero E1/E2, zero control reruns, zero automatic retries. The output directory
  is `results/a/q3-yuanzhifang/pipeline-family-20260925` and must be absent at
  first execution. Its run ID is
  `yuanzhifang-q3-pipeline-family-20260925`.
- A single driver manages at most two case workers. Each case executes cold
  construction, P2, then P3. A global lock checks available physical RAM and
  free output disk immediately before every dispatch; each must be at least
  2 GiB. Unknown resources stop dispatch. Children use Windows
  `BELOW_NORMAL_PRIORITY_CLASS` and one numerical-library thread.
- Each call has a 30-second cap; the whole batch has a 300-second cap and
  dispatch stops at 270 seconds. A rejected structure, failed child, failed
  result validation, resource failure or timeout stops new dispatch. Already
  running calls are allowed to finish or are terminated by their own timeout.
  Their output and failure receipts are preserved.

Run identity verification only:

```powershell
python -B src/q3_yuanzhifang/pipeline_family_benchmark.py --check-only
```

After review and a coordinated runtime window, declare actual concurrent work
and run once, for example:

```powershell
python -B src/q3_yuanzhifang/pipeline_family_benchmark.py --concurrent-work P1+P2
python -B src/q3_yuanzhifang/pipeline_family_export.py
```

`--check-only` performs file identity and baseline verification but creates no
output directory and runs no build, derive, Step or E0. The real runner records
the fresh process command, official inputs, platform inventory, concurrent
work declaration, resource checks, cold end-to-end wall time, E0 P2/P3 time,
call ledger, exact plan bytes and gzip-preserved stdout/stderr/result/trace/log
bytes with compressed and raw SHA-256 hashes. The exporter reads completed
receipts only, seals manifest and call-ledger snapshots before recording their
hashes in a standard board feed, and never starts a solver or evaluator. The
P3 row points to the same-case, same-plan, same-core E0 P2 result for its cache
comparison. Failed and partial attempts remain visible; no successful result
is overwritten by a later failure.
