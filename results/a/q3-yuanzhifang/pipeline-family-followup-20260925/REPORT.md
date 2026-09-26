# Six shared-weight chains: measured gains and regressions

Frozen candidate 6bae8dfa317bc71226068344b59dd65d2612c32b; followup runner 84ec8decc1e8fdb8a5a2b176e60981d272f32ac0. Windows Ryzen 5 5600H, at most two low-priority workers, shared P2 host with recent P1 activity conservatively included (P1 current activity unknown). Luna medium ran the script; soft token instructions are not an enforced hard cap and actual model usage is unavailable.

T0 2026-09-24T19:17:58.410233Z, T1 19:18:52.556133Z, wall 54.146888 s. New calls: 4 cold + 8 E0; zero retries/E1/E2. Separately reused 044/046's 2 cold plans and 2 complete P2 results from ba3f848492b213d5f3ec93cf12b0da0cc79eea8f after full commit/command/identity/compressed/raw-byte verification. These are not new cold or E0 calls. Together the two family batches have 6 cold + 10 E0; only 092 P2/P3 remain missing.

|case / k5|P2 cycles|P3 cycles|P3 extra bytes|P3 spill bytes|P3 byte hit rate|captain V2 P3|
|---|---:|---:|---:|---:|---:|---:|
|044|63413 (reused)|41205|1751296|1585152|0.604753940252225|85406|
|046|96034 (reused)|83050|1538048|1087488|0.4630545968647345|88200|
|067|15686331|15686331|210882560|202303488|0|13422709|
|073|3337352|3337352|110682624|109504512|0|2627067|
|083|295101|241719|6501376|4755456|0.5519236821215694|245505|
|092|not run|not run|unknown|unknown|unknown|1138015|

Captain V2 comparisons are the pinned 2d5459fa unified500 records read through the member mirror, source d81a9e42084e1c3c1480d6927c4a2c590e65bdae. These are the earlier fixed comparator, not a claim about any newer expanded version. No captain raw trace was downloaded in that readback. Do not compare its Apple M5 Pro online-E0 wall time with this Windows construction-only cost.

New cold wall seconds: 067 2.0236332, 073 1.5089064, 083 2.0460203, 092 11.9372209. Reused historical cold: 044 0.8200638, 046 1.0080189. The slow 092 observation was on a shared, low-memory host; no repeat distribution or causal runtime conclusion is available. Per-E0 times are in the call ledger and CSV.

All six stages use common-input byte vectors [5472,86400,645120,186368,7040], except 067/073 where each entry is four times larger. Thus 044/046/083/092 have 930400 shared bytes in total, while 067/073 have 3721600. The latter exceeds both the configured shared cache and aggregate five-core L1 capacity; their actual cache hit rates are zero and the pipeline worsens Makespan. 044/046/083 improve relative to V2 despite some L1 spill. This supports a guarded router and further capacity/order research, not blanket promotion of all shared-chain pipelines or proof that the working-set size alone causes every difference.

092 completed its one cold plan. Its next dispatch check found 2001186816 B available RAM, below the fixed 2 GiB gate, so no P2/P3 child was started. Earlier successful dispatches had at least 2166272000 B; minimum free output disk was 20487192576 B. Keep that stopped receipt and plan; any next batch must reuse the verified plan and fill only two missing E0s under a separate budget.

The standard feed contains 8 new successful E0 records and one resource-stop record. Original failed validator receipts and their schema correction are retained. This remains partial structural-family development evidence, not a single unified100x5 result or independent acceptance.
