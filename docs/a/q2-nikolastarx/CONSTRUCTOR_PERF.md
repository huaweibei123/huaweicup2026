# P2 direct constructor: bounded performance diagnosis

The first optimization should stay in Python: repeated structural validation
and adjacency construction, followed by per-core DAG proposals, dominate the
two large examples. Native code is not needed to establish the next useful
improvement. This report changes no algorithm or evaluator source and makes no
new claim about Makespan, DDR bytes, or improved solver speed.

## Evidence and scope

Source is `dd9d89918f7a4e3d2cfab48d4d0246db3408310b` (the three inspected
constructor files are unchanged in checkout HEAD
`7f064bbc4663b6ab5a7c26343620bfa4f32a4921`). Evidence is in
`results/a/q2-nikolastarx/constructor-profile-20260924/`.
The original binary profiles are retained locally under
`/tmp/p2-constructor-profile-20260924-s8ee/`, with hashes in the normalization
receipt. Repository pstats are derived exports with filename/caller prefixes
replaced by `${REPO_ROOT}` and `${PYTHON_BASE}`; all call counts, timings and
caller edges are preserved and the aggregate totals were checked after reload.

Exactly one `cProfile` execution of the actual, unmodified
`src.q2_nikolastarx.direct_solve` CLI was performed for each of 008/014/025,
all at four cores. `runpy` invokes the original `main`, including graph/config
reads, `build`, structural validation, plan serialization, both plan writes,
and the solver ledger. The already imported `evaluate_scene_b`,
`_build_scene_b_tasks`, and `subprocess.Popen` were poisoned before profiling.
No poisoned entry point, scoring function, or scheduling step appears in the
recorded call stacks; all solver ledgers record E0/E1/E2 = 0. Each output plan
is byte-identical to that case's existing k4 direct-pilot plan. This is a
construction measurement and regression check, not another official run.

One additional `-X importtime ... --help` captured the real cold CLI import
graph without constructing a plan. The profile runs preload the official
module to install the guards, so their import cost is not a cold-process
measurement. All measurements are single observations on the shared Mac;
other sessions could use three workers. cProfile overhead changes timings.
Use these samples for attribution, not a speed claim or an exclusive-machine
comparison to Fang. No install, build, Colab, GPU, or network benchmark ran.

008's CLI and profile completed successfully, but subsequent metadata capture
used `platform.platform()`, whose processor lookup attempted `Popen` and was
blocked. The pstats and plan were already preserved. Only offline summary
generation was recovered, using `os.uname`; the construction was not rerun.
The unused elapsed-time value is null rather than reconstructed. The raw
profile's accounted duration remains available.

## Where time goes

Seconds below are cumulative cProfile time unless labeled otherwise. Parent
and nested rows **overlap**: the two `validate_graph` calls are already inside
initial indexing and final derive, and proposal calls are inside construction.

| Measurement | 008: word | 014: DAG | 025: DAG |
|---|---:|---:|---:|
| Eligible operations | 864 | 35,705 | 18,662 |
| Input bytes | 509,065 | 14,404,567 | 8,864,067 |
| Profile accounted total | 0.04857 | 2.44132 | 1.28744 |
| Read text, including config | 0.00115 | 0.00963 | 0.00826 |
| Decode graph JSON | 0.00245 | 0.03396 | 0.02171 |
| Initial full DAGIndex | 0.01554 | 0.55562 | 0.33506 |
| Base Index within DAGIndex | 0.01285 | 0.42826 | 0.26721 |
| Final official derive | 0.01570 | 0.85043 | 0.36593 |
| Both full graph validations | 0.01906 | 0.48813 | 0.30947 |
| All per-core proposals | 0 | 0.66609 | 0.38692 |
| JSON serialization, plans/ledger/stdout | 0.00168 | 0.06319 | 0.03363 |
| Existing unprofiled pilot outer wall | 0.19686 | 1.75525 | 0.94333 |
| Existing pilot internal wall | 0.01583 | 1.55770 | 0.74724 |

For 014, final derive accounts for 34.8% of profile time, proposals 27.3%,
initial indexing 22.8%. For 025 these are 28.4%, 30.1%, and 26.0%. JSON decode
and encode together are about 4.0% and 4.3%. Ordinary file reads are smaller.
There is no search over candidate algorithms: the router chooses once;
`propose` is the four-core placement comparison for each eligible operation
(142,820 calls on 014; 74,648 on 025).

The duplication is structural: `direct.py:54` validates, then lines 58–60 build
and contract the adjacency and topologically order it. Final
`derive_multicore_plan` validates the graph again at official stub line 116,
then repeats adjacency and contraction at lines 188–190. Its singleton
subgraph Kahn loop uses `ready.pop(0)` and `ready.sort()` at lines 211–218.
Callers in pstats place all 55,489 list-sort calls for 014 within derive,
costing 0.25558 seconds; derive's list pops add 0.02683 seconds. On 025,
derive's list sorts/pops cost 0.06647/0.00496 seconds. These sort totals include
both ready maintenance and its other list sorts, so they must not be labeled
as isolated ready-queue timings.

The single importtime sample totals 28.343 ms of self import time (excluding
unmeasured interpreter/argument work). Loading the P2 evaluator solely to use
`read_scene_b_config` adds a cumulative 11.112 ms including its P1/Step1–3
dependencies. This is worth removing for small graphs, but cannot explain a
second of large-graph construction time.

## An important timing boundary

Existing pilot outer minus internal wall is about 0.18–0.20 seconds for all
three examples. It cannot be assigned wholesale to algorithm initialization.
`evaluate_feedback.monitored` includes its process observer and cleanup in the
reported wall: cleanup performs four `ps` snapshots, followed by another
survivor snapshot before stopping the timer, even after normal child exit.
The internal timer also omits interpreter imports and the final ledger write.
The present measurements do not isolate the contribution of each omission.

For future benchmark protocols, record both observed child exit time and
cleanup completion time while preserving the current observer-inclusive
field. An equivalent externally timed process-to-plan measurement should be
used on both compared solvers. Do not rewrite old records or substitute the
internal timer for end-to-end solver time to manufacture a win. No runner
changes or new timings were made for this report.

## Lowest-cost next implementation

The following first stage retains the unchanged final official derive check.
Its output and tie-breaking invariants should be covered by exact byte
comparisons, with no new E0 required solely for identity verification.

1. **Hoist core-independent work out of `propose`.** For each ready operation,
   compute predecessor release, duration, pipe, and the ordered list of each
   input tensor's producing cores once before trying cores. During proposals
   the committed state does not change, so these values are identical for
   all candidates. Cache copy duration by size using the same
   `max(1, ceil(size / bandwidth))` expression; do not silently replace floating
   division with a supposedly equivalent integer formula.
2. **Reduce allocation per proposal.** Replace the three fixed traffic counters
   with three integers and reconstruct their diagnostic dict only for the
   chosen candidate. Scan cores in ascending order and retain the smallest
   complete `(end, added bytes, compute load, core)` score rather than retaining
   every proposal in a list. Preserve equal-score behavior. Keep sparse clock
   updates rather than copying a k-by-pipe state for every candidate.
3. **Lazily prepare tensor-specific DAG data.** Word construction needs the base
   Index, not the extra tensor-incidence tables and critical tails currently
   built by `DAGIndex.__init__`. Defer those extras until DAG build is chosen;
   do not construct a base Index and then reconstruct the same base again in
   a fallback DAGIndex. Cache a successful word descriptor, which is currently
   checked twice. Word-path savings in this sample are only milliseconds.
4. **Cheap startup/output cleanup.** Call the official
   `read_required_settings(config, 'multicore_scene_b',
   ('cross_core_copy_delay_cycles',))` directly, matching the current
   `read_scene_b_config` body without importing all evaluators. Serialize the
   plan once with the existing indent, key insertion order, Unicode policy and
   trailing newline; hash those bytes and write them to evidence and the
   exclusive `xb` output. This avoids two readbacks, not an existing double
   serialization. Preserve failure behavior and evidence.

A second, separate stage can remove repeated work by using a singleton-specific
structural certificate against the already validated immutable Index. It must
check exact node coverage, singleton map uniqueness, core coverage, and
same-core precedence order, while relying explicitly on the existing global
topological construction for acyclicity. The frozen official files stay
unchanged and external E0 still uses official derive. This changes the solver's
validation scope, so it requires separate tests and truthful ledger wording;
it is not merely a cache optimization or permission to drop validity checks.
Malformed input and a mutated graph/plan must not pass through a stale cache.

## Native boundary

Read-only inventory found Apple clang 21.0.0 (`/usr/bin/clang`, ARM64), C++ via
`/usr/bin/c++`, and Python 3.12.13. The project environment has NumPy 2.5.3,
SciPy 1.18.1, pandas 3.0.6, matplotlib 3.11.2; it has no installed numba,
Cython, pybind11, or orjson. Rust was not found in this shell's PATH. None were
installed, compiled, or imported to run a benchmark. Dynamic dictionaries and
heap choices are not naturally a vectorized NumPy kernel.

Do not port the evaluator to speed up a constructor that calls it zero times.
If the Python changes leave proposal/adjacency work dominant, the small native
boundary should take canonical integer arrays for the graph and return
ownership plus operation order. Python should retain input/config validation,
schema/JSON emission, evidence and final checks. A native implementation must
preserve sorted producer-core iteration, heap `(-tail, op_id)` ordering, all
score tie keys, ceil semantics, map insertion order, and validated integer
bounds; fast-math or unchecked int64 truncation would invalidate exact identity.
Count array conversion, cold library load and any per-input preprocessing in
solver wall; report compilation separately. Given k <= 5 and the measured
official-derive share, a proposal-only rewrite cannot eliminate the main
validation cost. No native speedup estimate is established by this profile.

The minimal next acceptance test is structural/byte equivalence on the same
three examples plus existing fork/merge, shared tensor, zero-byte, tie, and
unsupported-word tests. A separately frozen timing comparison then measures
whether it improved the real end-to-end objective. This diagnosis itself has
not implemented or validated any proposed optimization.
