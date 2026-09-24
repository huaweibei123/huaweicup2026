# Controlled split: one official P2 result

016 / five cores: **2,240,622 → 1,952,569 cycles**, reduction **12.8559%**. Extra DDR **281,636 → 39,994,024 B**; spill remains zero. This is a Makespan/movement tradeoff, not all-metric dominance.

One solver **0.679139 s**, one external unchanged E0 **4.079934 s**; aggregate **6.176729 s**. No online E0/E1/E2, no retry, all three process IDs exited. Source `d1cb26fe04cd7f0a49c053fde8b0e97d3c9b5780`, runner `c970e6a8215307f864d87f56fcfd3b3989306ed3`; reference data `81219bf923524fb60616e39b5ad2dced67aec3e2` was read, not rerun. The exact final plan matches the earlier static plan hash.

The proposed 610 large tensor crossings account for 39,976,960 added bytes. The fixed-plan lower bound is 1,931,673; its gap to official time is 20,896. The bound is not global, and the original compute-touch memory proxy alone did not prove zero spill. This actual E0 run establishes zero spill for this plan/input/config only.

All 14 raw manifest entries, four feed references and two compressed byte roundtrips passed. This script adds zero scoring. Full-suite b7 results and Pro r02 pending theory are separate; central feed admission and Git byte verification are recorded separately.
