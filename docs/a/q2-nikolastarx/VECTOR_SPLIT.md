# Controlled half-lane transfers: experimental constructor

`src.q2_nikolastarx.vector_split` is a new, separate candidate. It does not
change the `b7c05cf2205bd42ec23680e618a10796b37562f6` unified algorithm currently
handed to s59ee for all 500 benchmark coordinates. It uses no case IDs, stored
scores, evaluator calls, random choices or candidate scoring loop.

## Reason to try this change

In a homogeneous all-V fork–chain–reduce stage, keeping every chain on one core
can waste a substantial fraction of available compute capacity. For 12 chains,
4 operations per chain, 524 cycles per operation and 5 cores, whole-chain
placement requires at least one core to do 12 operations: 6288 cycles. Ignoring
communication and reducers, the unrestricted operation-work bound is only
`ceil(48/5)*524 = 5240`. This gap concerns a restriction on the placement, not
proof that the official graph can reach 5240 cycles per stage.

The candidate allocates q whole chains to each core, where `n=qk+r`, then splits
the remaining r chains in half across r distinct sender/receiver pairs. Senders
execute their half first; receivers execute their half after their q whole
chains. A remaining core runs the fixed scalar reduction tree in a ready order.
All ownership repeats across stages, including ownership of external L1 inputs.
The constructor requires q≥1, `0<2r<k`, equal positive chain sizes, equal even
chain length, and equal effective compute durations. Existing vector recognition
guards tensor incidence, single producers, external boundaries and stage coverage.

In the 12-by-5 example, the chain workloads become 10,10,10,10,8 operations.
The sender's first half ends at 1048 and the receiver needs it at 4192, leaving
3144 cycles for transfer in an equal-release ideal model. The frozen 32768-byte
COPY pair has an uncontended minimum lag of 1594 cycles. Two pairs' total
rounded service plus one 500-cycle delay is 2688 cycles in an isolated model;
this is **not an upper bound for the official run**. Boundary loads, broadcast,
shared bandwidth, COPY FIFO head blocking and Step3 allocation edges matter.

## Important counterexample to generalizing the ideal claim

Equal halves do not always attain even the relaxed work bound. With n=16,
k=7 and chain length 8, the candidate's maximum load is 20 operations, whereas
`ceil(128/7)=19`. Thus communication hiding alone is insufficient for a general
optimality claim. The 12-by-5 arithmetic is a special parameter condition. The
new synthetic test records this counterexample, rather than labeling the method
optimal over its accepted domain. Pro r02 has been asked to prove or refute
such extensions; its response is still pending.

## Evidence and cost boundaries

The returned fixed-plan lower bound includes the retained original tensor
dependencies, submitted V FIFO edges, and minimum cross-core COPY lags. It
checks acyclicity but excludes bandwidth sharing and added memory dependencies.
It is not a bound over alternate assignments or an official execution trace.
The original compute-touch residency report also excludes inserted COPY and
spill; it must not be cited as a zero-spill certificate.

For 016's 305 stages, the proposed two large cuts per stage add 39,976,960 bytes
of large-vector COPY traffic before scalar traffic or spill. Compare this
explicitly against achieved whole-chain solutions' much smaller movement. A
Makespan win would not imply an across-metric Pareto improvement. Preserve the
existing solution when recording this alternative; do not silently replace the
full-suite frozen constructor.

Six synthetic tests passed on the local Python environment in 0.032 s, with
subprocess and official evaluation entry points poisoned. They cover the exact
crossing count, persistent input ownership, sender/receiver ordering, one
ideal timing instance, the generalization counterexample, adverse resources,
unsupported inputs, determinism and the zero-call/no-overwrite CLI. Command:

```text
.venv/bin/python -B -m unittest tests.q2_nikolastarx.test_vector_split -v
```

At this document's first revision, there has been **no original-case E0 run**
for this candidate. One static 016/k5 construction, followed by at most one
separately frozen E0 pilot, is sufficient to test the proposed mechanism.
Those must use their own source/runner/protocol identities and must not fill a
cell of the existing b7 unified benchmark. First failure stops; no implicit retry.

The algorithm is linear in original incidences apart from heap-based tree
ordering and topological validation: O((N+E) log N + kN) with current small-k
tree ready selection, O(N+E+k) working storage plus returned evidence. It does
not enumerate placements, split positions or candidate combinations.
