# Q2/B stage A checkpoint — measured evidence

Evaluated source HEAD: `fd9d686c37b5a27a8595fc2f7483c089bf4a92e3`. Task card: `35709578f01689c20eaf9ef2dd68c274393a3a53`.
T0: 2026-09-24 03:56:25 Asia/Taipei. This is developer self-test, not independent acceptance.

## Six-field delivery

1. **Goal:** establish a deterministic Q2 baseline and verify priority/COPY/FIFO/capacity boundaries before search.
2. **Inputs:** frozen official case002/config and PDF minimal input; fixed Pro3 head_blocking/fork graph-plan pairs; labelled local synthetic negatives and memory-pressure input. No sealed cases.
3. **Outputs:** source constructor/runner, metrics.csv, all official result/trace/log files, negative stderr, hashes, environment and this generated report; method paragraph in paper/sections/a-q2.md.
4. **Constraints:** stage A only, serial, maximum 12 Q2 calls including final confirmation; 1800-second aggregate allowance; unmodified official source/config. No Q1/shared-evaluator/dependency changes.
5. **Checks:** fixed PDF answer, empty core, both fixed-assignment comparisons, rejection at three specific layers, legal spill/peak bounds and full repeat equality. Only the checks below were actually run.
6. **Checkpoint:** first evidence requested 60–90 minutes after T0; produced early and submitted to local coordination. Stage B remains unstarted.

## Results

| Invocation | Status | Makespan (cycles) | Added COPY (B) | Spill (B) | Supervised wall (s) |
|---|---|---:|---:|---:|---:|
| 01-pdf-minimal-empty-core | ok | 6 | 0 | 0 | 0.547 |
| 02-case002-stub | ok | 200352 | 4371456 | 0 | 1.281 |
| 03-case002-contiguous | ok | 132209 | 485376 | 0 | 0.766 |
| 04-fifo-blocked | ok | 15511 | 128 | 0 | 0.531 |
| 05-fifo-reordered | ok | 10511 | 128 | 0 | 0.562 |
| 06-fork-coarse | ok | 4940 | 80000 | 0 | 0.531 |
| 07-fork-fine | ok | 3938 | 80000 | 0 | 0.546 |
| 08-intra-core-reverse | rejected | — | — | — | 0.281 |
| 09-global-fifo-cycle | rejected | — | — | — | 0.282 |
| 10-op-capacity-rejection | rejected | — | — | — | 0.281 |
| 11-legal-memory-pressure | ok | 4687 | 280000 | 280000 | 0.282 |
| 12-case002-incumbent-confirmation | ok | 132209 | 485376 | 0 | 1.031 |

case002 contiguous construction: 132209 cycles versus random format stub 200352 cycles (34.0116% lower). The stub is not a strong baseline; this single-case comparison does not establish search quality or generalization.

The two Pro3 comparisons preserve core assignment and movement totals. They do not isolate every possible cause: changing priorities also changes shared DDR interactions. In fork, the source COPY_OUT completes earlier as shown below, directly explaining the earlier remote release in this input.

| Fork plan | COPY_OUT end | COPY_IN release | COPY_IN start | COPY_IN end |
|---|---:|---:|---:|---:|
| 06-fork-coarse | 1771 | 2271 | 2271 | 2938 |
| 07-fork-fine | 769 | 1269 | 1269 | 1936 |

## Budget, preparation and limitations

Actual official Q2 launches: **12 / 12**. Nine successful evaluations and three expected rejections; no timed-out or resource-limited Q2 invocation. The original run directory failed before any Q2 launch due to Windows GBK decoding of the UTF-8 manifest; its zero-call ledger and failure note are preserved. The continuation used a 1770-second ceiling, conservatively reserving 30 seconds for that preflight.
Recorded experiment wall: **12.469 s**, through comparison checks and before final metrics/artifact hashing. Summed supervised Q2 intervals: **6.921 s**. These include process startup, output and up to a sampling interval of observation delay; they are not evaluator speed benchmarks. Final report generation/hash verification and public setup are additional explicitly unbenchmarked overheads.
Largest sampled controller+child working set: **81.566 MiB** during monitored subprocesses. This does not include a continuous sample of static archive reading/reporting and is not an OS hard limit or proof of whole-run peak memory. All six monitor/control tests passed after fixing Windows venv redirector reaping; they invoked zero official evaluators.
Public preparation: uv sync --locked succeeded (14 packages; uv reported installation in 1m 28s); scripts/a_materials.py --extract verified 114 originals and 100 cases. End-to-end setup was not stopwatch-instrumented, so no exact total setup-time claim is made. source/config/lock hashes and installed versions are in run.json.

Capacity-negative input deliberately violates the official single-op input/output capacity guarantee. The separate legal pressure input keeps each op within capacity and demonstrates spill. Reported memory peaks are Step3 local outputs, not reconstructed global physical addresses.

Not covered: cases008/044, all 100 cases, 2–5-core quality matrix, many seeds, multi-producer differential examples, backing/incarnation variations, priority-stage-only rejection distinct from the ordinary plan rejection, timeout/resource failure under large official graphs, formal equivalence, M1/M2 search, Linux/macOS. Control-path timeout/resource tests are not real official-graph stress tests.

## Reproduce and inspect

```powershell
uv sync --locked
uv run python -B scripts/a_materials.py --extract
uv run python -B -m unittest discover -s tests/q2 -p test_*.py -v
# Requires a separately authorized 12-call budget and a fresh output directory:
uv run python -B -m src.q2.stage_a --output results/a/q2-yuanzhifang/<fresh-run-id> --wall-seconds 1770
# Regenerate the report from saved evidence; does not evaluate any graph:
uv run python -B -m src.q2.report --run results/a/q2-yuanzhifang/stage-a-20260924-035625-retry1
```

Exact per-call commands are in evaluations/<name>/run.json. Artifacts retain original plan bytes and full traces; artifacts.json covers the original 89 evidence files, while delivery_manifest.json also covers this generated report and its generator receipt. Only input_plan filename is excluded from the final repeat comparison; the two plan byte hashes match.

Next recommendation: independently review these fixed files and mechanisms, then decide whether to authorize the separately budgeted three-case D/M1/M2 comparison. No further E0 calls are made by this delivery.
