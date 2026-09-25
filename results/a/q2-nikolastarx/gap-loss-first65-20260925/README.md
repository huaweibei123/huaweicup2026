# Gap first-65 diagnosis

This is a fixed diagnostic prefix of 65 accepted K5 cases, not a complete batch. The compact observations preserve all 65 rows, source identities and native comparison scores. No solver or evaluator was run to produce this report.

Gap was constructed for 51 cases; selected in 23. In the 23 selected gap plans, spill bytes are zero. This does not prove memory-reuse or credit dependencies have no scheduling cost. It does rule out attributing their extra transfer bytes to spill.

| Case | E0 M | Static finish | COPY bytes / 60 | Spill B |
|---|---:|---:|---:|---:|
| 053 | 383506 | 253585 | 313011.1 | 0 |
| 043 | 208889 | 107753 | 198173.2 | 0 |
| 003 | 205295 | 105450 | 185495.7 | 0 |
| 054 | 257626 | 158728 | 229138.3 | 0 |
| 056 | 96280 | 54763 | 84747.3 | 0 |
| 040 | 78024 | 39717 | 69592.2 | 0 |
| 049 | 66201 | 37904 | 56583.9 | 0 |
| 047 | 103379 | 75437 | 79328.0 | 0 |

The byte/bandwidth column is a relaxed service-volume diagnostic for that fixed plan, not a queue simulator or an assignment-independent optimality bound. The static calendar omits boundary loading and COPY/resource queueing. These observations prioritize reducing partition traffic while preserving useful execution order; they do not establish a sole causal bottleneck.

The separate 003/k2 regional-cut experiment showed why both matter: fewer COPY bytes with inherited priority slowed E0, while retiming the same owner map produced a small E0 improvement. See ../hyperrefine-probe-20260925/README.md.
