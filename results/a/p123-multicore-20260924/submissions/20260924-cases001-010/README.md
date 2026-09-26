# Original results for cases 001–010

This volume exports 130 existing terminal solver receipts: P1/P2 cores 2–5 and P3 cores 1–5 for each of ten cases. There are 126 successful results and four failed P1 attempts (003, cores 2–5). Failures remain failed with null final Makespan. No solver or evaluator was invoked for this export.

Feed: `board-feed-20260924T133700.533615Z-cf4c0ea0d79a-001.json`; stored-byte SHA256 `089c96d0e6bda3fac77ef90b1772bac2f791289f6531d414d1bf59718e4db37e`. Capture was 2026-09-24 13:36:54.665464–13:37:00.070462 UTC and was not atomic. Original attempt/run identities are retained, with revisions incremented from the previous partial feed and first-three package.

Each successful record references the original final plan, complete official result and cell receipt. P3 retains official scene B/read_only and its same-plan, same-core P2 result. References are included in this data commit. Additional environment evidence records CPU/RAM observed during the batch and archived thread configuration; it is not a historical per-cell resource measurement. Unknown GPU/RSS remain null.

The unchanged validator at `b0937de5b97cb2e85fda68d702c8076457993588` was run from this repository root using:

```text
python -X utf8 -B <fixed-board-checkout>/src/benchmark_board/protocol.py results/a/p123-multicore-20260924/submissions/20260924-cases001-010/board-feed-20260924T133700.533615Z-cf4c0ea0d79a-001.json --submission
```

Observed exit 0: valid true, 130 records, 126 eligible. The four failed P1 attempts are not eligible. `precheck.json` records this observed summary. UTF-8 mode is needed by the unchanged validator on this Windows installation. Protocol prose follows `c4ec05fd34edfcf144434fcdc182b30b4a82caf8`; schema and admission requirements remain unchanged.

The exact raw reference hashes were matched to the completed read-only publication audit (SHA256 `55a40e2ba5b0541a577b5ba9e93c11b8a177a55d1fba0d42230fe491c6cd31d0`). That audit parsed and privacy-scanned JSON/gzip originals; it reported zero findings. `preparation.json` records the selected files and byte hashes checked again at staging. These checks do not constitute independent algorithm reproduction or scientific acceptance.

The original 1300-cell batch is still running. This volume is not the final 100-case comparison. The original 14 local singlecore timeouts elsewhere remain intact; the captain's separately verified shared denominators are not substituted into these historical receipts.
