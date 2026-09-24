# P1 capacity-return case 084 mechanism probe

One real case 084/k5 structural probe: official E0 Makespan **399121 cycles**; solver end-to-end wall **0.18660849999287166 s**; separate external E0 wall **1.4718682500242721 s**. Calls: one solver, one E0, zero E1/E2/retries. The plan uses a graph-derived five-chain packet and cuts all 1077 recognized chains. This is a single mechanism observation, not a unified solver batch or a 100-graph result; no quality or cost certificate was established.

The standard feed is `board-feed-20260924T1830Z-capacity084.json`. It records source implementation and runner commit `e566dd5ce6a1737880ca88d35964bfd846bc4512`. The official singlecore denominator, **2507412 cycles**, is the same-identity frozen E0 case 084 result copied byte for byte from `6fcec11ccc472a1a652b21feb6fccf85a4555598`. It is not an optimized k1 plan. Feed export performed zero scoring calls.

`plan.json` preserves exact bytes. `result.json.gz`, `trace.json.gz`, and `graph.json.gz` decompress to the exact local original bytes; original SHA-256 values and compressed artifact hashes are in `export-receipt.json`. `run-derived.json` differs from the original local `output/p1-capacity-return/20260924T1830Z-capacity084/run.json` only by redaction of two absolute interpreter paths and an added derivation field. The raw run SHA-256 is recorded. Raw process receipts and other logs remain only in the local output directory and are not claimed as Git archived. The feed's result, plan, trace, and derived run references are in this directory.

Board precheck verifies schema and available bytes. It does not independently rerun E0 or certify full-matrix algorithm quality. Central admission and scientific acceptance are separate.
