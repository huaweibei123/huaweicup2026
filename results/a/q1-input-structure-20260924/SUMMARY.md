# P1 shared-input budget: implementation and first official evidence

The constructor addresses repeated external-input loading across Tasks. It compares at most K metadata-only active-core configurations, selects one using compute/copy/gate costs, constructs that plan once, and refines each selected Task with bounded input windows. It never evaluates alternative plans online. The requested K-core result retains empty schedules for inactive cores.

Implementation: `src/q1/shared_input_budget.py` at `288dd520caa5c7baaa1413e4021eb2d4221b6e66`. Ten synthetic checks and the static coverage audit are preserved in this directory. The audit is not an official performance measurement.

## Three predeclared official probes

| Case / requested cores | Bounded04 cycles | New cycles | Extra DDR bytes, old → new | Solver seconds | External E0 seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 044 / 5 | 132892 | 64624 | 6196032 → 1051488 | 0.078590 | 0.182366 |
| 046 / 5 | 131039 | 103846 | 5013664 → 3143456 | 0.075345 | 0.130865 |
| 090 / 5 | 542638 | 319844 | 21724704 → 8838528 | 0.074526 | 0.240996 |

All three new E0 results have zero spill. Actual active cores are 2, 4, and 5, respectively; all are requested-five-core experiments. The finite batch used exactly 3 solver and 3 external E0 processes, one worker, no retries or E1/E2. Timing is nonexclusive Apple M5 Pro/macOS/Python 3.12.13 observation, not a controlled speedup comparison against the older two-worker batch.

Full original plans, results, traces, logs, receipts, paired baseline bytes and feed are under `results/a/q1-shared-input-probe-20260925/20260924T1618Z-input3/`, originally frozen at `edd47216ca11d6dbb9390381886df08c68d4c1d7`. The runner actually executed at `77e2234a443a580db1953138d4e5b7fee25774f9`; cherry-picking the evidence does not change either execution identity.

The result supports the combined construction on these three selected mechanisms. It does not prove which submechanism caused each improvement, a general zero-spill certificate, a full100 average, an optimum, or independent scientific acceptance. Static proxy cycles remain different from official Makespan. Submission, central admission, independent replay and algorithm acceptance are separate states.
