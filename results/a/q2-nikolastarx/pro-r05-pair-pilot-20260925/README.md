# R05 saved-plan pair — frozen, no dispatch

The experiment compares the exact saved 003/K2 seed with the raw candidate
recovered from the original R05 metadata. It tests whether the static proxy's
rejection agrees with official Makespan, and records all movement categories.
It is a mechanism experiment, not a new online solver score or a full100 mean.
The current c665 003/K2 result is 245150 cycles, retained only as a separate
existing comparator. Both frozen plans will be independently evaluated.

`prepared.json` pins the final **capsule-v3.zip** (517312 bytes), controller,
worker and manifest. Earlier local v1/v2 packages were never dispatched and
are retained. Root review corrected portable paths, worker import setup,
duplicate call accounting, and the actual Colab cell entry semantics.
Syntax, cell import without `__file__`, entry dispatch with kernel argv, and
independent extracted-capsule preflight passed; none executes an evaluator.

Budget: one CPU Standard VM, one worker, seed then recovered, at most two
official E0 calls; each attempt is reserved before dispatch. Each call has
180 seconds, batch work 360 seconds, sampled process-tree RSS 4 GiB, output
file limit 64 MiB, zero retries. No solver construction or E2 call. Failure
stops the pair and preserves original error/partial files. `output/batch.json`
is the authoritative call ledger. The controller's setup status is separate.
An independent 10-minute VM stop guard and the coordinator's explicit window
are required before creating a runtime.

Upload the capsule to `/content/q2-r05-pair-20260925.zip`. Execute
`scripts/q2_r05_pair_colab.py` through the existing CLI with
`P2_R05_PAIR_MODE=run` and `P2_R05_PAIR_SHA256` from prepared.json. Results are
`/content/q2-r05-pair-20260925-results.zip`; verify downloaded bytes/hash before
stopping and independently reading back the session list. An observation
timeout is not permission to redispatch. This protocol does not authorize any
additional case or a full500 batch.

## Host dispatch entry, added after coordinator review

The frozen capsule above is unchanged. `scripts/q2_r05_pair_dispatch.py` is
the single-use host entry. Its SHA-256 is
`dbff87bbb45fd0e9006fce9c8de44fb0f4845241c626606c67a0f32c8ed0de66`.
The flag below records already-received exclusive admission; it does not
create that authorization. Do not run before the coordinator grants it.

```sh
python3 -B scripts/q2_r05_pair_dispatch.py --admitted \
  --capsule output/r05-pair-pilot-20260925/capsule-v3.zip \
  --out output/r05-pair-host-20260925-v1 \
  --pythonpath ~/.local/share/huaweicup2026/colab-cli-0.7.2-fork-f18e982c
```

The host verifies capsule and embedded cell identity, explicitly uses OAuth2,
and requires a recognized empty-session response. Before creation it records
T0/deadline and arms a detached watchdog with an absolute 600-second deadline.
The wrapper provides both required cell environment variables. A workload
failure still triggers one attempt to retrieve the original archive, then
stop and fresh session readback. Unknown calls remain unknown without the
worker ledger. Completion requires successful workload evidence and proven
stop; unproven stop retains the watchdog. Each command is bounded by the
remaining deadline, with 60 seconds reserved after the workload for evidence
retrieval and cleanup. The watchdog stop request itself has a 25-second
network timeout; a request is not proof of remote termination.

`tests/test_q2_r05_pair_dispatch.py` covers stop failure, readback failure,
strict empty-response parsing and wrapper variables, corrupt batch evidence,
and successful release using synthetic commands only (five tests). Combined
with seven ready-exchange tests, 12 focused tests passed. This does not claim
the host entry has completed a live run. `host-receipt.json`, command logs,
watchdog log and downloaded `result.zip` are written to the new output folder.
