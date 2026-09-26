# First three complete submissions

Existing P1/002/k2, P2/001/k5 and P3/001/k2 results requested in Issue15#5814852660. No new solver/evaluator calls, retries or altered official outputs.

Feed: `board-feed-20260924T132504.494191Z-c255fefc63ad-001.json`, SHA256 `345894b2d1b4bd69a1e55c6d0b0f8d491a86ecd4056316193fdeb794884bcaad`. Capture 13:25:03.206771–13:25:04.486682 UTC, non-atomic. Original attempt/run IDs retained; P1 preflight revision 2→3, other two revision 1→2. Makespan cycles: P1 157602, P2 47502, P3 116868.

Plan, complete result and original cell receipts are referenced by exact stored-byte SHA256 in this same data commit. P3 retains official `scene=B, problem=3, cache_mode=read_only` and its original same-plan/same-core P2 pair. Two local official singlecore results support the ratios. Local 14 baseline timeouts elsewhere remain unchanged.

The receiver's unmodified `b0937de5b97cb2e85fda68d702c8076457993588` validator was run from an external fixed source snapshot with this repository as cwd:

```text
python -X utf8 -B <fixed-board-checkout>/src/benchmark_board/protocol.py results/a/p123-multicore-20260924/submissions/20260924-first3/board-feed-20260924T132504.494191Z-c255fefc63ad-001.json --submission
```

Observed exit 0: valid/submission true, 3 records, 3 eligible, no reported_or_failed. This is format/original-byte admission checking, not independent scoring or captain acceptance. On this Windows machine omitting `-X utf8` first failed with a GBK decode error in the unchanged validator; UTF-8 mode resolved it without changing data or validator. Current delivery prose follows c4ec05fd34edfcf144434fcdc182b30b4a82caf8; its schema/validator requirements are unchanged.

Read-only publication audit parsed and scanned all 13 selected JSON/gzip artifacts (263969 stored bytes, 2056345 decoded bytes); no privacy or integrity findings. Report `publication-audit.json` SHA256 `65dee4edcb748a58fc1b0515aa3699d296ffa1bb0b5a404976c49d5cd25c9990`. It does not scan all candidate logs or prove global algorithm/evaluator equivalence. Additional source identity evidence is linked by the feed.

The rest of the original 1300-cell batch is still running. This is a first delivery, not the final 100-case table.
