# Mean per-case Makespan speedup

Arithmetic mean of each valid case's singlecore_cycles / makespan_cycles; not a ratio of sums.
P3 is an extension metric; its official primary comparison is same-core no Cache / Cache.
NA values are excluded, and valid / expected counts are retained. Unequal coverage is not a paired comparison.
P1/P2 core-1 points reuse the same official singlecore anchors, not separate solver executions; actual P1/P2 runs cover cores 2–5.

| Cores | P1 mean (n/100) | P2 mean (n/100) | P3 extension mean (n/100) |
| --- | --- | --- | --- |
| 1 | 1.000 (86/100) | 1.000 (86/100) | 1.096 (86/100) |
| 2 | 1.770 (78/100) | 1.456 (86/100) | 1.898 (86/100) |
| 3 | 2.428 (76/100) | 1.821 (86/100) | 2.572 (86/100) |
| 4 | 2.966 (76/100) | 2.103 (86/100) | 3.134 (86/100) |
| 5 | 3.347 (76/100) | 2.249 (86/100) | 3.604 (86/100) |
