# P1 general bridge E0 pilot runner plan

Prepared for the 2026-09-26 coordination decision. This is a one-cell admission request: **068/K5 only**. The second frozen candidate, 085/K5, remains available in the runner source for a separately admitted run but the current CLI rejects it; a future admitted run requires an explicit reviewed CLI change. It is excluded from this first window because its recorded baseline is already 4.675× and its compute-resource headroom is smaller. Case 068 is the lower baseline (2.759×) and adds a structurally distinct bridge pattern. Neither ratio predicts the candidate's E0 result.

The runner is `src/q1_benchmarks/p1_general_bridge_two_e0.py`. It verifies the candidate, graph, archive, official source/configuration, and E0 supervisor hashes before dispatch. It extracts the exact graph member from the frozen ZIP into a new run/cell directory, copies the fixed plan bytes there, and launches the unmodified official `multicore_cut_evaluate_problem_1.py` with explicit result, trace, and log paths. The saved plan is used directly; there is no solver or Task construction path.

| Cell | Candidate SHA-256 | Graph SHA-256 | Maximum calls in first window |
| --- | --- | --- | ---: |
| 068/K5 | `0b4b64cba1e0000220337bcee60cd94e206526f949ec3ba04cad02fb4d8b2720` | `dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d` | E0 1 |
| 085/K5 (deferred) | `ba9be0e9bea3ea3f23c0eda28c7fa6ce1d5787fa52624da8e54a9c61120cc054` | `b63169e9cd0f21dc2da6617e7138472e95937465c703b7e4bf4dbc80125ed4f6` | E0 0 |

Frozen shared inputs: case archive `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`; official config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`; official E0 entrypoint `2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f`; official code aggregate `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`; process supervisor helper `08f86b1e95dbed9f0c3d82c4005cbf85d81e0164493fc4fc51542ced9035011c`.

The first window is bounded to one worker, at most 1 E0, zero solver calls, zero **standalone** Task-compilation calls, zero E1/E2, and zero retries. Official E0 itself compiles and schedules Tasks internally; that work is included in the E0 call. E0 timeout is 120 seconds; whole-run wall cap is 300 seconds. Any source/hash mismatch, dispatch/cleanup failure, invalid result, timeout, or other first-cell failure stops the run. Its attempt and any logs remain in that unique run directory; no rerun may reuse the directory. The runner defaults to no action unless `--preflight` or `--execute` is selected, and `--case` is mandatory so a two-cell batch cannot start implicitly.

After coordinator admits this first window, the intended command is:

```sh
uv run --locked python -B -m src.q1_benchmarks.p1_general_bridge_two_e0 --execute --case 068 --run-id 20260926TXXXXZ-068-k5
```

The run ID must be replaced with a new unique value. The command is documented for later admission only; it was **not run** during preparation. Safe byte/CLI preflight is `uv run --locked python -B -m src.q1_benchmarks.p1_general_bridge_two_e0 --preflight --case 068` and reports zero calls. The project requires locked Python 3.12; invoking the host `python3` may select 3.14. No official E0, standalone Task compiler, E1, or E2 was invoked in this preparation; the candidate plan was produced and structurally validated earlier.

Outputs are confined to `results/a/p1-general-bridge-probe-20260926/runs/<run-id>/<case>-k5/`. Existing source candidates and earlier runs are never overwritten. Each attempted cell retains `attempt.json`, graph/plan copies, process stdout/stderr, and any official result/trace/log created before failure. A successful result records Makespan, data movement, and artifact hashes; a failed or timed-out first cell leaves the next candidate unrun. This pilot is mechanism evidence only and is not a full-matrix result.
