# Stage L: negative shared-input pipeline evidence

The two prospective cells are complete. Both plans are legal under unchanged
official Scene A E0, but both are worse than the fixed v4 same-cell result:

| Cores | Stage L Makespan | v4 Makespan | L scheduled COPY B | v4 scheduled COPY B | L extra DDR B | L spill B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 84,041 | 64,624 | 2,932,000 | 2,026,944 | 1,956,544 | 0 |
| 4 | 82,479 | 64,624 | 2,957,344 | 2,026,944 | 1,981,888 | 0 |

This rejects the present constructor as an improvement on these two development
cells. It does not reject all shared-input batching, other partitions, lifetime
capacity models, or two-core constructions. No new scoring budget is created.

## Fixed evidence and independent checks

- Constructor: `5c64b4057cb9b2f2af5426bd1efdd579b9df5559`.
- Runner: `aa66a805551a2f2225795f2ec5b2db444ba35b28`.
- Actual plans, diagnostics, E0 result/trace/log, manifest, run receipts and feed:
  `2dadb457ecd998dbdfca574329e76000e8c1f906`, under
  `results/a/q1-yuanzhifang-stage-l/stage-l-mem512-20260925/`.
- Producer's negative-comparison README was added in
  `032f8f0362ac10e2e2ca422766bd30a38c4394c6`; raw results/feed are unchanged.
- Captain comparison: fixed `9c5f87548cc7588465a638e032993969b5cac891` full500
  feed, same graph/config/official identities.

The parent read both completed E0 records and timelines, then ran its own
`src/benchmark_board/protocol.py` with `--submission --commit 2dadb457...` and
the producer repository. It returned valid=true, eligible=2, records=2. This
checks fixed artifact bytes/submission metadata; it is not a new E0 run or
central score-board receipt. The feed has been handed to the existing board
owner, with no manual duplicate submission requested.

The board owner subsequently reported signed central source_status for this
fixed result: delivery prefix8e2d8f7e, checked_at2026-09-24T22:11:23.385019Z,
added2/status ok; local signed seq11380 and HTTP contain both eligible records.
The already-open P1 page first showed the batch at22:14:52Z without refresh.
The owner's outbox still showed awaiting_receipt at that instant; queue status
is recorded separately from central acceptance. This parent has read the
owner's report, not independently reverified the central signature.

`analyze_packet_trial.py` independently reads the fixed originals and original
044 graph. For every tensor it reconstructs the input-boundary Task set and
output-boundary Task set using the official boundary rules, then sums COPY
bytes and `max(1,ceil(bytes/60))` service. Reconstructed COPY bytes equal E0
exactly for both plans. The isolated service sums are 49,098 and 49,494 cycles,
also exactly equal to the constructor's corresponding static service proxy.
Both E0 results report zero spill and zero Step3 memory-dependency edges.
Thus the large timing error cannot be explained by a byte-count discrepancy or
spill in these two records. The model's claimed scope already excluded timing
guarantees; this experiment demonstrates why that limitation matters.

The selected total cost proxies were 55,435 and 49,494 cycles, substantially
below the measured 84,041 and 82,479. For k4, core0 finishes its final Task at
22,460, while core3 begins its first Task only at 43,334. Middle cores1/2 each
accumulate 35,489/37,560 cycles in MTE2 operations. These are observed
fill/drain and shared-resource effects, not additive independent delay terms:
COPY intervals overlap across cores. They support investigating FIFO timing,
shared-DDR contention and pipeline balance before another candidate, but are
not a controlled decomposition proving the exact causal contribution of each.
`local_makespan` is not used as a lower bound on global Task duration.

## Calls and resources

Actual first-cell T0 `2026-09-24T22:07:52.148724Z`, batch T1
`2026-09-24T22:08:08.851017Z`, batch wall16.703258s; two cold solvers and two
new external E0 calls, zero E1/E2/retries, one worker. Cold solver walls were
7.0336955/7.7344650s and external E0 walls0.8484066/0.9378048s. Each owned
solver/E0 Job had a 512 MiB aggregate committed-memory cap and was verified to
have zero active processes at close. Available RAM before the cells was
2,380,935,168/2,135,826,432B. Windows/Python environment and exact commands
remain in the original manifest/receipts; there is no controlled cross-machine
speed claim. The measurement window was released immediately after T1.

The subsequent parent analysis uses zero new solver, Task compilation or
evaluator calls. Reproduction:

```sh
python -m src.q1_yuanzhifang.analyze_packet_trial --output NEW_ANALYSIS_JSON
```

The next useful deliverable is a timing model or structural argument that
accounts for these observations, before allocating another scoring batch.
No full100 mean or global optimality claim follows from this two-cell failure.
