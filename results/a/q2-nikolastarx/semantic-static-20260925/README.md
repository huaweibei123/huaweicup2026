# New unified router: 30-cell structural check

Fixed solver source: `b7c05cf2205bd42ec23680e618a10796b37562f6`.
The script constructed exactly the six affected graph families × five core
counts: **30/30 structurally valid and full-core-order acyclic**, zero E0/E1/E2.
Elapsed static audit wall: **14.492321 s**; per-row construction time excludes
process startup and I/O and is not a benchmark solver timing.

Nine output plans exactly match old static hashes. Six output plans match
already evaluated plans byte for byte: 016 k2 uses arrival-tree, 016 k4/k5 keep
the previous direct plans, and 062 k2/k4/k5 use paired leaves. These checks prove
plan identity, not new-source solver timing or independent official rescoring.

The large-vector-cut repair triggers on 016/024/051 at k2 and k3. Other cells
retain the selected general construction or use the guarded tree. `rows.jsonl`
records every route, input/plan hash, trigger, constructor count and exact
reference path; `report.json` fixes source/script/config identities. No 500
new-cell validation is claimed: the other94 graph families were recognized
in the companion scan but not reconstructed in this check. No full plan copies
were stored here; known official references already preserve their bytes.
