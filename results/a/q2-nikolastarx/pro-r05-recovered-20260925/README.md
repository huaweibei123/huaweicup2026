# R05 rejected raw plan: artifact recovery

`recovered-raw-plan.json.gz` is the discarded **raw candidate** from the frozen 003/K2 `run-v2` constructor, not a new run or an evaluated result. The constructor returned its seed because its static proxy increased (`230838 → 241374`). No E0/E2 was run here; this recovered candidate has no official Makespan.

Recovery used `run-v2/result.json` (`rebuilt_owner`, `rebuilt_starts`), the original `static-003-k2/seed-witness.json.gz` chains and seed plan mapping, and the read-only case003 graph. SHA-256 checks compare the **uncompressed** witness and seed plan bytes with `run-v2` metadata; the graph and `ready_exchange.py` hashes also match. The frozen adapter at commit `1ff472bc60db45069c588280bef52826ed1e0385` has SHA-256 `620104c39686c6d20a5e01e9c494f88d6071af28fd8bd6a92b75c5cf2e7e94cc`; its packet splitting is the chain's maximal same-Pipe runs. `receipt.json` records all input/output hashes and checks.

The old `rebuild` first places ready packets in earliest nonoverlapping same-core/same-Pipe gaps with positive durations. Every start is either a tight dependency release or the end of a blocking same-Pipe reservation. Future reservations cannot remove that tight predecessor, so the final fixed lag + Pipe FIFO DAG has exactly those earliest starts. Consequently the stored `rebuilt_starts` equal the original constructive starts, and sorting eligible ops by `(start, op_id)` within `rebuilt_owner[packet]` reproduces the raw core rows. This proof requires unchanged frozen packet IDs, chains, lags, durations and owner semantics; it is not an official performance claim.

Run from the repository root:

```sh
python3 scripts/q2_recover_r05_plan.py \
  --graph data/raw/a/official/data/case_003.json \
  --config data/raw/a/official/data/config.txt
```

The script checked all 11,123 packet IDs and 13,455 eligible op IDs, official plan structure, and independent pre-Step2 mandatory copy bytes (`5,207,554`, matching metadata). It did not call `rebuild`, matching, Step2, or an evaluator.
