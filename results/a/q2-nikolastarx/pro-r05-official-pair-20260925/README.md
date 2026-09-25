# R05 saved-plan official pair: negative quality result

The one admitted 003/K2 comparison completed on a CPU Standard Colab runtime.
Both frozen plans were evaluated once by unmodified official E0. There was
no new construction, E1/E2 call, retry, parameter search or full-grid run.

| Plan | Official Makespan, cycles | Scheduled COPY, bytes | Spill COPY, bytes |
| --- | ---: | ---: | ---: |
| Old R05 seed | 248166 | 6351422 | 0 |
| Recovered raw candidate | 254508 | 5207554 | 0 |
| Existing c665 comparator, previously evaluated | 245150 | 4262874 | 0 |

Against its old seed, the candidate saves **18.00964%** of scheduled COPY
bytes but increases Makespan by **2.55555%**. It is also **3.81725%** slower
than the current c665 plan. The existing static proxy rejected it; this
official result does **not** reveal a false rejection for this candidate.
It does not validate proxy rejection for other candidates or graphs.

The fixed compute-FIFO necessary bounds were 230755 and 240126 cycles.
Arithmetically, the official change decomposes as `+9371 - 3029 = +6342`:
the bound increases by 9371 while the difference between E0 and that bound
shrinks by 3029. This difference is a relaxation residual, not measured DDR
stall time; the decomposition alone does not assign causal delays.

## Evidence and scope

- Host source: `afabca83ffa941f988cae0680a4d99760018d580`.
- Unchanged capsule source: `7c9b648dfaad134215fcc09c0a3258861cdd4c72`;
  capsule SHA-256 `c0d25765b29f8958ebc93c3ef39fdae76179b26963835745052d8abfa05a0a74`.
- The full downloaded `result.zip` is **2835556 bytes**, SHA-256
  `c90065d9d90aae3be4144080483e3ac394a6ef150f92fc7d4450d81114ba2c66`.
  This matches the remote completed-cell declaration. All 23 ZIP members
  passed CRC and were hashed; both result/Trace JSONs parsed. Frozen plan,
  result and manifest identities, B/2-core identity, both process exits and
  movement metrics were independently checked. See `verification.json`.
- The ZIP preserves original plans, official results, Traces, logs, process
  receipts and environment setup logs. `batch.json` and `preparation.json`
  are byte-identical convenience copies of their ZIP members.
- Both E0 processes exited 0, with no surviving children. Reserved/completed
  E0 attempts: 2; E2: 0; retries: 0. Worker batch wall was 21.279 seconds;
  setup was separate (uv bootstrap 5.496 seconds, locked sync 6.434 seconds).
  These are evaluator experiment costs, not online solver timings.
- T0 before creation: `2026-09-25T04:54:48.715344Z`.
  E0 seed ran `04:55:19.422074Z`–`04:55:30.214935Z`; recovered ran
  `04:55:30.351135Z`–`04:55:40.571930Z`. Sampled worker RSS peaks were
  238596096 and 231235584 bytes, below the 4 GiB limit.
- Host stop and session readback both exited 0; a later fresh sessions query
  showed no active sessions and usage showed active assignments 0. The
  detached watchdog was terminated only after proven stop and is gone.
  Host/command logs, fresh readbacks and the original receipt are included.
  Upload/download host log paths are redacted derivatives; original local
  and published hashes are recorded in verification.json. The remote ZIP
  remains byte-for-byte original.

## Consequence for the next algorithm

Do not install this raw plan or describe its byte saving as a score gain.
The next reconstruction should begin with the online caller-selected current
plan, and jointly inspect compute/FIFO serialisation and movement rather than
assuming that fewer bytes will win. The new singleton-packet adapter provides
that entry, with synthetic tests only; it has no official improvement yet.
The current c665 full500 score is unchanged. No additional resource window,
retry or batch is implied by this completed experiment.
