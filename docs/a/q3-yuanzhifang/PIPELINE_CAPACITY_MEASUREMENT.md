# Capacity pipeline measurement card

Candidate: `src/q3_yuanzhifang/pipeline_capacity.py` at
`2df4a5fa70d7a59492a7477e9ecd706501e64ad6`. This is a separate 044,
four-core structural pilot, not a unified full500 result. The candidate reads
the official fixed config itself, including bandwidth and L1/UB capacities.
Its one O(k L²) stage DP uses first-job cold setup and constrains each stage's
common-input residence plus the largest single-operation noncommon footprint
in each memory space. The working-set abstraction does not prove zero official
spills or bound E0 Makespan. A rejected structural/capacity guard stops before
E0, even if the constructor emits a fallback plan.

The independent run directory is
`results/a/q3-yuanzhifang/pipeline-capacity-20260925`, with run ID
`yuanzhifang-q3-pipeline-capacity-20260925`. It permits one fresh cold
construction and at most two external E0 evaluations (P2/P3), zero internal
E0/E1/E2 and zero retries. One worker checks at least 1 GiB available RAM
before every child, sets Windows below-normal child priority, caps each call
at 30 seconds, the batch at 120 seconds, and dispatch at 90 seconds.

Before E0, the runner compares the new two-field plan by raw bytes with the
fixed original pipeline P2/P3 control from commit
`e6b5500dcbf3818034804168ee79d0f65c16706b`. Exact byte equality reuses
both fixed E0 artifacts; changed plans receive fresh P2 and P3. It checks
coverage and singleton mapping, records actual cold wall time and plan/control
identity, and preserves complete result, trace, log and call receipts. The
exporter only reads completed artifacts and labels reuse distinctly.

After committing this runner, exporter and card, identity checking is:

```powershell
python -B src/q3_yuanzhifang/pipeline_capacity_benchmark.py --check-only
```

That check runs no constructor, derive, Step or E0. Actual execution requires
an approved coordinated window and an accurate `--concurrent-work` declaration;
this card does not authorize dispatch.
