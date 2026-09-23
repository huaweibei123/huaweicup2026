# Q2 fixed-plan A/B mechanism check

Only original case044 parent/child plans were evaluated by unmodified P2 E0. No plan construction or search occurred.
044 uses four configured cores but all 1364 operations are on core0. Original plan bytes and mapping order are preserved.

| Plan | Status | P2 cycles | Added COPY bytes | Spill bytes | CLI wall s |
|---|---|---:|---:|---:|---:|
| parent | ok | 100404 | 1416192 | 1416192 | 0.5470000000004802 |
| child | ok | 108066 | 1784064 | 1784064 | 0.6090000000003783 |

Original A evidence for these exact plans: 116227 -> 126094 cycles; source 13d6b0298f944d3c0bfdf3172191f1ac25a50379.
Original Pro case008 B evidence is reused, not rerun: components 123060 -> word 63768, unchanged per-op cores, differing mapping insertion order; source 3a4505d4101e23d54580d15560da3820e02d05da.
Cross-scene absolute values do not rank algorithms. These compound plan changes do not isolate one causal variable. No full-domain, independent Pro rerun, construction speed or optimality claim.
Observed timing comparison: {"scope": "Observed event timing only; no fixed-duration causal counterfactual", "memory_edge_evidence": "Official step3 reports dependency counts; full adjacency is not independently reconstructed", "idle_evidence": "Per-pipe union of occupied intervals; unoccupied horizon is not attributed to one cause", "same_ordered_op_events_ignoring_subgraph_label": false, "same_step3_summary": false, "makespan_delta": 7662}. Per-core occupied/idle intervals, memory peaks and Step3 dependency counts are in calls.json. Idle totals are not a causal FIFO-wait decomposition.

Task fields: goal=fixed-plan mechanism observation; input=protocol identities; output=full evidence/ledger/metrics; limits=2 calls, 30s each, one worker, 180s outer; acceptance=identities and complete evidence with failures retained; milestone=bounded mechanism checkpoint, not final algorithm acceptance.

Timing: recorded preparation and Git freeze precede T0 and are reported separately. T0 includes job startup, official CLI, output reading, archive/report and delivery. At 120s no new evaluator starts. Existing-plan evaluation is not solver construction wall time.
controller.json, run.json and publication.json separate local measurement, packaging and publication endpoints. Missing publication receipt means delivery is not confirmed within the window.

Full original outputs are in evidence.zip; controller logs remain alongside. No E1/E2/P3, no retries. Memory supervision is a sampled 4 GiB stop threshold, not a hard allocation guarantee.

New measurement command: `python -X utf8 -B -m src.q2.mechanism_measure run --folder results/a/q2-yuanzhifang/ab-mechanism-20260924`.
Inputs/source freeze and existing failure evidence must not be overwritten for a rerun. A fresh run requires new scheduling.

## Observed mechanism and limits

Both original plans are valid in B. The merge changes B makespan from 100404 to 108066 cycles (+7662, approximately 7.63%). Both have zero partition-added COPY because every operation remains on core0. Spill COPY increases from 1416192 to 1784064 bytes (+367872). Thus A's boundary-byte saving does not transfer into B; the same plan edit changes the core-internal compilation/order and its spill outcome. This is an observation, not a causal decomposition.

Core0 PIPE_M occupied time stays 74404 cycles, while its unoccupied global-horizon time grows from 26000 to 33662. PIPE_V occupied time stays 9988; MTE2 occupied time grows 39082 to 45189. These interval totals do not identify the waiting cause. Step3 memory dependency counts change 6542 to 5972, and observed L1 peak falls 523136 to 517120 bytes despite the slower outcome; fewer edges or lower peak are not a makespan improvement certificate. Full op events and Step3 summaries differ.

Actual T0: 2026-09-23T23:33:46.840123+00:00; as-run commit: 2c67b6b6c56d7659776835fd51b718eaa9d246da. Both official subprocesses exited 0. No retries or additional calls.
