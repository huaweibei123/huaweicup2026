# 014/K1 E2 rank-index preparation differential: one admitted CPU attempt

This is the complete result of the single CPU Standard attempt admitted by the
total scheduler on 2026-09-25. It reused the old 014/K1 graph, selected plan,
config and prepared object from `e4f7b13e4af04914a1264a650831a3959f14a373`.
It did **one new preparation**, no old rerun, no E0 evaluation or native score,
and no retry. The admission and exact command are in
`docs/a/E2_RANK_014_DIFFERENTIAL.md`; the controller HEAD was
`8821876abde637bc1b0841326dc4b5e665ba7baa` (draft PR #198). Its capsule
SHA-256 was `9a41bc000814f180d99433d8cb5cf645dc134c564c98ad19d63fcfcb5648a3af`.

## Result and evidence

| Check | Observed result |
| --- | --- |
| Full prepared-object pickle bytes | Equal, 28,399,387 bytes; old/new SHA-256 `4c8569591c245a8c14b290368fc694ecacb9690159ba2ef550a8b0a754787af7` |
| Recursive field/value/order comparison | Equal; `first_difference=null` |
| Operations packed | 58,083, same as old snapshot |
| New runner | `completed`, exit 0; outer child 24.753 s, internal runner 24.287 s, build 13.959 s, full differential check 3.741 s |
| Setup | `uv sync --locked` 3.012 s, separately reported |
| Resource | Peak *sampled* process-tree RSS 1,127,075,840 bytes; no RSS limit hit; one worker |
| VM | T0 `2026-09-25T04:36:56.661384Z`; stop requested `04:37:47.378062Z`; host finished `04:37:50.134349Z` |
| Stop proof | `colab stop` exit 0; `colab sessions` exit 0 and named session absent; later fresh OAuth readback again said no active sessions |

`result.zip` (SHA-256
`d0578bbe0c6c965206d316b39c6e08a6e102adf2331f8966e10ef54f1114f630`)
contains `cell-receipt.json`, `new/report.json`, the complete new
`new/prepared.pickle`, `runner.log`, and `setup.log`.
`host-receipt.json` is the controller's original receipt; `logs/` preserves
new/upload/exec/download/stop/readback and watchdog logs, plus an independent
post-stop session readback. The source guard forbade E0 evaluation and native
library load/replay; the 0 figures in receipts are planned limits, not an
independent external syscall count. No simulator performance result was
produced in this attempt.

The old 52.521-second preparation used `cProfile`, so it is **not** a matched
unprofiled timing baseline. This attempt proves equivalence of the prepared
object for one graph and one selected plan, not an E2 speedup ratio, all-case
correctness, or a better official Makespan.
