# R7 shared-input band, 044/K5: one official E0 result

The frozen plan `8eecfa3411b660b7cbffc8951ee7129df2ebb49745128243bbd6e1a3f9b90716` passed one authorized official P1 E0 on the official graph `9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e` with the frozen config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`. The official evaluator SHA-256 was `2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f`. The source commit before scoring was `21506e720d81a886e8564a2756ee0d43fe9cc9e5`.

| Fixed plan | Makespan (cycles) | Scheduled COPY (bytes) | Spill-added COPY (bytes) |
| --- | ---: | ---: | ---: |
| Unified full500 baseline, `originals/prior-result.json.gz` below | 64,624 | 2,026,944 | 0 |
| R7 shared-input candidate, one fresh E0 | 58,450 | 1,712,000 | 0 |

The single-cell Makespan fell by 6,174 cycles (9.5537%); scheduled COPY fell by 314,944 bytes (15.5379%). The baseline result is `results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500/cells/044-k5/originals/prior-result.json.gz`, compressed SHA-256 `2c0408591dd5db062dc0dcf2c3a5ecbc11ad4787a531e5e7b48026353508f8f4`, with its plan in the same directory. That baseline belongs to the fixed 500-cell unified checkpoint; its official E0 result was reused only because the plan/graph/config/evaluator identity matched the earlier original. The R7 result here is a fresh E0.

The coordinator's one-cell admission was `output/handoffs/resource-window-20260925/P1_R7_044_K5_ADMISSION_20260926.json`, SHA-256 `1d3c27558a127630387638a00329acf41cd38434b270223308ca12ff0920b9e0`. Execution started at `2026-09-25T19:01:15.157Z`, finished at `19:01:15.288Z`; batch wall was 0.1315 seconds. Actual calls: solver 0, standalone Task compiler 0, official E0 1 (including its internal Task compilation), E1 0, E2 0, retry 0. The supervised child exited 0, and cleanup was confirmed. All original inputs, stdout, stderr, official result, trace, and official log are under `runs/r7-044k5-20260925T1901Z/` with hashes in `044-k5/attempt.json`.

Key artifact SHA-256: official result `cf9ba2384d2896c55ca930689f68c43ef139bf7a06274cb2cb52d64d9ebd705b`; trace `fbbb11154eec0f5cd19253b5c73f06c2be4bfad51bf54f1f4fa92f7bda14b212`; official log `d709bbe93a26ff234c95c359da96c285cbff2f4d652e25253cfde6ef1f1d456d`.

This is a mechanism result on **one graph and one core count**, not a unified algorithm benchmark. The prototype's selection rule has not been integrated into the fixed full500 solver, and no other E0 budget follows from this result. The static construction took 0.249 seconds on this case but its current signature scan is not near-linear in graph size; the end-to-end time of a future unified solver is unmeasured.
