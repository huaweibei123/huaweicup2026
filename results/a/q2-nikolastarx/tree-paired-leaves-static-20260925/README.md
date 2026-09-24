# Static paired-leaf experiment

`report.json` fixes the source, graph, configuration and check script hashes.
It records exactly three structural constructions, with **zero E0/E1/E2**.
The plans and details are original outputs; prior-trace files identify their
existing official sources by SHA-256. The prior run is the packets-first data
at commit `ae1d8c4d904395e010d742ea090811fb6042f6e8`.

Reproduction requires an empty result location; `check.py` refuses to overwrite
the report. The original command used the existing execution worktree as its
read-only `--prior-run` argument. All paths within the implementation are
repository-relative. Do not rerun the check merely to read these results.

Root verification: source/plan/detail/prior-file SHA-256 readback, original and
rewritten ownership comparison, disjoint pair structure and seven synthetic
unit tests. The local mathematical proof and its capacity limitations are in
`docs/a/q2-nikolastarx/TREE_PAIRED_LEAVES.md`. No official improvement, zero-spill
certificate, global optimality or central performance admission is claimed.
