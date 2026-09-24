# Active-core model diagnostic

Fixed algorithm/script source: `b4ea8aa75310952d6ca7fb809efa8c3df99c2ebf`.
`profile-k4.json` records the input/config/source file hashes and the full
capacity/model terms. Its three-graph analysis took 0.379 s on the shared Mac;
this is offline diagnostic time, not solver or E0 performance.

Under a four-core budget the model selects 2/4/4 active cores for 044/083/092.
For 044 the conservative raw L1 envelope for six local jobs is
`6*6144+73728 = 110592 B`, below 524288 B; the compute/input relaxation is
40584 cycles. That value is not an achieved official Makespan. On 092 the raw
capacity bound allows only18 jobs/core, while four cores would require36, so
the implementation retains the existing four-core plan without claiming a
memory certificate. All component projections are scanned; first-component
private aliasing is not assumed to describe the others.

Reproduction (choose a fresh output path):

```sh
.venv/bin/python -B results/a/q2-nikolastarx/active-core-model-20260925/analyze.py --cases 044 083 092 --cores 4 --output output/fresh-core-profile.json
```

This reads graph statistics and private lifetime projections and solves the
arithmetic relaxation. It emits no submitted multicore plan and invokes no
solver CLI, E0, E1 or E2. The earlier ee1 full500 evaluator batch uses an older
frozen source; its results must not be attributed to this new version.
