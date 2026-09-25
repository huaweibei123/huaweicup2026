# P1 shared COPY_IN component census (static)

Source: `data/raw/a/official-cases.zip`, SHA-256 `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528` (100 official graphs). Run from the repository root:

```sh
python3 scripts/p1_shared_group_census.py --output results/a/p1-shared-group-census-20260926/census.json
python3 scripts/p1_shared_group_baseline_audit.py --output results/a/p1-shared-group-census-20260926/baseline-audit.json
python3 scripts/p1_shared_group_priority.py --output results/a/p1-shared-group-census-20260926/priority.json
```

The script verifies the ZIP hash, then reads each graph once. A component is a weakly connected set of non-COPY ops under direct op edges and tensor producer-to-consumer edges. A reused COPY_IN tensor is produced by exactly one COPY_IN op and consumed by compute ops in two or more components; *partial* means fewer than all compute components consume it. `consumer_groups` records exact sets of consumer component indices, with components numbered from zero in minimum-op-ID order.

| Measure | Cases / structure |
| --- | ---: |
| Graphs with cross-component reused COPY_IN | 74 / 100 |
| Graphs with partial reused COPY_IN | 56 / 100 |
| 011 | 16 components × 43 ops; 8 distinct four-component consumer groups × 22 tensors = 176 partial shared tensors |
| 027 | 16 components × 89 ops; 8 four-component groups × 45 tensors = 360 |
| 059 | 64 components × 43 ops; 16 eight-component groups × 22 tensors = 352 |
| 097 | 64 components × 103 ops; 16 eight-component groups × 52 tensors = 832 |

The per-case counts, component-size histograms and tensor bytes are in [`census.json`](census.json); exact consumer-component sets are retained for the four focus cases. They have regular consumer-group incidence and equal component sizes. This is a structural lead for studying shared-input grouping; equal sizes and consumer groups do **not** establish component DAG isomorphism, feasible Task partitioning, cache-capacity fit, or useful timing.

The second script reads the **already saved** K5 plans and `prior-result.json.gz` files from `p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500`; it does not regenerate them. For each shared tensor, it counts the distinct baseline Tasks containing a compute consumer. The count above one indicates a Task-boundary reread; `(count - 1) × tensor size` is a structural reread quantity, not a predicted time saving. Source paths and SHA-256 hashes, full Task-count distributions, and saved movement fields are in [`baseline-audit.json`](baseline-audit.json).

| Case | Shared tensors crossing baseline Task boundaries | Structural extra read | Saved spill COPY | Interpretation |
| --- | ---: | ---: | ---: | --- |
| 011 | 88 / 176 (50%) | 540,672 B | 0 B | Four active cores, one Task each; half the shared inputs already remain within one Task. |
| 027 | 300 / 360 (83.3%) | 2,727,936 B | 0 B | Six Tasks across five cores; a long tail Task remains. |
| 059 | 330 / 352 (93.8%) | 2,072,576 B | 0 B | Five active cores, one Task each; cleaner grouping study. |
| 097 | 832 / 832 (100%) | 17,039,360 B | 4,272,128 B | Largest boundary exposure, but capacity and spill interactions complicate attribution. |

The initial reuse-only triage suggested **059** as a clean mechanism study. A subsequent compute-resource check changes the performance-research priority: 059 and 097 already sit close to the dominant Pipe's resource lower bound. They remain useful for explaining reuse, but are poor first targets for materially raising the overall mean.

The third script joins the **same frozen checkpoint** with a necessary lower bound `L = max_pipe ceil(sum(max(1, op.cycles))/5)`. It assumes each original non-COPY op executes once and each core has one slot per Pipe. Its optimistic contribution to the 100-case mean is `(B/L - B/M)/100`, where `B` is the fixed official single-core baseline and `M` the saved K5 Makespan. This ignores dependencies, FIFO, capacity, COPY and DDR contention: it is an upper ceiling on possible improvement, never a prediction of achievable gain or a shared-input-specific benefit. The 100 bounds and contributions were checked against the independently published [resource calculation at f25c7415](https://github.com/huaweibei123/huaweicup2026/blob/f25c74150826f95f15b55e4eca8a71be50eedaf9/results/a/p1-compute-resource-gap-20260926/resource-gap.json); all match.

| Case | Saved K5 cycles | Compute lower bound | Optimistic maximum contribution to mean |
| --- | ---: | ---: | ---: |
| 011 | 46,880 | 36,890 | 0.010669× |
| 027 | 508,076 | 445,824 | 0.006497× |
| 059 | 150,782 | 147,559 | 0.001202× |
| 097 | 2,102,348 | 2,060,698 | 0.001105× |

For a broader construction, inspect 019, 010, 100, 015 and 026 next: all have shared inputs crossing baseline Tasks and materially more optimistic headroom. These are research witnesses, not case-ID dispatch rules for a solver. The full 100-case record in [`priority.json`](priority.json) retains both axes separately. In particular, 068 has large resource headroom but only 1,944 B of structural repeated shared-input reads, so a headroom-only ordering would also be misleading. Any new constructor must identify useful structure from the input, preserve parallelism and capacity, and account for the actual core queues.

Separately, [the R7 044/K5 official probe](../p1-r7-construction-probe-20260926/RUN_RESULT_044_K5.md) reduced Makespan from 64,624 to 58,450 (9.55%). It supplies one positive mechanism result. Replacing only that cell would increase the frozen mean by just 0.0025238× (about 0.0622%); that arithmetic is not a new unified benchmark. This census continues to use the frozen 4.055266985790237× checkpoint consistently.

This census constructs and scores no plan. In particular, graph-visible reuse is not a valid two-key P1 submission or a Makespan claim. A future candidate would need complete eligible-op coverage, valid `node_to_subgraph` and `core_schedules`, the official combined data/core-order DAG and capacity checks, and separately authorized official evaluation. Solver, Task compiler, E0, E1 and E2 calls here: **zero**.
