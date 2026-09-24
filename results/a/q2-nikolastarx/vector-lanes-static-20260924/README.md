# Vector-lane constructor static evidence

These are the three already completed CLI constructions for 016 at 2/4/5
cores. They were copied from `/tmp/p2-vector-lanes-s8ee-20260924/` without
rerunning the solver. No E0/E1/E2 was called. Each case retains the plan and
full solver ledger. The duplicate evidence plan is represented by a verified
byte-identity alias in `receipt.json`, not another duplicate file.

The receipt freezes source/input/config hashes and the observed nine-test
result. `docs/a/q2-nikolastarx/VECTOR_LANES.md` explains the template, proof
scope and static byte counts. There are no official score, spill or expanded
execution-feasibility claims in these artifacts.

All three original CLI commands used this form, with cores 2, 4 and 5:

```sh
.venv/bin/python -B -m src.q2_nikolastarx.vector_lanes data/raw/a/official/data/case_016.json --cores 2 --output /tmp/p2-vector-lanes-s8ee-20260924/016-k2/plan.json --evidence /tmp/p2-vector-lanes-s8ee-20260924/016-k2/online --wall 30
```

The original temporary directories still exist; do not overwrite or rerun
them. The algorithm owner controls any subsequent separately frozen E0 pilot.
