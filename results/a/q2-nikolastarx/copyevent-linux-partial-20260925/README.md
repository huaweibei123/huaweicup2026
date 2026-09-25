# P2 Linux full-grid attempt: stopped after 66 accepted cells

This is **not a complete algorithm score**. The previous c665 full500 remains the
formal complete result. This independent batch does not resume or replace it.

- Algorithm: `295ec9cf4351b77f5c6fffe8fbb23e8bc8d2f323`, COPY-event guarded route.
- Runner: `4b08468fd14a939ce259b0560e3ec27816f675a5`.
- Source/input capsule: SHA-256 `d3c4325e5111e8e71403dab8033f2c2f40bb0989cfd39ebb701109f1095e22aa`, 15,849,016 bytes. Reproducible with the committed packer; manifest retained here.
- E2: fixed 603b source set, Linux binary `77ece8929ddcc04e6087dd1c8fc02ee61e79f03b79499182b9f069122092ab3a`.
- CPU Standard DEFAULT Colab, two workers, locked Python 3.12 environment, no GPU.
- Limits: 500 coordinates; at most 4 native requests and 1 independent E0 per cell;
  180 seconds each solver/E0, 7200 seconds outer batch, 8 GiB sampled aggregate
  process-tree RSS, zero retry. These Linux timeout limits differ from Mac 60/60s.

Pure preparation/preflight started 01:44:28Z on 2026-09-25 and took 16.334 seconds;
it issued no evaluation calls. Actual dispatch was 01:47:21Z; terminal outer
receipt was 01:58:48Z, 686.957 seconds, exit 1, no surviving descendants.
Observed outer peak including observer was 1,899,839,488 bytes. The VM was stopped
and the server session listing subsequently showed only the separate P1 runtime.
The independent local 2.5-hour cleanup guard was released after that readback.

Of 67 started cells, 66 passed full selected-E2/independent-E0 equality, including
Makespan, cross-task traffic and all five movement fields. There were 207 E2
attempts, 206 native returns and 66 independent E0 calls. One request remains
unknown in the preserved ledger; confirmed E0 fallback is zero, possible fallback
is one. The other 433 coordinates were never dispatched. No retry or hot resume.

014/K2 reached its outer 180-second solver deadline during the fourth native
request. The first three returned after 31.24, 38.65 and 41.01 seconds; the fourth
had only about 24 seconds before the whole solver was killed. 014/K1 completed
in 164.04 seconds, with its three native requests taking 38.36, 44.05 and 42.84
seconds. Source verification took about 0.65 seconds. These receipts identify
repeated complete public E2 calls as a major wall-time cost, and the stored inner timing narrows it further: task preparation took 29.08–40.78
seconds per completed call, while native replay took only 0.004–0.028 seconds.
The outer-minus-inner cost was roughly 2–3 seconds. All six compilation cache
lookups missed; see `failure-timing.json`. A resident process alone therefore
does not address the dominant measured preparation cost. No evidence of
numeric disagreement occurred among completed selected-plan pairs.

`results.zip` is the downloaded 26,894,768-byte original (SHA-256
`03f8516b31cb229b7f2ea2bb4c812f0719b0ed0e889e5e9fbcfe4a00789f2c05`).
It contains complete plans, online ledgers, independent E0 results, traces,
process receipts, setup/build identity and terminal summary. Run `python3 audit.py`
in this directory for a read-only hash/source/call/metric audit. It deliberately
does not calculate a full-grid average. The finished subset has biased coverage
and cannot establish full-grid wall-time or quality performance.

The baseline denominators are the same frozen official **singlecore CLI** results
used by the shared board; that CLI labels results scene A. They are report-only,
not P2 algorithm inputs. Every new final result is scene B at the requested cores.

Before this batch, three fixed stage-major plans were independently evaluated
under a separate 3-E0 budget; their failure evidence is in the sibling
`template-stage-pilot-20260925` directory and never affects this frozen solver.

No new full500 is started merely by increasing timeouts. Next qualification is
to explain and reduce repeated preparation cost or use a verified suitable host,
then freeze a new complete batch with a declared resource budget.
