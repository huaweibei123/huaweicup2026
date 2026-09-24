# Paired-leaf official results

| Cores | Prior packets-first | Paired leaves | Reduction | Added DDR B | Spill B | Solver s | E0 s |
|---|---:|---:|---:|---:|---:|---:|---:|
|2|1514524|1389508|8.2545%|6144|0|1.283998|4.732733|
|4|844842|775354|8.2250%|24576|0|1.334877|3.579314|
|5|672387|617306|8.1919%|43008|0|1.256647|3.482302|

Three solver and three unmodified final E0 calls, zero online scoring/retries. Same ownership and exact pair rewrite verified; all official movement fields unchanged. Total batch wall seconds: 18.994280499988236. These are three development cells, not a full-suite average or global optimality proof.

Source 22d773abfa5f78cf18fec65b8fb5759d88f11842; runner fa92d86add0dd8a52d2d644864925aaf620c7426. Prior data ae1d8c4d904395e010d742ea090811fb6042f6e8. Nine process IDs are gone. Original hashes, comparisons and bound gaps are in verification.json. Central admission is tracked separately.
