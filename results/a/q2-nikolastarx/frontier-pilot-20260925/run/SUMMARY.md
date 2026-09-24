# Frontier pilot receipt: one cell

Case 056, five cores: Makespan **253,392 → 165,886 cycles** (34.53% lower). Extra DDR movement is **0 → 7,222,022 bytes**; spill is zero in the new E0 result. The movement increase means the result is a tradeoff, and aggregate totals alone do not establish causation.

The completed run records one solver (0.354926375 s), one final external E0 (1.579094041 s), and zero online E0/E1/E2 calls. No retries are recorded. The actual plan is semantically equal to the fixed static plan at source `ee1b8fd39efab8c8ed8140bbebe4c08e778052b9`. Graph/config hashes match the feed identity. Runner: `64e0133b97eb7dee50aa835e9c1714d84ce508eb`; old comparator data read from `571536962b3f6ad9468584a0e5ae04398e684543`.

Unique compute coverage: all 7,678 eligible operators assigned once. Manifest entries (14), feed artifact references (4), both gzip/raw roundtrips, and all three recorded process IDs were checked. This audit performed no solver or evaluator call and adds zero scoring. It is one single-cell evidence item, not a replacement for the full 500-cell evidence set, nor a causal proof from totals.
