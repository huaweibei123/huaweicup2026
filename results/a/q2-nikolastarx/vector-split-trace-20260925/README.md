# Existing vector_split trace readback

This reads the one completed 016/k5 E0 run, source
`d1cb26fe04cd7f0a49c053fde8b0e97d3c9b5780`. It performs **0 new solver/E0/E1/E2
calls**, does not rebuild Step2/Step3 and never changes the original run files.
The result is 1,952,569 cycles, zero spill, 39,994,024 added DDR bytes. The plan
matches the earlier static construction byte for byte. All **27,760** operation
intervals agree between result and trace exports; these are exports of one run,
not independent E0 executions.

This is the team's constructed-and-validated **d1 single-cell** improvement of
**12.8559%**, from the existing 016/k5 score 2,240,622 to 1,952,569. The Pro r02
answer is still in flight at this handoff: this result must not be attributed
to an answer not yet received. It also does not replace the frozen b7 full
500-cell results or establish a new full-suite mean.

## The steady-stage mechanism is visible

All **304** root-to-root periods after stage 0 are **6,387 cycles**. The fixed
plan lower-bound periods are 6,335, leaving exactly 52 cycles per period.
Across both large transfers in every steady stage (608 transfers total):

| Observed measurement | Cycles | Count |
| --- | ---: | ---: |
| Source large COPY_OUT duration | 1,095 | 608 |
| COPY_IN start minus external release | 503 | 608 |
| COPY_IN start minus receiver's second whole chain op 2 end | 0 | 608 |
| Large COPY_IN duration | 1,097 | 608 |
| COPY_IN completion minus receiver's two-whole-chain completion | 49 | 608 |
| Receiver V gap immediately before suffix | 49 | 608 |
| Suffix start minus max(last whole end, COPY_IN end) | 0 | 608 |
| Sender V gap before first whole chain op 3 | 47 | 608 |
| That sender op 3 start minus large COPY_OUT end | 0 | 608 |

The previous MTE2 operation finishes before external release in every steady
large transfer. The 503-cycle wait therefore is **not** a wait for the preceding
MTE2 operation or the configured cross-core release. The only same-core
operation completing at the eventual COPY_IN start is the receiver's second
whole chain op 2. This is exactly the timing signature predicted by the
hand-derived UB-credit predecessor. In the frozen P2 event loop, a ready Pipe
head whose external release has arrived still needs its local predecessors;
the reconstructed incoming COPY has no original local producer, and this run
has zero spill. Thus a local dependency gate is the source-level explanation,
consistent with Step3 memory reuse.

However, the exports retain only memory-dependency **counts**, not the complete
WAR/WAW edge list or reused-byte sources; `official.log` also has no printed
WAR/WAW/credit records. We did not rebuild `prepare_step3_execution`. The
specific `second whole op 2 -> incoming COPY_IN` edge and its hand-derived byte
sources therefore remain an inference from source plus timing, **not a directly
read back memory-edge record**. No per-edge byte attribution is claimed.

## Concrete stage 100 (zero-based)

Previous root 5912 ends at **643,233**; current root 5971 ends at **649,620**.

| Event | sender 0 -> receiver 2 | sender 1 -> receiver 3 |
| --- | ---: | ---: |
| Large COPY_OUT | 644,783–645,878 | 644,784–645,879 |
| External release of incoming COPY | 646,378 | 646,379 |
| Receiver second whole chain op 2 ends | op 5918: 646,881 | op 5926: 646,882 |
| Incoming COPY | 646,881–647,978 | 646,882–647,979 |
| Two whole chains end | op 5920: 647,929 | op 5928: 647,930 |
| Suffix first operation starts | op 5939: 647,978 | op 5943: 647,979 |
| Suffix ends | 649,026 | 649,027 |

The receiver-3 path is tight through the final root FIFO on **every steady
stage**, not just this example:

`505 broadcast + 4192 whole-chain work + 49 wait + 1048 suffix work + 502 scalar transfer + 91 root V tail = 6387`.

The final 91 is seven consecutive 13-cycle scalar operations on core 4 after
the last leaf arrives. The minimum-lag fixed-word path is
`502 + 5240 + 502 + 91 = 6335`. The observed 52-cycle difference is therefore
**3 broadcast-serialization cycles + 49 exposed receive cycles** on this path.
The sender's simultaneous 47-cycle V stall lies on another overlapping branch;
adding 47, 503 and 49 together would double-count concurrent waiting. These
identities describe the observed schedule, not a counterfactual guarantee of
how much a modified memory rule would improve it.

## Startup differs and cannot be attributed the same way

Stage 0 root ends at 10,920 versus bound 5,833, a difference of **5,087**.
Its two incoming large COPY operations are released and start at **7,486**;
both end at **8,762**. The proposed receiver predecessor has already completed
at 7,195. Thus no late-release-to-start gap exposes that predecessor in startup.
Each receiver waits 519 cycles after its two whole chains, but their suffixes
end at 9,810, before the sender's whole work ends at 10,339. That 519 cannot
be assigned directly to startup's root delay. Initial input loads and shared
DDR contention are present; this readback does not uniquely separate them.

The entire fixed-plan gap is accounted for arithmetically:

`20,896 = 5,087 startup + 304 × 52 steady-period difference + 1 final COPY_OUT`.

The official memory peaks also show why original compute-touch intervals were
insufficient: sender cores peak at **98,306 B UB**, receiver/root cores at
65,538 B, despite every original compute-touch estimate being 65,538 B. Zero
spill is compatible with memory-reuse dependencies and exposed communication.
The 20,896 gap is to this fixed-plan bound, not a global optimality gap.

## Files and reproduction

- `readback.py`: standard-library-only reader; no official imports.
- `summary.json`: source/plan/input hashes, export checks, histograms, exact gap
  decomposition and selected transfer records.
- `large_transfers.csv`: all 610 large transfers and neighboring compute/COPY
  timestamps.
- `stage_roots.csv`: all 305 root completions and corresponding fixed-word bound.

Point the reader at the existing completed run directory containing
`final/result.json.gz`, `final/trace.json.gz`, `manifest.json` and `online/`:

```sh
.venv/bin/python -B results/a/q2-nikolastarx/vector-split-trace-20260925/readback.py --run-dir "$RUN_DIR"
```

The run originally lives in the experiment worktree under
`results/a/q2-nikolastarx/vector-split-pilot-20260925/run/016-k5/016-k5/`.
No original graph, trace, plan or large archive is duplicated here.
