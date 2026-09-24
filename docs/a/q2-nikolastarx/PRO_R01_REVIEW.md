# Pro r01: five conclusions that change P2 development

Reviewed on 2026-09-25 from the complete locally archived
`AI chats/20260924-P2-异构流水与最优性界/r01-response-c800fcd4.md`, and the frozen
official P2/Step2/Step3 sources. The linked ZIP/report/prototype bytes were **not
read or executed by this review**. Pro's test counts remain author reports.
This review adds 0 E0/E1/E2 calls and changes no algorithm. A nested agent
independently checked the prefix-DP/lowering part, also read-only.

## 1. Accept the independent, unconstrained MVM result; do not extend its guarantee to our two current graphs

The normal-form proof is sound for independent nonpreemptive jobs
`A_i=M(a_i) → B_i=V(b_i) → C_i=M(c_i)`, with all jobs available initially,
no other dependencies, no capacity restriction, and no COPY costs. Swapping an
adjacent `C_i,A_j` on M can move A_j earlier without invalidating any predecessor;
C_i can move later because it has no external successor. Repeating puts all A
before all C. For a fixed V order, inversion exchanges align the A and C orders
to it: moving the earlier-needed A forward cannot hurt that V sequence, and
the aligned C order has nondecreasing release times. Hence one job permutation
contains an unconstrained optimum.

For that domain, the stated H recurrence/formula is correct. The two-Johnson
argument also checks out: deleting C or A gives the two-machine relaxations;
`min(H_AB,H_BC) ≤ OPT + min(sum a,sum c) ≤ 3OPT/2`. This is an independently
understandable guarantee, not a claim about the cited 4/3 algorithm, which this
review has not inspected.

The safe-drain guarantee needs the stated invariants: preserve the seed A/B/C
orders, test actual **ideal-model** readiness of the next C, preserve all remaining
A deadlines, and do not idle M while an A remains. Backward V deadlines ensure
each B_i finishes by the seed C_i start z_i. After the last A, M's elapsed work is
`sum a + sum already-drained c`, no later than the corresponding seed prefix;
induction on the remaining C operations proves no worse ideal completion. It
does **not** minimize memory or prescribe official start times.

Capacity is a real restriction, not a minor omission: two `(1,2,1)` jobs with
one unit of residency each have unconstrained optimum 6, but capacity one forces
serial completion at 8 and forbids the all-A-first form. Shared tensor lifetimes
are not the constant-q job model either. Treating a V* chain as one uninterrupted
B is additionally a restriction unless a separate equivalence proof is given.

**Current impact:** 016 is entirely V, with successive fork-join regions; 062
has four/eight M visits in a leaf chain and reduction successors. Neither is
an independent terminal M–V–M job instance. These formulas are useful guarded
constructors for genuine independent chains, not a replacement for the current
016/062 mechanisms or an official approximation guarantee.

## 2. The homogeneous exact formula is credible; the improvement is an ideal certificate, not new official performance

For identical `(a,b,c)`, maximizing the normal-form path expression yields
`max(n(a+c), a+b+c+(n−1)max(a,b,c))`. For symmetric M visits this becomes
`max(2an, nb+2a)`. The existing word with `h=1+ceil(b/a)` attains it for
`0<b≤2a`, including the short n<h cases.

A compact independent check of the nontrivial h=3 branch: for `a<b≤2a` and
n≥3, until the last A, M never idles; `finish(A_i)=(2i−3)a` for i≥3. The ideal
V finishes obey `finish(B_i)=max(a+ib,(2i−3)a+b)` for i≥3. The final three C
operations then finish at `max(2na,nb+2a)`. In the h=2 branch (`b≤a`), M is
continuous for n≥2 and finishes at 2na; n=1 is simply 2a+b. Thus the body of the
answer can be supplemented without relying on its unavailable attachment.

An independent tiny DAG enumerator written for this review, not Pro's code,
checked five inputs with n≤3. Full acyclic M/V FIFO enumeration and complete
normal-form enumeration agree:

| Jobs | Acyclic FIFO pairs | Optimum in that ideal model |
| --- | ---: | ---: |
| `(1,1,1)` | 1 | 3 |
| two `(1,2,1)` | 10 | 6 |
| `(1,1,4),(1,1,1),(1,4,1)` | 342 | 9 |
| `(5,10,5),(5,10,5),(1,1,1)` | 342 | 31 |
| `(4,1,3),(1,5,2),(2,2,1)` | 342 | 13 |

Another 36 ideal word checks used `a∈{1,2,3}`, integer `1≤b≤2a`, n∈{1,2,3};
all match the symmetric formula. These bounded checks support implementation
interpretation, not the general proof or official success. They spend no
official evaluation budget. No inference is made about COPY, spill, finite
capacity, or the optimal distribution of jobs across cores.

## 3. Adopt the fixed-compute-FIFO longest-path bound, with the correct graph and replacement rule

For a **singleton** candidate whose original compute FIFO is fixed, let D_exec
contain only dependencies proved to survive P2 reconstruction. Add adjacent
eligible operations of each `(core,pipe)` FIFO and compute the weighted longest
path using `max(1,cycles)`. Every successful execution respects those edges;
therefore this is a candidate lower bound and is at least its assigned-Pipe
work bound. It is not a lower bound over other ownership/order choices.

The source support is concrete: singleton ranks determine relative eligible-op
order in P2 `_prioritize_task_seq` (43–59); Step2 `seq_ext` keeps that order
(443–456); Step3 projects `seq_ext` on each Pipe (279–289); final P2 enforces
those Pipe heads (381–412). Intermediate COPY/spill operations cannot shorten
the resulting compute chains. A non-singleton mapping does not allow us to
assume an arbitrary user-chosen order inside its bucket.

Do not substitute D_val. The already documented synthetic example
`A(M,10) → original COPY_OUT → B(V,10)` with no tensors loses both direct
edges in P2 reconstruction (209–213), although plan validation contracts A→B.
The resulting independent compute tasks can have time 10; charging a contracted
20-cycle path would be invalid. For the frozen 100 graphs, the prior audit found
no such extra contracted-only edges and at most one eligible tensor producer;
retain those explicit checks instead of generalizing them to all legal inputs.

**Pruning policy matters:** `L≥incumbent` is valid only when the replacement
rule accepts strict Makespan improvement. If an equal-time plan with less DDR
may replace the incumbent, equality cannot be discarded on this bound alone.
Cycles in the constructed graph indicate inconsistency only after its retained
edge assumptions have been established; do not turn an unproved edge into an
“official invalid” label.

## 4. The two-prefix DP is exact for a specified raw model; singleton COPY lowering is the missing useful lemma

For a fixed complete tensor/op graph and two fixed FIFO words, `(i,j)` uniquely
determines the visited set S. In the **Step2 first/last-touch sequential model**, a
tensor is resident after a prefix precisely when it has been touched and still
has a later touch. A transition allocates every newly first-touched managed
tensor before releasing last-touched tensors. This includes graph inputs and
dead outputs; “only allocate outputs” is insufficient for this model.

Future residency is determined by S, so minimizing the maximum scalar peak via
one label per state is valid. With separate L1/UB capacity constraints, exact
feasibility is a reachability problem that checks both budgets. Simultaneously
minimizing both unconstrained peak coordinates instead requires nondominated
labels; one arbitrary weighted sum does not provide that vector optimum.

Fixed **compute** FIFO alone does not fix COPY FIFO. A minimal static example:
M word `[A,C]`, V word `[B]`, only compute dependency `B→T→C`. UB input X→A is
4 bytes; Y→B is 1 byte; A's final output a is 1 byte; T is 3 bytes; C's final
output c is 1 byte. Singleton order A,B,C expands to input/calculate/output
buckets with raw peak **5**. Order B,A,C keeps the same compute FIFOs but holds
T while loading X and allocating a, giving peak **8**. Its input COPY order
also reverses. These are hand-derived raw peaks, not E0 outcomes.

There is a promising exact extension rather than a reason to abandon two
dimensions. With **fixed ownership and singleton mapping**, the P2 base Task's
COPY nodes/edges and Step1 raw order are fixed; their **subgraph bucket** changes:
an input/COPY_IN belongs to the earliest local consumer, an output/COPY_OUT to
the latest local producer. For a compute-prefix set S, the former has entered
the expanded prefix iff at least one local consumer is in S; the latter iff
all its local producers are in S. This defines an expanded set U(S).

A DP transition can therefore expand all newly entered bucket operations in
the fixed Step1 relative order and check every raw alloc-before-free instant,
while retaining state `(i,j)`. This needs a formal lowering lemma and focused
tests for shared inputs, local DDR→UB conversion, synthetic direct-edge tensors,
first/last bucket selection and complete coverage. Pro's answer points out the
COPY issue but does not supply that implementation or proof. If one instead
freezes all four independent FIFO words, the naïve state count is their prefix
product; it is not automatically quadratic.

Even an exact local zero-spill Step2 DP does not establish final multicore
execution validity or minimum official Makespan: Step3 memory-reuse edges,
cross-core COPY release and MTE head blocking remain. Step3's free-credit queue
also stores **which** earlier readers/writers released each byte (144–183).
Two histories can have the same visited set, zero current residency and the
same maximum peak, yet leave different credit-source histories and hence
different future WAR/WAW edges. A single `(i,j)` peak label is not sufficient
for optimizing that extended execution objective. Nor should a full 062
`(8728+1)×(10908+1)` grid (about 95 million states) be launched casually. Start
with a structurally bounded region or count exact reachable states; beam pruning
changes an exact certificate into a heuristic and must be labelled.

## 5. The new six official results select the next questions; they do not validate every Pro claim

This review read the existing compressed final result JSONs under
`results/a/q2-nikolastarx/{vector,tree}-pilot-20260924/run/`; it did not rerun them.
All six report zero spill:

| Candidate | k2 Makespan | k4 Makespan | k5 Makespan |
| --- | ---: | ---: | ---: |
| 016 complete vector lanes | 4170750 | 2552270 | 2243707 |
| 062 tree frontier | 1514488 | 1008337 | 673563 |

016 has only 4876/12188/12184 extra DDR bytes, yet its k4 result is about 13.4%
slower than the prior 2250687; k5 is slightly slower too. Thus zero spill and
low transferred bytes are demonstrably insufficient objectives. The fixed
500-cycle cross-core release and the scalar reduction/broadcast critical path
are specific mechanisms to inspect next in the existing trace. This is a
hypothesis to measure, not a causal attribution already proved by the totals.

For **016**, all eligible operations are V. Once that compute FIFO is fixed,
there is no second compute word to interleave, so the proposed M/V-prefix DP
has one path and cannot improve it. Useful changes would alter scalar ownership,
the reduction/V order, or lane placement—each changes the fixed object being
optimized. Preserve the true stage lower bound separately from the whole-lane
restriction, as in `TREE_FRONTIER_THEORY.md`.

For **062**, distinct M/V words do permit alternate compatible priority
linearizations, as the static example shows. However the new tree candidate
already has zero spill and low measured raw/Step3 peaks; finding an even smaller
memory peak alone is unlikely to be the right target. First use fixed-FIFO
longest-path and existing trace evidence to distinguish compute-Pipe idle gaps,
piece-load imbalance and COPY/allocation ordering. Then choose one concrete
word/order change. Do not apply independent-MVM guarantees to the tree, or add
a large exact memory DP merely because it is mathematically available.
