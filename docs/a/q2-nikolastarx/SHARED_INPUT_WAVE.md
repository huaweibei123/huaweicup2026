# P2 shared-input wave constructor

`src/q2_nikolastarx/shared_input_wave.py` offers `build(graph, cores, config)` and `build_from_index(index, cores, config)`. It returns the two-field official plan and separate diagnostic metadata. It makes zero E0/E1/E2 calls and does not choose among candidates by score.

## Applicability and construction

The guard requires at least two independent compute components and at least as many components as cores. At least two original external tensors must be consumed by every component, once each. Every compute operation has one output tensor; direct op edges, multi-producer tensors, contracted dependencies absent from tensor incidence, ambiguous repeated operation signatures within a component, and heterogeneous component templates are rejected with `UnsupportedStructure`. Signature matching uses the original shared tensor identity, operation type, pipe, duration, input provenance, and tensor position/size. It does not dispatch by case ID or operation ID. An operation or private tensor ID rename leaves the template matching intact.

Ownership remains `DAGIndex.assignment(cores)`, so whole components stay on one core. The first component's topological order fixes shared-input waves. For each wave, the constructor emits the dependency-closed prefix through that input's consumer for every component owned by a core. Remaining operations are then emitted in topological order. This places all same-core uses of each shared input close together while retaining a legal per-core FIFO. `derive_multicore_plan` statically validates the output.

## Memory interpretation and limits

Metadata includes the per-core peak of original-tensor first-to-last touch intervals in the submitted priority order. DDR graph inputs count against UB in this model. It also reports whether those peaks fit the provided L1/UB capacities. These values do **not** include official transformation copies, Step2 spill behavior, or Step3 reordering; `zero_spill_claim` is always false. The activation frontier grows with the number of components processed in parallel. The constructor currently reports rather than changes ownership or splits into smaller batches when that frontier exceeds capacity.

Read-only static construction of the three diagnosed four-core inputs gave raw L1 peaks of 86,144 B (044), 205,312 B (083), and 664,064 B (092), against 524,288 B L1 capacity. Thus 092 remains over the raw capacity. These are not official results or claims of makespan/spill improvement. No E0/E1/E2 calls were made. A synthetic three-component fixture reduced raw L1 peak from 360 B with `component_envelope` to 280 B with shared-input waves; both plans passed static validation. Run `python3 -B -m unittest tests.test_q2_shared_input_wave -v` for the focused tests.
