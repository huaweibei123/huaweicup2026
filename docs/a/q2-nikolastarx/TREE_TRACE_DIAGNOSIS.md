# 062 tree trace: change the compute words before optimizing their interleaving

2026-09-25. Read-only diagnosis of the three existing official results under
`results/a/q2-nikolastarx/tree-pilot-20260924/run/`. No solver, candidate,
compiler, E0/E1/E2, or new performance experiment was run for this diagnosis.
The scripts, complete witness paths, hashes and per-core/pipe/packet records are
in `results/a/q2-nikolastarx/tree-trace-diagnosis-20260925/`.

## Main finding

The saved candidate already has zero spill. Its fixed **compute FIFO** lower
bound is within 0.5% of actual Makespan for every tested core count. Therefore a
large two-prefix DP that preserves those M/V words has almost no performance
headroom. The useful next change is the words themselves: delay skeleton joins
until each core's independent complete packets have been submitted.

| cores | official Makespan | max assigned compute-Pipe work | fixed compute-FIFO lower bound | maximum improvement preserving compute words |
|---|---:|---:|---:|---:|
|2|1514488|1388400|1513704|784 cycles / 0.0518%|
|4|1008337|774000|1005132|3205 cycles / 0.3178%|
|5|673563|614400|670344|3219 cycles / 0.4779%|

These are candidate-specific bounds. The bound uses original eligible tensor
producer-to-consumer edges and adjacent eligible ops on each `(core,pipe)` word,
weighted by `max(1,cycles)`. It assumes singleton mapping, fixed ownership and
fixed words, and deliberately ignores COPY time/delay/memory. On this graph,
all eligible dependencies are single-producer tensor edges retained by P2. The
script checks the submitted words exactly match observed compute-Pipe order.
Thus every valid execution with these same words respects the bound. This is
not a bound over different ownership or FIFO choices.

The finding directly applies the restricted fixed-FIFO result reviewed in
`PRO_R01_REVIEW.md`; it does not apply independent terminal M–V–M guarantees to
062's four/eight-M-visit chains with reduction successors.

## Loads, idle cycles and piece imbalance

Total original M work is 2618400, so the fractional balanced M-work references
for k2/k4/k5 are 1309200/654600/523680. Max assigned M work is respectively
6.05%/18.24%/17.33% above those references. These ratios quantify ownership
imbalance, not attainable official speedups.

| k | core | M work | V work | M idle before its last completion | core final completion |
|---|---|---:|---:|---:|---:|
|2|0|1230000|184500|111050|1514488|
|2|1|1388400|208188|125366|1513900|
|4|0|615600|92232|55876|671878|
|4|1|774000|115992|70120|844261|
|4|2|614400|92268|392339|1008337|
|4|3|614400|92196|391585|1007713|
|5|0|466800|69912|42527|509513|
|5|1|462000|69300|210382|672903|
|5|2|614400|92052|57013|671727|
|5|3|614400|92052|55811|672315|
|5|4|460800|69372|211678|673563|

The diagnostic JSON also gives MTE2/MTE3 duration sums, first/last timestamps,
all four Pipe idle gaps, and full-run utilizations. DDR duration sums are actual
elapsed busy cycles under shared bandwidth, not bytes/60 or a global traffic
bound. Pipe idle cannot be summed across pipes/cores to obtain removable
Makespan; many idle intervals overlap useful work elsewhere.

For k2, core1 has two 512-leaf packets plus the 133-leaf remainder; core0 has the
other two large packets. Core0 becomes fully idle at 1341482 until the final
remote result arrives at 1514400. This is mostly assignment/remainder imbalance,
not a premature skeleton blocking another local packet. The fixed FIFO path
contains 1387200 M cycles and 126504 V cycles: closed leaf-chain execution also
retains many of the intra-chain 36-cycle waits between 300-cycle M visits.

For k5, two cores receive four roughly 128-leaf packets while the other three
receive three. Core2/core3 have 614400 M cycles, versus roughly 461000–467000 on
the others. Both assignment imbalance and early-join blocking remain. Core1 is
fully idle 338197–504803; core4 is fully idle 168227–337379. Eliminating their
waits alone does not remove the heavier cores' work.

## k4: a directly observed unnecessary serialization

All four cores finish their first complete packet near 335584. Core1 then
executes a second packet; cores2/3 have independent second packets, but their
submitted order inserts skeleton joins before those packets.

| core | relevant order | all-Pipe idle window | independent work delayed |
|---|---|---|---|
|3|packet23984, join23992, packet23988|335584–670982 = 335398 cycles|packet23988 starts compute at671137|
|2|packet23983, join23991, join23995, packet23987|336172–671596 = 335424 cycles|packet23987 starts compute at671891|

Trace sequence for core3:

1. Its packet23984 ends335584. Join23992 needs core1 packet23985, whose root ends
   670456; COPY_OUT1000037089 ends670482.
2. The required remote COPY_IN1000037090 waits the fixed500, then executes
   670982–671008. It is the current MTE2 FIFO head.
3. The graph-input COPY_IN1000034506 for independent packet23988 follows that
   head and can only execute671008–671034. Its first compute15371 starts671137.

Trace sequence for core2:

1. Join23991 finishes336172. The next skeleton join23995 requires core3
   join23992, whose COPY_OUT1000037101 finishes671096.
2. COPY_IN1000037102 executes671596–671659. Packet23987's first input
   COPY_IN1000033482 then executes671659–671711; compute12811 starts671891.
3. Packet23987 finishes1007063. The final skeleton crosses back through core3
   and returns to core2, ending with the graph output at1008337.

The original graph confirms those packet first ops have graph inputs and no
compute dependency on the preceding skeleton joins. Packet subtrees are disjoint
and closed. The official `queue_if_ready` accepts only the current Pipe cursor
head; `advance_pipe` advances only after that head completes. The latter
independent input cannot bypass the remote COPY_IN. The V FIFO also puts the
join before later packet RELUs, so merely changing M/V *linearization while
preserving their words* cannot solve this, as the lower bound confirms.

Some transfers are released early but start late: tensor1000028347 (0→2) is
released337454 but starts987755, a650301-cycle interval. This includes useful
prior packet execution and possible memory-dependency wait; it is not650301
removable idle cycles. Full memory dependency edges were not recorded, so the
diagnostic does not claim to identify every individual stall's complete cause.

## Reproducible critical-path witness

The analysis additionally reconstructs only known tensor COPY incidences from
singleton buckets, official sorted tensor IDs, and recorded COPY IDs; it does
not invoke Step1/2/3. It adds every recorded Pipe FIFO edge and cross-core
release edges with500-cycle lags. Every reconstructed edge is checked against
the actual source-end/target-start timestamps, and all24003/24015/24027 op records
in trace and result are checked one-for-one.

| k | same-all-Pipe-word bound with isolated COPY durations | known-constraint longest path with recorded DDR durations | actual Makespan |
|---|---:|---:|---:|
|2|1514385|1514488|1514488|
|4|1007836|1008337|1008337|
|5|672892|673563|673563|

The last path is a **posthoc witness**, not a predictive evaluator or a bound
transferable to other schedules: its COPY durations include the observed shared
DDR contention. Its equality shows a recorded-time tight chain can be traced
using only retained dependencies, FIFO and cross-core release, without adding
unobserved memory dependencies to that witness. Other operations do exhibit
readiness residuals, so this does not prove memory dependencies irrelevant to
every operation or to a future candidate.

The k4 witness crosses cores1→3→2→3→2. Its totals are M921300 + V84096 + MTE2785
+ MTE3156 + release lags2000 =1008337. It passes through core1 packets23982 and
23985 before core2 packet23987: this serializes roughly three large packets
along one critical chain despite four available cores. The full ordered op-ID
path, incoming-edge kind, duration and actual timestamps are saved in
`062-k4-paths.json`; k2 and k5 have matching files.

## Next bounded construction and what remains afterward

First keep the exact pieces, ownership and internal packet order. For each core,
place every complete packet before skeleton nodes, retaining a common topological
order for the skeleton. No packet needs a skeleton predecessor, so this preserves
original dependencies while changing the problematic V/COPY words. The exact
cut count, graph-input replication and compute work stay unchanged. The cost is
retaining packet-root tensors longer; calculate raw per-pool peaks and retain
E0 validation rather than asserting zero spill. This is a single structural
change suitable for a three-cell comparison, not a parameter grid.

After isolating that effect, ownership granularity is a separate question. Fixed
W/(2k) binary subtree sizes leave a heavy-core remainder, especially k4/k5.
A future deterministic frontier partition could split only overloaded complete
subtrees at low-byte reduction edges and balance exact M work, with an explicit
cut budget and no score search. This changes ownership and should be measured
separately from the words-first change.

Finally, a bounded two-leaf pipeline inside one packet could overlap a36-cycle
RELU with the next independent300-cycle M, rather than closing one entire leaf
chain. Its guard must cover the private-input unary chains and retained reduction
outputs; the existing independent MVM theorem is insufficient. This is a later
proposal, not a constructed or evaluated algorithm. Neither this proposal nor a
95-million-state memory DP is needed before testing the diagnosed FIFO change.

Independent read-only review by `review_dag_constructor` confirmed the concrete
k4/k5 head-blocking intervals and their source graph independence. It executed
no solver/evaluator and did not modify the diagnosis files. Root controls the
next candidate freeze and official evaluation budget.
