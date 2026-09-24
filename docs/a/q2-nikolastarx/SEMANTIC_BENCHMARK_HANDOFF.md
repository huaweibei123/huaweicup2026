# P2 unified solver: exclusive benchmark handoff to s59ee

Algorithm owner: `nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894`.
Execution owner: the existing local benchmark task s59ee, coordinated by the
central scoreboard s7c98. This handoff follows the user's new request to finish
the P2 benchmark. It is a **new version**, not a silent continuation of the
old `6e5099a35300133419990bf1f44f621f98850c21` 500-cell batch.

1. **Objective.** Measure all 100 original graphs at 1–5 cores using one unified
   structural algorithm. Report legal execution, unmodified E0 Makespan, extra
   DDR and spill, plus actual end-to-end solver time. Publish full coverage and
   failure counts; compare per-case baseline/Makespan arithmetic means against
   the same frozen Fang version and target definition. Missing cases must not
   be imputed as successful scores or mixed with another algorithm's results.
2. **Fixed inputs and code.** Solver commit
   `b7c05cf2205bd42ec23680e618a10796b37562f6`; entry point
   `src.q2_nikolastarx.adaptive_semantic`. Source files are `baseline.py`,
   `direct.py`, `dag_direct.py`, `component_envelope.py`, `tree_frontier.py`,
   `tree_packets_first.py`, `tree_paired_leaves.py`, `vector_lanes.py`,
   `vector_arrival.py`, `adaptive_semantic.py`, all under `src/q2_nikolastarx/`.
   Use case_001.json through case_100.json and the unchanged official source
   manifest. Official code SHA-256:
   `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`;
   config SHA-256:
   `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`.
   Run `uv sync --locked`; freeze the actual runner, interpreter, lockfile and
   resource protocol separately. No random seed: the construction is deterministic.
3. **Exact missing matrix and ownership.** For this solver version, every
   `(case in 001..100, cores in 1..5)` is **not yet run as a full benchmark**:
   500 coordinates, zero successful/failed E0 executions under this program.
   Thirty static constructions are not official evaluations. s59ee is the sole
   writer of the new run root
   `results/a/q2-nikolastarx/semantic-benchmark-s59ee-20260925/`, including its
   protocols and result feeds. The algorithm owner will not write there or
   launch duplicate coordinates. Keep each parallel cell in its own directory.
   Algorithm source remains owned by s8ee; do not amend it while measuring.
4. **Outputs and validation.** Each cell retains exact plan, sidecar solver
   evidence, full E0 result/trace/log, command, environment, process receipt,
   checksums, protocol and standard feed. Submit via the central enqueue flow.
   The plan contains only `node_to_subgraph` and `core_schedules`. The solver
   ledger must have one top-level attempt, all online E0/E1/E2 counts zero and
   a matching final plan hash. A repair cell executes a base construction and
   one whole-lane reconstruction; both are included in solver wall time.
   External final E0 time is separate. Preserve failures, timeouts and unknown
   process outcomes, not just winners. Compress full JSON results/traces with
   byte-hash roundtrip receipts, retaining their evidence.
5. **Execution limits and scope.** At most 500 final E0 calls, zero online E0,
   E1 or E2, no automatic retry. Suggested per-cell bounds remain 30 s solver
   and 60 s E0, including a separately reserved cleanup allowance, with 4 GiB
   sampled process-tree RSS per cell. s59ee and central must freeze actual
   concurrency and aggregate deadline against currently available local RAM,
   CPU and P1/P3 windows; parallel workers must not each receive the whole
   500-cell allocation. These are execution limits, not official contest hard
   limits. The owner currently has zero solver/E0/Colab work in flight. Use the
   validated macOS path; static Windows fixes are not native Windows admission.
   Reuse or sparsely check out an execution tree; do not expand unrelated AI
   chat attachments or hundreds of old result folders.
6. **Completion and escalation.** No user calendar deadline. Completion needs
   500 terminal coordinates with valid/failed/unknown states and actual n/100
   statistics, plus central feed receipts. Unknown children/call counts,
   version drift or shared-host resource conflicts stop new dispatch until
   resolved. Failed cells receive no implicit retries. The original old-source
   batch's remaining 494 are not additionally dispatched or counted here.

## Command contract

Replace CASE, K and OUT with a declared coordinate and new directory:

```text
python -B -m src.q2_nikolastarx.adaptive_semantic data/raw/a/official/data/case_CASE.json --config data/raw/a/official/data/config.txt --cores K --output OUT/plan.json --evidence OUT/online --wall 30
python -B data/raw/a/official/code/multicore_cut_evaluate_problem_2.py data/raw/a/official/data/case_CASE.json OUT/plan.json --config data/raw/a/official/data/config.txt -o OUT/final/result.json --trace-output OUT/final/trace.json --log-output OUT/final/official.log
```

## Existing evidence and reuse boundary

The new-source static check covers six affected families × five cores, all 30
structurally valid and acyclic, with six exact official-plan matches. Nine of
the 30 also match the old 500-cell static hashes. The other 94 families were
recognized but not reconstructed in this new check. Six synthetic tests passed;
see `semantic-static-20260925/report.json` and `ADAPTIVE_SEMANTIC.md`.

Known matching official plans are 016 k2 from data
`0e990656155e857447410a5725ce5ff661fa6b5f`, 016 k4/k5 from direct data
`81219bf923524fb60616e39b5ad2dced67aec3e2`, and 062 k2/k4/k5 from data
`b8267f86fb545232bd20113aa24c52f5e0521853`. Exact paths and hashes are in
`semantic-static-20260925/rows.jsonl`. Reusing these scores requires the same
graph/config/official identities and an exact actual output-plan match; label
the score as reused and do not invent new E0 or solver timings. If the benchmark
needs independently measured new-source end-to-end timings, run the solver.
Any decision to reuse E0 must be explicit in the final fixed execution protocol.

The old-source six completed coordinates are 008k3, 014k4, 025k5, 016k1,
016k2 and 062k4, data `62d8d01b8746ef83f7b7e46749dbc27699fd566e`. They belong to
the old version and do not silently fill the new matrix. Their other 494
coordinates were unassigned, never dispatched. All recent P2 pilot feeds have
been accepted by central; acceptance and reused-plan equivalence do not prove
the full-suite improvement target.
