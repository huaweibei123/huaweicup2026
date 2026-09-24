# P3 repeated fork/join: finite migration and an exact compute-model optimum

## Scope and provenance

This package contains no official E0/E1/E2 evaluation. It changes original operation ownership and singleton priority lists only. It never splits an operation, re-associates an ADD tree, changes an input graph, or submits timestamps.

Repository source basis: `huaweibei123/huaweicup2026`, commit `16cf6f59aae69fe8bfd2f32e89bb823eaabb20f9`.

The original `case_051.json` was read from the already-mounted contest attachment. Its raw SHA-256 is `884e8b12ac1f7a9b569958909680e8c2f6055966a59c9f929ffd5cee48aae43b`, matching `results/a/q3-nikolastarx/stage-20260924/INDEPENDENT_READBACK.md`. The mounted case024 and case016 raw bytes were hash-checked against that report but not independently evaluated or fully structurally parsed in this package.

The exact original first-stage lane IDs and original ADD edges are in `first_stage_structure.json`. Original ADDs 61..71 correspond to J0..J10: pairs 01,23,45,67,89,10-11; groups 0-3,4-7,8-11; group0-7; final root. No tree edge is synthesized or re-associated.

## Files

- `stage_migration.py`: proposed repository integration module. Copy into `src/q3/`. The public `construct` first calls the existing exact tensor-port recognizer and additionally checks the proved shape and durations. Variants: `single_cut` and `two_cut_optimal`. Five cores only.
- `compute_templates.py`: small exact-integer model for one stage, with the original first-stage structure. It reconstructs and checks FIFO/dependency timing and the five-state A-policy transition table. No official evaluator imports.
- `abstract_certificates.json`: all 59 operation owners, priority words, exact earliest start/end values, and a critical path for each small template. Timestamps are certificates, not submission fields.
- `verify_raw_plan.py`: an independent full-original-graph compute/FIFO/500 checker and optional official STATIC `derive_multicore_plan` check. It does not run Step2, Step3, or E0. Its minimal recognizer is for audit; production must use the existing full recognizer through `stage_migration.construct`.
- `raw_static_verification.json`: full original case051 check results.
- `case_051_single_cut_singleton_plan.json` and `case_051_two_cut_optimal_singleton_plan.json`: concrete two-field plans for that exact original graph; not official execution results.
- `*_metadata.json`: collector sequence and each actual original large-vector migration edge.

## The exact computation model

There are 48 indivisible 524-cycle V operations per stage, in twelve original four-operation chains. The original eleven scalar ADDs take 13 cycles each. Every vector operation has at least three scalar ADDs on its path to the stage root. The previous root precedes every operation of the next stage. Cross-core original dependencies have a 500-cycle lag. COPY service, memory, bandwidth and Cache are omitted.

For any later-stage previous-root core a and current-root core b, all 524-cycle operations on core c lie in one common necessary window: its beginning is at least 500 if c differs from a; its end is at most T minus 39 minus 500 if c differs from b. Hence

\[
48\le\sum_{c=0}^4\max\left(0,\left\lfloor\frac{T-39-500\mathbf1_{c\ne a}-500\mathbf1_{c\ne b}}{524}\right\rfloor\right).\tag{S.1}
\]

Below T=6279, equal root cores allow at most 11+4*9=47 large operations; distinct root cores allow at most 2*10+3*9=47. Thus every later stage needs at least 6279.

For the first stage, the incoming-root delays are absent. Below T=5779, the corresponding capacity is at most 10+4*9=46. Thus the first root needs at least 5779.

`two_cut_optimal` achieves both bounds, including original chain precedence and the unchanged ADD tree. Therefore for S stages,

\[
\operatorname{OPT}_{B,\mathrm{compute}+500}(S)=5779+(S-1)6279=6279S-500.\tag{S.2}
\]

This is also a lower bound on every successful guarded official singleton execution, NOT its predicted performance. No optimality claim is made for arbitrary non-singleton subgraphs or changed hardware constants/trees.

## Two-cut optimal template

Every stage has exactly two migrated vector boundaries: lane2 after its second original operation; lane9 after its second original operation.

Use roles a,b for alternating physical cores 0 and 1; physical cores2,3,4 stay fixed. Stage1 has a=0,b=1. Subsequently a is the previous root core and b the opposite core. Inclusive op ranges:

```
a: L2[1..2], L0, L10
b: L3, L4, L2[3..4]
2: L9[1..2], L5, L8
3: L1, L11, L9[3..4]
4: L6, L7
```

Subsequent stages append all scalar ADDs to b in this ORIGINAL-node order:

```
J0,J1,J2,J3,J6,J7,J9,J5,J4,J8,J10
```

The first stage moves only J5 (the original ADD of lanes10/11) to core a, after its vector word; b omits J5 from its word. This boundary treatment is necessary for this certificate to achieve 5779.

For later stages, vector-word ends are 5240 on a; 5740 on b,2,3; 4692 on4. The first seven ADDs finish on b at5831, J5 at5844. Late sibling scalars8/9 arrive at6240; J4,J8,J10 then finish at6253,6266,6279. All migration release constraints fit the certified words.

In stage1, a computes J5 from5240 to5253 and its result arrives at b at5753. J4 on b finishes at5753, then J8 and J10 at5766 and5779. This is a change of original-node owner, not a new ADD.

## Lower-traffic next candidate

`single_cut` uses only lane2's second-to-third operation boundary. It keeps every immutable-input head's original fixed core and collector2 throughout:

```
0: L2[1..2], L0, L1
1: L3, L4, L2[3..4]
2: L5, L6, L7
3: L8, L9
4: L10, L11
```

Pure ADDs use the current REDUCE/leaf ownership, not head ownership. Mixed ADDs go to core2. The resulting core2 ADD word is `J3,J2,J6,J7,J8,J9,J10`. Every stage takes6379 in the computation model, including the first stage. Later-stage gap to the B optimum is100 cycles.

In the no-spill task-rebuilding traffic calculation, each stage adds one 32768-byte COPY_OUT and one 32768-byte COPY_IN, plus five scalar gathers and four broadcasts except at the final boundary. Thus its structural added-copy bytes are

\[
65536S+4[5S+4(S-1)]=65572S-16.\tag{S.3}
\]

This structural accounting is not an official measured traffic result. Step2 spill and actual Cache/DDR service may change the result. The extra transfer can overlap computation, so its full transfer service must not simply be added to the compute bound.

## Reproduce the small model

```
python compute_templates.py
```

This recomputes the exact stage transition table, first-stage values, and the certificates. It reads the included original first-stage structure, not a full official-case package.

## Reproduce the full static original-graph check

From this directory, with paths adjusted to the repository:

```
python verify_raw_plan.py /path/to/repo/data/raw/a/official/data/case_051.json \
  --official-code /path/to/repo/data/raw/a/official/code \
  --output-dir /path/to/a/new/output-directory
```

Expected purely static case051 values: single_cut153096; two_cut_optimal150196. Both have passed original graph/plan static validation and independent augmented-DAG acyclicity/timing checks in this run. The actual repository integration wrapper has not been executed inside the user's repository; the builder it calls was used for these saved plans.

## Minimum next official action

First check/compile `single_cut` and run one official case051/k5 evaluation locally. Compare its complete official result against the available four-core result and the independently implemented alternating-collector candidate. Inspect spill, original-compute FIFO, migrated COPY_IN readiness and same-time DDR contention. Do not call153096 an expected official score. Use `two_cut_optimal` primarily as a sharp compute-model certificate until its extra vector traffic is checked.
