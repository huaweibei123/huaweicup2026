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
   source manifest; initial mechanistic trial is 044 at two and four cores.
   The constructor never reads a case ID, previous plan/score, or saved model
   output. Input semantics and graph-derived cuts are recomputed within timing.
4. **Outputs:** exact two-field submission JSON, model diagnostics, all raw E0
   result/trace/logs, process events/receipts and a standard board feed. Keep
   unsupported or failed cells explicit. Reuse the matched official single-core
   baseline from fixed `6fcec11ccc472a1a652b21feb6fccf85a4555598`.
5. **Budget and acceptance:** prepare a separate frozen runner before START.
   At most 2 cold solver and 2 external E0 attempts, zero E1/E2/retries;
   one cell worker; per-solver 120s, per-E0 90s, whole batch 300s;
   available RAM at least 2 GiB at startup. Use owned Windows Job cleanup and
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
