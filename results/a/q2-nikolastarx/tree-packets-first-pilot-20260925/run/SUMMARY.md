# Tree packet-first ordering: three paired official results

Source `e5c3a923eafa570dba1cc8f415cd58014df1aa3b`; runner `1beadbbc70971d262f570499d5e2d1cd867d7195`. Prior tree data `d15f27fe3ad41be63c9e837af0a7afae440eca66`.

Execution UTC 2026-09-24T16:26:56.172195Z to 2026-09-24T16:27:13.738586Z; aggregate driver wall 17.566359125 s.

Three fresh solver calls and three final official E0 calls succeeded; zero online E0/E1/E2, scoring failures or retries. Postprocessing adds zero scoring calls and does not rerun the old tree solver.

| Case | k | Old Makespan | New Makespan | Delta | Reduction | DDR B | Extra DDR B | Spill B | Solver s | Final E0 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 062 | 2 | 1514488 | 1514524 | +36 | -0.002377% | 13407744 | 6144 | 0 | 1.019341 | 4.502228 |
| 062 | 4 | 1008337 | 844842 | -163495 | 16.214321% | 13426176 | 24576 | 0 | 0.938316 | 3.540819 |
| 062 | 5 | 673563 | 672387 | -1176 | 0.174594% | 13444608 | 43008 | 0 | 0.932889 | 3.288638 |

Two wins and one loss are retained: k2 worsens by 36 cycles; k4 improves by 163495 cycles; k5 improves by 1176 cycles.

Independent byte/data checks confirm node_to_subgraph entries and all op owners are unchanged. Packet metadata, reconstructed complete packet membership, each internal packet word, skeleton subsequences, core compute loads, raw cut edges and transfer bytes are unchanged. New core schedules exactly equal the stable partition of each old schedule into packet ops first, skeleton ops second; 1/2/3 core orders change for k2/k4/k5 respectively.

Every official data_movement_bytes field is identical old/new, including original_graph_copy_bytes, scheduled_copy_bytes, added_copy_bytes, partition_added_copy_bytes and spill_added_copy_bytes. All three have zero observed spill. The sole plan-level intervention is order, so DDR volume does not explain these quality changes; this does not prove a general ordering improvement or zero-spill theorem.

The reported fixed-FIFO bounds remain candidate-specific metadata. They are preserved for diagnosis and are not treated as predicted Makespan or independently reproved by this export. The k5 bound is unchanged while its official Makespan improves.

Checked 42 per-cell manifest entries, 6 raw/stored gzip hash-and-size roundtrips, 67 unchanged original files, and nine completed driver/solver/final receipts. All nine PIDs are absent. All per-cell and aggregate producer prechecks are eligible; this is not central admission or scientific acceptance.

This is case062 at three fixed core counts, a selected paired development experiment, not full100/500. No whole-suite mean is reported. Wall times include launch/input/output/observation/cleanup; separate final E0 wall is retained. Machine timing differences do not establish causal solver speedup.

The frozen failure_policy retains the copied phrase six-cell driver; manifest, three single-cell protocols, journals and batch cover exactly three cells with max3 final E0. This wording issue does not change the observed allocation. Original evidence is not altered.

Root reports actually receiving and replying to the P1 resource-window release. This export does not independently validate the external handoff messages.

Publication remains with the parent: explicitly include three nested final/official.log files. Original driver receipts retain actual interpreter paths. No Git operations, external messages, network requests, central ledger writes or mirror synchronization were performed.
