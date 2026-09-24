# P1: preserve components before cutting Tasks

Owner: `nikolastarx/s-6607cb2735304751b36662035723372b`.

## Hypothesis and evidence

The fixed64 batch at `6664a63adc3464d28d1f835d907cdeaea23e6b35`,
`results/a/local-p1-fixed64-20260924/20260924T1337Z-s59ee/board-feed-full500.json`,
contains 100 cases at each of 1–5 cores. Its five-core arithmetic mean of
official singlecore Makespan / candidate Makespan is **1.0913102892**, not the
board's mixed historical-best mean. At five cores, 50/100 candidates are slower
than official singlecore. These are existing measurements, not new calls.

Graph-only inspection found that case020 has 288 COPY-contracted weak compute
components (largest: 28 ops). fixed64 mixes components in all 110 Tasks; adjacent
Tasks form a dependency chain, and all 110 land on core 0. Its Makespan is
1,078,404 cycles versus singlecore 532,746, with 60,788,736 extra DDR bytes and
zero spill. Thus zero spill alone does not identify a good partition.

The Pro r06 memo's chain/component constructions informed the hypothesis;
r11's Q1-specific local compilation and full global evaluation distinction is
retained. Sources are archived in `AI chats/20260924-Pro1-A题方法/附件/` as
`r06-RESEARCH_MEMO.md` and `r11-RESEARCH_MEMO.md` on the shared main branch.
Their reported experiments are not local validation of this algorithm.

## Direct construction

`src/q1/component_pack.py` contracts excluded COPY nodes with the frozen
official graph helper, builds weak compute components using union-find, sums
compute cycles by pipe in each component, then assigns components in decreasing
maximum-pipe-work order to the least projected loaded core. Ties use total
work, current operation count and core index. All whole components assigned to
one core become **one Task**. Original compute-map insertion order is retained.

Distinct weak components have no compute dependency edge between them.
Unioning components therefore leaves no cross-Task compute dependency;
the official plan derivation and Task-order validator check that property.
The pipe-load vector is a construction proxy: it is not a Makespan prediction,
spill certificate, or proof of a performance bound. Shared input replication,
FIFO order, memory pressure, copy costs and shared DDR arbitration remain E0
questions. A connected graph uses one core; no artificial cut is introduced.

After the official adjacency and COPY-contraction helpers have built the graph,
union-find costs O((V+E) alpha(V)), component sorting O(C log C), assignment
O(CKP), with K<=5 and P the pipe count. Sorting successor sets for deterministic
union traversal adds O(sum d(v) log d(v)). The official helpers and final
validation have their own cost; this is not an unsupported end-to-end linear
complexity claim. No candidate search, evaluator, training or offline case
precomputation is used by the solver.

## Frozen first validation batch

Before viewing any new E0 results, freeze this eight-cell development batch:

- k=4: cases 002, 020, 044, 045, 080, 097.
- k=1: cases 020, 044 (verify behavior; do not assume equivalence to singlecore).
- One active cell, one evaluator process; constructor timeout 30 s, E0 timeout
  60 s; at most eight constructor starts and eight E0 starts. No retry, E1,
  E2, or search. Stop the batch on unexpected failure; retain unrun cells.
- Freeze constructor and runner source commits before execution. Preserve each
  input identity, exact plan, E0 result, diagnostics and process receipt. Record
  solver startup-to-exit wall separately from external E0 wall, including plan
  writing and constructor validation. An E0 success must parse a real result.
- Reuse exact fixed64 and official singlecore evidence from the above commit;
  do not rerun the baseline. Record all attempted cases including regressions.
- This selected development batch diagnoses mechanisms. It does not establish
  a full-100 score or optimum. Further variants require a new declared batch.

User authorized continued P1 quality and speed optimization, including local
and Colab resources when not conflicting with other sessions. Execution owner
s-59ee confirmed no active local/Colab scoring at reservation time. This batch
does not reuse any sealed prior budget or activate cloud/GPU resources.

## Verification boundary

Four graph-level unit tests cover independent chains, an internal COPY bridge,
complementary pipe loads/order preservation, and input-domain handling. They
invoke no evaluator. Performance results and board feed will be delivered in
their own immutable result directory, separately from this construction note.
