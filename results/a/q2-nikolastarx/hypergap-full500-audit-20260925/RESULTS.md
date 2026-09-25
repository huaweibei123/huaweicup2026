# Frozen P2 hypergap: full 500-cell result

One frozen algorithm covers all 100 official graphs × 1–5 cores, with one result per coordinate. The constructor uses the graph/configuration/core count and a fixed rule with at most three native E2-scored complete plans; it does not read historical case winners. Every selected plan received an independent unmodified official E0 evaluation.

| Cores | Previous full100 mean | Current full100 mean | Mean increase | External screenshot | Relative to screenshot |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.108597 | 1.206139 | +8.80% | — | — |
| 2 | 2.050483 | 2.316727 | +12.98% | 2.26 | +2.51% |
| 3 | 2.815665 | 3.235566 | +14.91% | 3.18 | +1.75% |
| 4 | 3.476781 | 3.971149 | +14.22% | 3.96 | +0.28% |
| 5 | 4.014094 | 4.549757 | +13.34% | 4.53 | +0.44% |

The comparison is the arithmetic mean of each graph's fixed official single-core baseline Makespan divided by its selected P2 Makespan. The screenshot is a user-supplied external report, not a reproduced peer run. Its unrounded values, input/configuration identities and implementation have not been verified. The current values slightly exceed the displayed numbers; 4- and 5-core margins are under 0.5%, so this is not evidence of a substantial lead.

## Paired quality and cost

- Against the previous complete frozen algorithm: **268 improvements, 232 ties, zero regressions** over 500 graph/core cells; 69 of 100 graphs improve for at least one core.
- New K1–5 win/tie/loss counts: 59/41/0, 64/36/0, 54/46/0, 49/51/0, 42/58/0.
- Per-cell solver process wall, including cold startup, construction, online E2 scoring and plan output: mean **4.029 s**, nearest-rank p95 **18.841 s**, max **40.187 s**. This was a single-worker run on the shared macOS host; no controlled hardware speedup over the previous four-worker batch is claimed.
- Independent final E0 wall is separate: mean **1.410 s**, p95 **6.592 s**, max **13.980 s**. Whole batch wall including runner overhead and final checks was **2797.986 s (46.63 min)**.
- Actual counts: 500 solver starts, 1131 native E2 returns, 500 independent E0 starts; zero fallback or unresolved in-flight calls. Runner completed with exit code 0.
- The existing compute-only necessary bound certifies 81/62/32/33/23 cases at K1–5 within 5% of optimum under its documented assumptions; zero cells meet that lower bound exactly. The loose K5 mean B/LB ceiling 6.108 is not an achievable target or a prediction. We have not proved global optimality.

## Evidence and publication

- Solver: `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`; runner: `ff47cbca4a953602dec7e4b959bbb10a016eca9a`.
- Manifest SHA-256: `deea62c5e9f703e2558baf605a0b6ca5e5f35c4b2d85e57ac2a6eaaafd570501`.
- Original terminal runtime summary SHA-256: `25bce048b00444619eb9aa3c9e6e5cf5ec9d838d55be437491abfbb37f5682c6`.
- Shareable redacted terminal summary SHA-256: `083c3f5b603cb61dd8b132718b6437b35c7706ff3aa165bdcdd490617547a2f2`. Personal path strings were redacted and archive provenance added; these are intentionally different byte identities.
- [Audit report](report.json), [terminal summary derivative](completed-summary.json), [audit program](audit.py). The audit checks all 500 source/plan/result/receipt identities, old official denominators, call totals and bound domains without rerunning any solver or evaluator.
- Ten immutable feed groups were pushed through `3fc333c3d947a1accbf22344c35df1b230d6daa9`. Website owner readback confirms central 500 accepted/eligible/ok, unique 100×5 coverage, `complete=true`, `full_complete=true`, no missing cases and K5 mean `4.549756996698352`. Website admission and this independent audit are separate checks.

## Next falsifiable improvement

The new construction is useful but does not establish that all remaining gap is avoidable. Existing E0 traces for 005/009 show hundreds of cross-core transfers with the fixed 500-cycle release delay and zero spill; 015 has no cross-core transfer but has substantial per-Pipe imbalance. A byte-only cut objective cannot capture both mechanisms.

The prepared latency-weighted placement prototype charges transfer startup as well as bytes, then retimes the selected ownership. Its fixed three-cell pilot is not yet run: at most three native E2 and three independent E0 calls, one worker, 360 seconds total, zero retries, subject to the shared resource window. Summed isolated transfer delay is only a heuristic, not a Makespan bound. Any improvement must pass native/E0 agreement, then a newly frozen full500 run before becoming a new full score. No current-case historical winner is injected into construction.
