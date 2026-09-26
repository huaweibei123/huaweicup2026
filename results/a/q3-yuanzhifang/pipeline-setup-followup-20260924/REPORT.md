# Cold-setup DP followup: a capacity counterexample

Fixed algorithm f14e8f0ae38033e83d9f497301595b7568a55cb6; runner 27e04f55dac9de926af217e800aeab81ca739919. One public 044/k4 graph, Windows Ryzen 5 5600H, shared with P2, one low-priority worker. Luna medium executed the frozen runner; root exported the completed artifacts without further evaluation. Token instructions were soft budgets, not tool-enforced hard caps; actual model token usage is unavailable.

Actual T0 2026-09-24T18:39:53.951791Z, T1 18:40:09.618067Z, batch 15.665724 s. All three dispatch checks passed; minimum available physical RAM 3,920,994,304 B. Actual calls: 1 cold solver, 2 external E0, 0 retry/E1/E2. The earlier 92f84354 resource-stop attempt remains separate, with zero solver/E0 calls.

|Metric|New setup DP|Historical compute-only pipeline|
|---|---:|---:|
|P2 Makespan / cycles|64211|40927|
|P3 Makespan / cycles|41738|40927|
|Extra DDR / bytes, both problems|1731840|135168|
|Spill DDR / bytes, both problems|1622016|0|
|P3 byte hit rate|0.6167698915834174|0|
|Cold solver / seconds|0.6142877000020235|0.6956272|

External E0 times were 0.7841032 s for P2 and 0.9259748 s for P3. The cold times are different shared-host, single observations, not a statistically supported runtime improvement. Historical complete control artifacts are fixed at e6b5500dcbf3818034804168ee79d0f65c16706b; they were not rerun. New plan SHA-256 is 7fdad2c6798f57480c2261084e012175a113772836a87bdfe771c4e26be47d13. It differs in bytes and parsed fields; no historical E0 reuse occurred.

The exact abstract optimum has cuts [0,41,70,98,124], compute cycles [2822,1709,1577,1564], first-job setup [1232,11063,3112,123], modeled completion 38849, and shared input bytes [73440,663552,186368,7040]. Compared with the old cuts [0,28,58,91,124], 352 of 1364 compute operations change cores. All 1364 are still covered once by singleton subgraphs.

The second stage's shared-input set exceeds the official 524288 B L1 capacity. Measured peak L1 occupancy [79584,516992,188160,15744] B stays legal because the evaluator spills; it is not evidence that the input working set fits. Measured spill is 1622016 B. Cache hit bytes are also 1622016 B, miss bytes 1007840 B, total accesses 2629856 B; this numerical equality is an observation, not a proved one-to-one causal accounting without trace analysis.

P3 is worse by 811 cycles (1.98158%) and P2 by 23284 cycles (56.89154%). Higher byte hit rate and smaller abstract objective do not imply a better official plan. Do not promote this candidate. The model theorem remains valid in its stated serial-stage, first-job-only setup abstraction; real capacity and repeated reloads are outside that theorem. Next useful hypothesis is a capacity-aware partition or bounded wave order, not another unconstrained setup sweep.

Both positive and negative raw outputs, full result/trace/log, call ledger, environment and byte hashes are retained. This is one development cell, not a unified full500 result or independent scientific acceptance.
