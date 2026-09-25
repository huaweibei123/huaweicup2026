# R05 pair: fixed-order necessary bounds

This is a read-only static analysis, not a constructor run or an official
evaluation. `scripts/q2_r05_pair_static_bounds.py` validates the original
003 graph, both saved plan hashes, and the archived c665 E0 comparator before
applying the previously documented fixed compute-FIFO necessary bound.
Full path witnesses are retained in the two compressed bound records.

| Plan | Assigned Pipe workload bound | Fixed FIFO bound | Current c665 E0 |
| --- | ---: | ---: | ---: |
| Old R05 seed | 219548 | 230755 | 245150 |
| Recovered raw candidate | 222848 | 240126 | 245150 |

Units are cycles. The bound is conditional on successful official execution
of this exact singleton plan; it omits communication and memory effects.
It is not a bound on other assignments or orders, and does not prove that
either plan is officially valid.

The recovered plan can reduce Makespan relative to current c665 by **at most
2.0494%** under this bound, even with all omitted costs hidden. This is a
ceiling, not an expected gain. The bound does not rule out a strict gain,
so the frozen official pair still provides a valid proxy-rejection test.

The headline COPY reduction, 6351422 to 5207554 pre-Step2 bytes, is relative
to the old R05 seed. The current c665 comparator already has 4262874 official
scheduled COPY bytes and zero spill. These are different plans: a reduction
against the old seed cannot be reported as a reduction against c665.

Research consequence: retain the pair as a small mechanism check, and allow
the reusable reconstruction to start from a caller's currently selected
complete plan. It must obtain that seed online; the archived comparator in
this report is for research diagnosis and must never become an online lookup.
Singleton packets offer a first general adapter without requiring a historical
chain witness or risking contraction-induced cycles. This does not yet show
that the new adapter improves official results.

Reproduce with an unchanged official graph and a new output directory:

```sh
python3 scripts/q2_r05_pair_static_bounds.py \
  --graph data/raw/a/official/data/case_003.json \
  --output output/r05-static-new
```

The first exploratory run is retained locally under the prior output stage.
The published run verifies the current E0 comparator from archived bytes.
Both bound calculations took about a quarter second on this host; this is
not a solver end-to-end timing claim. No E0/E1/E2 or preparation was called.
