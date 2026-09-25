# R06 review and research priority

The public Pro reply is archived in `AI chats/20260924-P2-异构流水与最优性界/r06-response-9d1b8125.md`.
It is a DOM-to-Markdown derivative with public TeX source preserved. The ZIP
attachment has not been acquired. Author-reported test counts are not local
verification or official scores.

## Accepted scope and correction

- The three capacity classes (one, two, at least three jobs per group) follow
  from closed touch intervals only when physical private-tensor reuse patterns
  match between jobs. Equal operator signatures alone do not establish this.
- A repeated stage must account for dependencies and Pipe FIFO. The chain
  M(1)→V(1)→M(1), repeated twice under job-major Pipe FIFO, needs six cycles;
  twice the maximum Pipe workload gives four. The existing scalar finite-job
  DP remains a restricted model, not an official time model.
- The proposed `C0 + Q` upper envelope requires a fixed FIFO DAG, a globally
  work-conserving DDR server, and no uncounted credit/setup/spill delays. It
  cannot safely reject an official candidate merely because it exceeds the
  incumbent.
- The proposed 2-approximation additionally requires `Q <= T`. If Q sums
  rounded per-COPY cycles while the fluid model serves literal byte work,
  that lower-bound step fails. Two 1-byte transfers at 60 bytes/cycle require
  1/30 cycle of byte-fluid work, while rounded Q is two cycles. The local
  Fraction arithmetic is in `rounding-model-probe.json`. The guarantee can
  instead be scoped to a different model that treats each rounded integer
  as divisible mandatory work on a unit-rate global server. No official
  approximation ratio is claimed.

The independent static review is `independent-review.md`. It proposes further
minimal model checks; those proposals have not been run here. The only new
local execution is the tiny exact arithmetic probe. No real graph constructor,
preparation, E0, E1 or E2 call occurred in this review.

## Decision

Keep grouped template pipelines as a supplementary route. The separately
verified nine-graph opportunity ceiling is only +0.155990 in the all100 K5
mean, even if every relevant case attained its necessary lower bound. This
does not predict an attainable gain and does not justify another large
implementation/benchmark campaign now.

The next quality experiment remains the already-frozen R05 pair: the saved
003/K2 seed versus the recovered raw candidate, whose mandatory COPY bytes
fell from 6,351,422 to 5,207,554 while its static timing proxy increased from
230,838 to 241,374. The official comparison is pending the coordinator's
exclusive resource window; there is no new score. Its purpose is to test
whether proxy rejection discarded a useful general ownership change.

Infrastructure separately owns the preparation rank-index optimization.
Its synthetic equivalence checks and pending real-plan test do not establish
an end-to-end speedup yet. No frozen full500 solver is changed by this review.

The current complete algorithm remains c66559a6, with K2–5 arithmetic means
2.316727 / 3.235566 / 3.971149 / 4.549757. These slightly exceed the screenshot's
displayed values but do not demonstrate a substantial lead or equivalent
external test conditions.
