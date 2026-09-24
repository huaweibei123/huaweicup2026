# Stage L: shared-input packet pipeline

1. **Owner and scope:** @yuanzhifang30-sudo, parent session
   `yuanzhifang30-sudo/s-bdf7e1f4203b4ffda133950db055bd66`, continued P1 scope
   on `codex/q1-research-yuanzhifang-20260924`. Model/constructor is
   `src/q1_yuanzhifang/shared_packet_model.py`; do not edit the captain solver
   or the separately frozen Stage K solver and benchmark.
2. **Goal:** one graph-derived packet-pipeline candidate for homogeneous
   repeated jobs with shared same-position inputs. Prioritize official E0
   Makespan, report added DDR bytes and full cold solver wall separately.
   The model is not an official score, a timing bound or a global optimizer.
3. **Inputs:** unchanged original graph/config/E0 source in the frozen official
   source manifest; initial mechanistic trial is 044 at three and four cores.
   The constructor never reads a case ID, previous plan/score, or saved model
   output. Input semantics and graph-derived cuts are recomputed within timing.
4. **Outputs:** exact two-field submission JSON, model diagnostics, all raw E0
   result/trace/logs, process events/receipts and a standard board feed. Keep
   unsupported or failed cells explicit. Reuse the matched official single-core
   baseline from fixed `6fcec11ccc472a1a652b21feb6fccf85a4555598`.
5. **Budget and acceptance:** prepare a separate frozen runner before START.
   At most 2 cold solver and 2 external E0 attempts, zero E1/E2/retries;
   one cell worker; per-solver 120s, per-E0 90s, whole batch 300s;
   available RAM at least 1 GiB at startup and before each cell; each owned solver/E0
   Job has a 512 MiB aggregate committed-memory hard limit. Use owned Windows Job cleanup and
   the same source/input identity checks as recent I/J. Coordinate the shared
   machine window before starting. A 5–10 minute solver time is a suggestion,
   not a required run length or a hard 600-second validity rule.
6. **Status/deadline:** source preparation 2026-09-25 Asia/Shanghai; two small
   synthetic tests plus an excluded-COPY-bridge regression pass (three total:
   augmented-DAG/capacity, mismatched structure and hidden dependencies).
   044-model.json is a read-only metadata run: zero real plan construction,
   zero official Task compilation or scoring. No trial START yet. Freeze and
   validate actual E0 evidence before claiming quality gains.

The interval minimax DP evaluates metadata over at most 32 packet counts and
five active core counts; it emits only one plan after selecting the model
winner. This is a structural capacity/load/gate construction, not an online
brute-force loop over official scores. The current straightforward interval
builder is conservatively O(J L^3 + J K L^2); J<=32, L<=256. Its cost remains
inside solver wall and is a target for later optimization if the candidate
proves useful. The model and DP limitations are detailed in the result README.

## Two-cell runner preparation

- Frozen constructor: `5c64b4057cb9b2f2af5426bd1efdd579b9df5559`, including the explicit excluded-COPY-bridge guard. `d3fd2a344` is superseded for this trial; its 044 metadata happened to match but does not prove E0 quality.
- New branch `codex/q1-shared-pipeline-20260925` writes only `benchmark_l.py`, `export_l.py`, `job_l.py` and this record. `job_l.py` adapts `f3e548f1915ce895e1f785219420fc747777ceb0:src/q1_yuanzhifang/job_j.py` to execute the solver through Python module semantics after the Job gate; owned-process cleanup is retained.
- Prepare-only command: `python -m src.q1_yuanzhifang.benchmark_l --graphs GRAPH_DIR --preflight`. Actual launch also requires `--start-token STAGE-L-MEM512-20260925-START --producer-session ACTUAL_SESSION`; new run output defaults to `results/a/q1-yuanzhifang-stage-l/stage-l-mem512-20260925/run` and can be passed via `--output`.
- Fixed limits: exactly the two intended cells `044/k3`, `044/k4`; at most 2 cold solver attempts and 2 independent unchanged E0 attempts; 0 E1/E2/retries; 1 worker; 120/90/300-second solver/E0/batch caps. At startup and before each cell, require ≥1 GiB available RAM. Solver and E0 each run inside an owned Job with a hard 512 MiB aggregate committed-memory limit; Job limit setup failure, excess memory, or inadequate available RAM stops without retries or relaxed bounds. The CLI uses `--output DIAG --plan PLAN`; all model DP and plan construction are inside the new cold solver wall. No historical result enters model selection.
- Export command after a real run: `python -m src.q1_yuanzhifang.export_l --run-dir RUN_DIR --feed FEED.json`. The exporter checks original plan/diagnostics/result/trace/log bytes and both matched single-core baseline originals from `6fcec11ccc472a1a652b21feb6fccf85a4555598`. Failed or unevaluated cells remain non-success without Makespan.
- The superseded `c34e03999e44a8e885cdc0860496b5204c271c39` preparation was never STARTed: 0 cold solver, 0 Task compiler, 0 E0/E1. The frozen `044-model-copy-guard.json` has no alternatives with `stages <= 2`, so k2 would be `Unsupported` and is removed before real scoring. This is a static applicability guard, not selection using E0 or historical results. The eligible k3 metadata has cuts `[0,51,66,124]`, packets `[4,4,3]`, proxy 55435; k4 has cuts `[0,28,60,86,124]`, packets `[4,4,3]`, proxy 49494. Both proxies are neither E0 results nor promised improvements.

The superseded `a6e48df8884d26700c77141f16a668888334d34c` no-memory-cap runner was also never STARTed. The new 512 MiB Job cap is stricter on the actual small 044 process than that runner, while the 1 GiB startup/cell RAM gate reflects current machine availability. This change does not alter the frozen constructor `5c64b4057cb9b2f2af5426bd1efdd579b9df5559`, experiment cells, score/call/time budget, or prior 0-call records. No busy wait or automatic retry is permitted.
