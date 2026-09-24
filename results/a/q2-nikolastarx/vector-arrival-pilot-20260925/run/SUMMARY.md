# Arrival-tree placement: one official validation

Source `ae4f8a0b4a0b3335092eb592a669c4fbc8d378b1`; runner `e83caab0c10489d2679fc479c71f4c696df99bfd`.

016 k2: Makespan **4,170,750 → 4,027,481 cycles**, reduction **3.4351%**. Added DDR **4876 → 9144 B**, spill **0 B**. Solver **0.578207 s**, external final E0 **4.289849 s**. Aggregate process budget consumption **6.091176 s**.

Exactly one deterministic solver and one final unmodified E0, no online E0/E1/E2 or retry. Static k4/k5 candidates were pruned because their fixed-plan lower bounds already exceeded existing achieved makespans; no new official scores claimed for those cells.

The fixed-plan bound is 4,026,386; the official gap is 1,095 cycles. This constrains further improvements with this exact placement/order, not different placements or a global optimum. All metrics and original files are listed in verification.json; root checked hashes and the three process IDs have exited. Results are development evidence, not a 100-case average. Central feed admission remains a separate state.
