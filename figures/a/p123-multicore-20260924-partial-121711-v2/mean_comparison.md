# Mean per-case Makespan speedup

Arithmetic mean of each valid case's singlecore_cycles / makespan_cycles; not a ratio of sums.
P3 is an extension metric; its official primary comparison is same-core no Cache / Cache.
NA values are excluded, and valid / expected counts are retained. Unequal coverage is not a paired comparison.
P1/P2 core-1 points reuse the same official singlecore anchors, not separate solver executions; actual P1/P2 runs cover cores 2–5.

| Cores | P1 mean (n/100) | P2 mean (n/100) | P3 extension mean (n/100) |
| --- | --- | --- | --- |
| 1 | 1.000 (86/100) | 1.000 (86/100) | 1.087 (52/100) |
| 2 | 1.806 (46/100) | 1.459 (52/100) | 1.900 (52/100) |
| 3 | 2.516 (45/100) | 1.750 (52/100) | 2.595 (52/100) |
| 4 | 3.079 (45/100) | 2.149 (52/100) | 3.130 (52/100) |
| 5 | 3.551 (44/100) | 2.251 (52/100) | 3.587 (52/100) |
