# P2 r05 — ready-frontier matching with exact tensor reuse

## Scope and provenance

This is a new, unscored construction prototype, not a result on case 003.
No official Step1/Step2/Step3/E0/E1/E2 was run here. The project adapter was
syntax checked, but NOT run in the complete user repository. The standalone
core was tested on synthetic integer models.

Read from authorized Vioano/huaweicup2026 at
`28818874e5e0306793427526c8612383a9397363`:
- `docs/a/q2-nikolastarx/PRO_R04_REVIEW.md`, full text;
- `src/q2_nikolastarx/gap_corridor.py`, full text with continuation;
- `results/a/q2-nikolastarx/pro-r04-review-20260925/static-003-k2/result.json`, full text;
- `src/q2_nikolastarx/gap_calendar.py`, full text;
- `src/q2_nikolastarx/gap_candidate.py`, full text.

The two gzip seed files were located via directory metadata, not decoded here.
The user's newer 12,774-overlap / 11-block / 16,384-byte statistics were not
recomputed here. The fixed-domain theorem and synthetic auditor are conditional
on complete and correct input interval/lag/hyperedge data.

## What changes

Discard old starts and low-slack groups. Split old nonbranch chains at Pipe
changes. Each resulting phase packet stays on one core, but different phases
of an old chain may change cores. Reconstruct a fresh schedule from ready
antichains, retaining M/V calendars independently. A batch is a placement
transaction, NOT a submitted execution barrier.

All unscheduled packets keep a tentative seed owner. This makes every local
byte comparison an exact comparison between two complete tentative ownerships,
not a guess about unknown future consumers.

Select at most one ready packet per tentative source core. Assign them
injectively to destination cores. Once all batch pins are removed from each
physical net, the exact connectivity cost is a constant plus the sum over
packet/core edges of the net weights whose fixed pins do not yet touch that
core. Injectivity is essential to that linearization.

Use the seed's horizon recomputed under a COMMON operation-edge-lag / compute-
FIFO model as a per-core/per-Pipe total-work cap. Because only one packet enters
a core in a batch, these caps become exact edge eligibility tests for that batch.
They are NOT full dependency, memory, or Makespan guarantees.

For each eligible packet/core edge, the existing persistent calendar supplies
a trial completion and a data-only tail. Among injective matchings whose exact
bytes do not exceed the reference matching, minimize the largest completion-
plus-tail, then exact bytes, then number of changed owners. A threshold test is
an integer Hungarian assignment. Binary search is over at most k squared
computed breakpoints; no assignment permutations are enumerated in production.

Local horizon nonincrease does NOT imply global horizon nonincrease. At the
end replay both complete plans in the same model; return the new one only for
weak Pareto improvement (one strict) in model horizon / pre-Step2 bytes.
Otherwise return the original seed. This last gate is a construction heuristic,
not a safe exclusion theorem about official schedules.

## Project integration

Copy these three new files into `src/q2_nikolastarx/`:
- `ready_exchange.py`
- `calendar_avl.py`
- `ready_exchange_candidate.py`

Entry points:

```python
from src.q2_nikolastarx.ready_exchange_candidate import build, build_from_seed

# Standard constructor; internally builds the gap seed once, then reconstructs.
plan, detail = build(graph, cores, config)

# Mechanism test with an ALREADY-loaded seed and in-memory witness from the
# verified build_with_witness contract. No old timestamp is used by repair.
plan, detail = build_from_seed(graph, seed_plan, witness, cores, config)
```

The adapter calls `derive_multicore_plan` and `mandatory_copy_work` for structural
and byte consistency. Neither is an official score. The adapter intentionally
requires integral bandwidth and M/V operations; its build entrypoint returns
the seed when the new guard rejects, and skips reassignment at one core. It retains the source guard
against contracted-only execution relations.

It never reads historical winner tables, chooses a case by ID, or calls E2.
The caller retains responsibility for final E2/E0 validation and whole-solver
wall-clock accounting. If an existing baseline-plus-candidate two-evaluation
contract is retained, the unscored raw gap seed is NOT additionally protected
against official-score regression without a third evaluation or a changed
contract. No hidden third evaluation is performed here.

## Fixed-domain audit

`fixed_domain_audit.py` is a diagnostic, not an alternate candidate generator.
It forms the complete two-core fixed-start flip components from low-slack
constraints and strict same-Pipe interval overlaps. It computes the invariant
byte lower bound, and tests its attainability by solving parity equations that
would make all noninvariant positive nets monochromatic. A failed parity test
does not invalidate the bound; it means the bound cannot all be attained at once.
No assignment enumeration occurs in the auditor.

The completeness claim is ONLY for fixed units, fixed positive-duration operation
intervals, every represented symmetric static lag, identical cores, and no
additional pinned-core restrictions. Use actual per-operation intervals, not
unit convex-hull spans. Input nets, direct-edge nets, boundary constants and
zero-byte timing dependencies must not silently be omitted.

## Tests

```sh
python test_ready_exchange.py
```

The test oracle deliberately enumerates ONLY tiny synthetic matchings / flip
vectors, outside the constructor. It checks integer Hungarian optimization,
byte-budget bottleneck optimization, exact batch linearization, the fixed-domain
characterization and lower-bound attainability, one-pass reconstruction, and
same-Pipe packets.

`retiming_fixture.json` and `retiming_mixed_fixture.json` were found in bounded
synthetic model exploration and then frozen as mechanism examples. They are not
blind holdouts, official configurations, or performance estimates. In both,
all fixed-start variables form one block and fixed-domain byte improvement is
zero, but reconstruction changes starts and reduces bytes without increasing
the common model horizon. The mixed example goes from 32 to 16 variable bytes,
and model horizon 52 to 48. Boundary constants are omitted in that toy model.

`test_wall_seconds` measures this tiny standalone test script only, not the
actual solver, seed construction, adapter integration, or evaluator.

## Low-cost stopping and limitations

Exactly one forward pass; no convergence loop, window-width sweep, or repeated
plan scoring. Hungarian's primal/dual optimization supplies the local optimum.
If the whole pass does not produce model Pareto improvement, return the seed.
The caller may impose a wall deadline and retain the already constructed seed.

This is NOT globally optimal under the byte budget. Dependent packets in
different batches can require a temporarily byte-worsening relocation to
realize later reuse; those paths are excluded. Injective batches also cannot
optimize arbitrary many-to-one bin packing. Read-only input reuse is modeled
exactly in bytes but not in reload timing. Outputs, COPY FIFO, spill, and
memory-credit effects are left to the official pipeline. Neither exact byte
improvement nor a model-horizon improvement proves an official speedup.
