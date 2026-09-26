# Shared evaluation service: design model only

The proposed service is specified in
[`CONCURRENT_EVALUATION_DESIGN.md`](../../../docs/a/e2/CONCURRENT_EVALUATION_DESIGN.md).
There is no service, socket, database, worker runtime, or stable public API here.

`model_checks.py` checks dispatch and oracle-budget state-machine examples with
invented integer durations. It does not import or execute E0/E1/E2, spawn
processes, or require new dependencies. Use the project's locked Python 3.12
environment. Write each run to a new file (existing output is never overwritten):

```sh
python research/a/evaluation_service/model_checks.py --output results/a/review/evaluation-concurrency-model-20260924/summary.json
```

Scope: a slow task does not block dispatch/delivery in the rolling model; three
tenants receive dispatch opportunities; simulated memory/inflight limits hold;
idempotent submission does not double-reserve; queued cancellation refunds;
started timeout keeps unknown cost; official rejection costs a call; zero oracle
budget blocks possible fallback; slow queues exert backpressure; deterministic
round selection preserves original proposal order on ties; completed candidates
ahead of an unresolved prefix still occupy the speculation window; failures stop
queued work without pretending running work was cancelled for free.

These checks do not prove real process isolation, fairness under dynamic arrivals,
transaction durability, IPC behavior, real candidate correctness, or speed. The
next implementation must test those boundaries with fault-injected fake backends
before consuming any newly declared formal-evaluation budget.

The ten existing checks do not model the later stage/unit/epoch stop hierarchy,
separate E0/E1 accounting, or multiple evaluation operations per proposal. Those
contract additions remain unimplemented and untested by this model.
