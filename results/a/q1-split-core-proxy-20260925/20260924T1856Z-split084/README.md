# P1 split-core proxy: one negative mechanism result

Case 084/k5 produced official E0 Makespan **426656 cycles**. Solver wall was **0.29253162498935126 s**; separate external E0 wall was **1.5332963750115596 s**. It used one solver and one E0 call, with zero E1/E2 calls and retries. Cleanup was confirmed. Against the existing full-return mechanism on the same case, it reduced extra DDR bytes from 9925632 to 7252992 while increasing Makespan from 399121 to 426656. This is a one-cell mechanism probe, not the unified 500-cell run or v2 three-cell smoke.

The feed is `board-feed-20260924T1856Z-split084.json`. The official singlecore denominator **2507412 cycles** was copied from the same-identity frozen E0 original at commit `6fcec11ccc472a1a652b21feb6fccf85a4555598`; no baseline rerun occurred. Plan bytes are unchanged; result, trace, and graph gzip files decompress to the exact original bytes. Original and stored hashes are in `export-receipt.json`. The raw run contains local interpreter paths; `run-derived.json` replaces those two paths and records the raw receipt SHA. Other raw process evidence remains only in the local output directory, not Git. Export added zero scoring calls.

The board precheck validates schema and committed bytes only. No independent rerun or full-algorithm acceptance is claimed.

Read-only trace analysis is reproducible with `python3 analyze_trace.py` from
this directory; `trace-comparison.json` records the derived values and SHA-256
of both decompressed source artifacts. It performs no solver/evaluator calls.
The split plan's DDR busy union is 346291 cycles, versus 390951 for full-return.
Time outside those DDR intervals grows from 8170 to 80365 cycles; this is not
CPU-idle time. The two whole-chain cores finish at 350981, while the three cut
cores finish at 426656/425681/425681. Total original M and V compute work is
unchanged. These observations expose the limitation of selecting by aggregate
work/service alone; they do not isolate the causal effect of every scheduling
change or certify a better allocation. No follow-up parameter sweep is run.
