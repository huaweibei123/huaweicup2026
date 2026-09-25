# Three-graph fork/join structure survey

Static-only survey of the archived selected pilot plans. It reads the graph and current selected assignment; no solver plan is built and no evaluator or schedule step is called. Chain indices come from `DAGIndex.__init__` and `gap_candidate._chain_dag`; the chain-placement/build methods are not called. Each fork scan is capped at 32 chain steps per branch.

| Case | Eligible ops | MTE2/MTE3/M/V duration | Chains (max ops) | Forks / joins | Strict diamonds | Diamond op union | Internal tensors (n; mean/max B; consumers) | Internal tensor payload / current cross-copy in union |
|---|---:|---|---:|---:|---:|---:|---|---:|
| 003 | 13455 | 0/0/438792/325189 | 9903 (9) | 3640 / 7166 | 172 | 903 (6.7%) | 13438; 579/8192; 20540 | 1,391,008 / 959,232 B |
| 005 | 4113 | 0/0/63882/60930 | 3049 (4) | 1166 / 2170 | 63 | 343 (8.3%) | 4106; 702/4608; 6258 | 487,312 / 136,768 B |
| 056 | 7678 | 0/0/131016/245953 | 5540 (8) | 2069 / 3894 | 202 | 1092 (14.2%) | 7641; 683/4096; 11483 | 669,798 / 138,912 B |

## Interpretation

003: 1–2-op chains 98.4%; fork out-degree {'2': 3034, '3': 99, '6': 54, '7': 3, '8': 18, '9': 432}; all joins have in-degree 2. M/V=57%/43%; 118/172 diamonds contain work on multiple pipes; selected placement splits 72 regions across cores.
005: 1–2-op chains 98.6%; fork out-degree {'2': 933, '3': 35, '5': 9, '6': 21, '7': 168}; all joins have in-degree 2. M/V=51%/49%; 42/63 diamonds contain work on multiple pipes; selected placement splits 12 regions across cores.
056: 1–2-op chains 97.2%; fork out-degree {'2': 1660, '3': 171, '6': 20, '7': 2, '9': 216}; all joins have in-degree 2. M/V=35%/65%; 148/202 diamonds contain work on multiple pipes; selected placement splits 42 regions across cores.

This is a bounded structural scan, not a performance result. Strict diamonds cover only a minority of eligible ops, so the structure is useful as a targeted region proposal, not a graph-wide rule. Multi-pipe work suggests possible throughput complementarity, but does not prove overlap or lower Makespan. The archived assignment’s internal cross-copy estimates under all-region co-location appear in the table and detailed regions in `STRUCTURE.json`; they are not promises about legal regrouping or preserved makespan.

## Diamond and byte definitions

A strict region has exactly two successor chains from its fork, two uniquely serial paths, and a common join whose only incoming chains are those two path tails. Interior nodes have no external in/out edges; fork input and join output boundary edges are allowed. Internal tensor payload counts each tensor once when all eligible producers and consumers lie in the region. Current internal cross-copy bytes are removable only under full co-location of the region in the current assignment; any such change still needs legal plan construction and official evaluation to establish its makespan and spill effects.

Pilot commit `a6b09dcebf26c5ac28bcb4378dec8dbf06b0c075`; manifest SHA-256 `7af8890338b120e6b179fe96fbaacf746b2ab7ad34a1f2dabe2945afdd29f597`. Run `python3 survey.py --raw-root <directory-with-case-json-files>` to reproduce using the manifest-hashed raw graphs.
