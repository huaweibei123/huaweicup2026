# Q2/B stage A: semantic and baseline checkpoint

Task: `a-q2-core-search`, card commit `35709578f01689c20eaf9ef2dd68c274393a3a53`.
Execution session: `yuanzhifang30-sudo/s-25ac3f7459f94fabb940724245a20ade`.
Local coordinator explicitly approved **stage A only** at T0 2026-09-24
03:56:25 Asia/Taipei. No M1/M2 search or full-data quality experiment is included.
Atlas writes remain with the coordinator.
Captain alignment: [Issue #33 comment](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5802181435).
The completed checkpoint is in
`results/a/q2-yuanzhifang/stage-a-20260924-035625-retry1/REPORT.md`;
its evaluated source HEAD is `fd9d686c37b5a27a8595fc2f7483c089bf4a92e3`.

## Reproduce

Use a clean task worktree and an unused output directory. Original inputs remain
read-only except for the existing verified case-restoration script.

```powershell
uv sync --locked
uv run python -B scripts/a_materials.py --extract
uv run python -B -m unittest discover -s tests/q2 -p test_*.py -v
# Only with a separately authorized budget, replacing FRESH-RUN-ID:
uv run python -B -m src.q2.stage_a --output results/a/q2-yuanzhifang/FRESH-RUN-ID
```

The control tests do not invoke Q2. The one-shot stage runner refuses an existing
output directory, persists each reservation before launch, and reserves at most
12 official Q2 invocations, including rejected inputs and the final confirmation.
**Do not rerun this stage under the original authorization after using its calls.**
A new directory is necessary for a separately authorized reproduction, not a way
to reset the per-stage allowance.

The stage allowance is 1800 seconds. Its deadline starts before static-input
preparation; each child is limited to 120 seconds or the remaining stage budget.
Only supervised subprocesses are interruptible under this deadline. Static
archive/metadata operations and final report/hash writing are not continuously
supervised. The recorded 12.469 seconds stops at the start of final recording;
the remaining output/hash/report tail is unmeasured. Installation and the initial
114-file/100-case restoration check are separate public preparation. Recorded
timeout/termination overshoot is retained. Serial execution only; this runner
does not establish a hard end-to-end wall-time guarantee.

The first attempt failed on Windows GBK default decoding before launching Q2.
Its zero-call budget and failure receipt are preserved in
`stage-a-20260924-035625`. After the explicit UTF-8 fix, the continuation used
`--wall-seconds 1770`, conservatively reserving 30 seconds for that preflight.
Together the two directories contain exactly 12 official launches, exhausting
the approved stage A call allowance.

Windows child processes use `sys._base_executable`, the actual same-version
interpreter. A control test reproduced a venv redirector orphan on timeout;
switching to the actual interpreter fixed child reaping. All child tools in this
stage use only the standard library. Working-set sampling includes the controller
and its one direct child every 250 ms during construction/CLI subprocesses. The
4 GiB stop threshold is **sampled**, not a kernel-enforced allocation limit;
between-sample peaks and shared-page double counting are possible. Static archive
reading and report generation remain controller-only preparation/recording with
boundary checks. No claim of hard memory containment is made. Sampling failure
or threshold crossing stops the stage; only its own known child is terminated.
This monitoring path is tested on Windows; other OSes fail closed.

## Baseline and predeclared inputs

`python -B -m src.q2.construct GRAPH --cores 4 --output PLAN` contracts original
COPY nodes using frozen structural helpers, chooses a deterministic minimum-ID
Kahn topological order, and assigns contiguous intervals using cumulative
`max(1, cycles)` thresholds. Each nonempty core gets one subgraph. The weights
are only a load heuristic, not true Task durations; official Q2 is the execution
and timing authority. The mapping is serialized in the constructed traversal
order. No deduplication by renumbering or reordered mappings is attempted.

| Call | Input/purpose | Expected status |
|---|---|---|
| 1 | PDF page 11 minimal graph with empty second core | ok, 6 cycles |
| 2 | Official case002 random format stub, 4 cores, seed0 | ok; format reference |
| 3 | case002 deterministic contiguous baseline, 4 cores | ok, independently confirmed |
| 4–5 | Pro3 head_blocking, fixed mapping, two priorities | ok; inspect FIFO effect |
| 6–7 | Pro3 fork, fixed core assignment, coarse/fine buckets | ok; inspect COPY placement |
| 8 | Reverse an intra-core dependency | rejected in plan ordering |
| 9 | Two independent chains, opposite cross-core FIFO waits | rejected in global execution graph |
| 10 | Single op input+output exceeds UB | rejected at Step2; outside official graph guarantee |
| 11 | Each op fits UB, but interleaved 70000-byte live outputs | ok; inspect spill and local peak |
| 12 | Better of calls 2/3, byte-identical plan, repeat official CLI | ok; full repeat comparison |

Two valid Pro3 graphs and four plans are read from fixed research commit
`3a4505d4101e23d54580d15560da3820e02d05da`, archive
`results/a/pro-research-20260924/pro3-r2.tar.xz`. The archive and all selected
members must match its manifest. No research script, runtime or WordEvaluator is
executed. Author scores are not used as substitute results or expected scores.

The global-cycle and capacity fixtures are local synthetic tests, not additional
official cases. Global-cycle input passes the ordinary graph/plan layer in the
intended construction; the exact rejection stage is separately checked. The
oversized-op fixture is explicitly outside the formal single-op capacity domain.

## Evidence and boundaries

Each invocation keeps graph/plan/config hashes, command, complete successful
JSON/trace/log, stdout/stderr, timing, samples and exit status. Unrecognized
failures remain errors. Timeout/resource-limit outcomes do not become invalid.
The runner records its source HEAD and source hashes, Python/environment,
dependency versions and lock hash, actual/reserved calls, comparison checks and
artifact hashes. `input_plan` filename is the only excluded field in the final
full-JSON repetition check because the plan bytes are copied to a new filename.
The result directory has a scoped `.gitattributes` rule preserving evidence bytes
across Windows and other checkouts; hashes must not change with line endings.

The three-case proposal for later stage B is separate: each case × method would
have equal 32-call/600-second ceilings, including the common initial baseline
and final confirmation. This document does not authorize or run that proposal.
Final competition coverage of all cases and 2–5 cores is also not stage A.
