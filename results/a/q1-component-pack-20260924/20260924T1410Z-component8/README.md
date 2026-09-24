# Component-pack: eight frozen P1 development cells

1. **Goal:** test whether preserving whole independent compute components and
   using one Task per core removes fixed64's artificial Task dependency chain,
   while recording regressions and memory costs.
2. **Inputs:** solver `2cf3951af50be1e35ff78acb91629f2d0207bd82`, runner
   `08fd5af400619231e261e36d48b91cf4298a063e`, frozen official source manifest,
   cases 002/020/044/045/080/097 at four cores and 020/044 at one core. Baseline
   and fixed64 evidence were reused from
   `6664a63adc3464d28d1f835d907cdeaea23e6b35`, not recomputed.
3. **Outputs:** `board-feed.json` (v1), `comparison.json`, `batch.json`, each
   cell's plan, full official result and trace (lossless gzip), diagnostics,
   process logs and run receipt. `references/` preserves exact baseline bytes
   and selected original fixed64 records. The exporter verifies historical
   result hashes and checks fixed64's reported Makespan against its raw result.
4. **Limits:** one active cell; at most 8 solver and 8 E0 starts; 30-second
   constructor / 60-second external E0 timeouts; no retry/search/E1/E2; stop
   on first unexpected failure. No cloud or GPU used. Other P2/Q3 sessions may
   concurrently use one worker each; this is not an exclusive timing trial.
5. **Verification:** all 8 cells returned and parsed valid official scene A
   results at the requested core count. Actual calls: 8 solver, 8 E0, 0 E1/E2,
   no failed or unrun cells. Submission preflight reported 8 records, 8
   eligible, no reported/failed rows. That checks format and evidence bytes,
   not independent solver reruns or scientific acceptance.
6. **Execution:** 2026-09-24 14:09:40.605–14:09:50.980 UTC on Apple M5 Pro,
   macOS 27 arm64, 48 GiB RAM, Python 3.12.13, locked dependencies. The run ID
   is a label; precise measurement times are in `batch.json` and per-cell
   receipts. No further execution is permitted by reusing this batch.

## Results

All Makespans below are simulated cycles. Speedup is the exact official
singlecore baseline divided by this candidate's Makespan; the table rounds
only the displayed ratio. JSON preserves full values.

| Case | Cores | Component-pack | Existing fixed64 | Official singlecore | Singlecore speedup | Extra DDR bytes | Spill bytes | Solver wall s | External E0 wall s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 002 | 4 | 261945 | 255464 | 261945 | 1.0000 | 0 | 0 | 0.075950 | 0.391541 |
| 020 | 4 | 133704 | 1078404 | 532746 | 3.9845 | 0 | 0 | 0.130929 | 1.302679 |
| 044 | 4 | 124268 | 131407 | 154407 | 1.2425 | 5678624 | 2887424 | 0.040464 | 0.171437 |
| 045 | 4 | 31878 | 204380 | 125614 | 3.9405 | 0 | 0 | 0.035907 | 0.180361 |
| 080 | 4 | 111314 | 354762 | 292138 | 2.6244 | 4190208 | 0 | 0.037730 | 0.185673 |
| 097 | 4 | 2626908 | 5532446 | 11491509 | 4.3745 | 14221312 | 6553600 | 0.128301 | 2.296132 |
| 020 | 1 | 532746 | 1078404 | 532746 | 1.0000 | 0 | 0 | 0.133220 | 4.737369 |
| 044 | 1 | 154407 | 131407 | 154407 | 1.0000 | 4438112 | 4438112 | 0.041137 | 0.341114 |

The six four-core development cells have arithmetic-mean baseline speedup
2.8610831032. This selected diagnostic set is **not** a full-100 score. Five
four-core cases improve over fixed64; 002 regresses by 2.53695% in Makespan.
The two one-core outputs happen to equal the official singlecore baseline;
this observation is not a general equivalence proof. Case044 at one core is
worse than fixed64, so fewer Tasks is not a universal objective.

## Interpretation and next hypotheses

- Case020: 288 independent weak components become four balanced Tasks (1752
  compute ops per core), replacing fixed64's 110-Task chain. It achieves
  8.0656 times lower Makespan than fixed64, with no extra DDR or spill. This
  supports the structural hypothesis on this case; the experiment changes
  partition, allocation and local ordering jointly, so it is not an isolated
  causal decomposition of every contributing mechanism.
- Case002: one weak component with 1798 compute ops becomes one Task/core.
  Preserving whole components leaves no parallelism. This is a limitation
  for connected graphs and motivates a separate legal intra-component
  decomposition, not a claim that all graphs should be packed this way.
- Case044 and 097 still spill (2,887,424 and 6,553,600 bytes at four cores).
  Component independence is not a memory certificate. Case097's speedup over
  this fixed singlecore baseline exceeds four; the baseline is a specific
  official schedule, not an optimum or a universal parallel lower bound.
- Observed constructor startup-to-exit times are 0.0359–0.1332 s, total
  0.6236 s for eight calls; independent E0 totals 9.6063 s. Graph read,
  construction, validation and plan/diagnostics publication are included in
  solver wall. Source-byte/hash preflight, exact input ZIP materialization
  (0.00848 s shared), gzip and export are benchmark infrastructure, recorded
  separately and not online algorithm operations. Every solver starts a fresh
  interpreter; filesystem cache is not flushed. Historical fixed64 used a
  different concurrency/polling arrangement, so these times do not establish
  a controlled program-speedup ratio, tail latency or P95.

## Commands and evidence scope

From the runner's frozen checkout, after `uv sync --locked`:

```sh
uv run python -B src/q1_benchmarks/component_pack_e0.py run 20260924T1410Z-component8
uv run python -B src/q1_benchmarks/component_pack_e0.py export 20260924T1410Z-component8
```

`run` refuses any existing batch directory. These commands record the original
execution, not permission to replay it. `export` does not execute algorithms
or evaluators. Preflight used the main-branch `src/benchmark_board/protocol.py`
and `--submission --repo <this-checkout>` because the algorithm's historical
base predates the board service. `PRECHECK.json` contains its actual output.

Source SHA/hash checks were completed before calls. Full official result and
trace JSON bytes are retained in gzip and checked by a round trip. Process
stdout/stderr only replace personal workspace/temporary-directory roots by
public labels; this derivation is recorded in the receipts. Original official
result bytes were not edited. This validation agent inherited the parent
algorithm discussion and therefore is not a blind independent reviewer.
